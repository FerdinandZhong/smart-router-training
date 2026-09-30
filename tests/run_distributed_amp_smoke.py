"""Exercise the real worker loop with two CPU/Gloo processes and mocked Ray I/O.

Run separately: PYTHONPATH=src:. python tests/run_distributed_amp_smoke.py
This proves backward/synchronization/reload logic, not Ray scheduling or GPU networking.
"""
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import torch
import torch.distributed as dist
import torch.multiprocessing as mp

ROOT = Path(__file__).resolve().parents[1]


def worker(rank, directory, stage):
    from smart_router.training.cluster_smoke import train_worker
    root = Path(directory)
    dist.init_process_group("gloo", init_method=(root / f"store-{stage}").as_uri(), rank=rank, world_size=2)
    def report(metrics, checkpoint=None):
        if checkpoint:
            with checkpoint.as_directory() as path:
                shutil.copytree(path, root / f"saved-{stage}")
    config = {"seed": 42, "dataset_path": str(ROOT / "data/pilot/pilot-smoke-v1"),
              "run_dir": directory, "stage": stage, "use_gpu": False, "steps": 20 if stage == "initial" else 2}
    if stage == "resume":
        config["resume_checkpoint"] = str(root / "saved-initial/model.pt")
    try:
        with patch("ray.train.get_context", return_value=SimpleNamespace(get_world_rank=lambda: rank, get_world_size=lambda: 2)), \
             patch("ray.get_runtime_context", return_value=SimpleNamespace(get_node_id=lambda: f"cpu-node-{rank}")), \
             patch("ray.train.torch.get_device", return_value=torch.device("cpu")), \
             patch("ray.train.torch.prepare_model", side_effect=torch.nn.parallel.DistributedDataParallel), \
             patch("ray.train.report", side_effect=report):
            train_worker(config)
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        for stage in ("initial", "resume"):
            mp.spawn(worker, args=(directory, stage), nprocs=2, join=True)
        root = Path(directory)
        initial = torch.load(root / "saved-initial/model.pt", weights_only=False)
        resumed = torch.load(root / "saved-resume/model.pt", weights_only=False)
        assert initial["step"] == 20 and resumed["step"] == 22
        assert not torch.equal(initial["model"]["weight"], resumed["model"]["weight"])
        assert initial["optimizer"]["state"]
        metrics = json.loads((root / "resume-metrics.json").read_text())
        assert metrics["start_step"] == 20 and metrics["weights_synchronized"]
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
        for stage, first, last in [('initial', 0, 20), ('resume', 20, 22)]:
            event_dir = root / 'tensorboard' / stage
            assert len(list(event_dir.glob('events.out.tfevents.*'))) == 1, 'Only rank zero should write'
            accumulator = EventAccumulator(str(event_dir)).Reload()
            losses = accumulator.Scalars('diagnostic/loss')
            assert [event.step for event in losses] == list(range(first, last + 1))
            stage_metrics = json.loads((root / f'{stage}-metrics.json').read_text())
            assert abs(losses[-1].value - stage_metrics['final_loss']) < 1e-5
        print("PASS: TensorBoard event steps, global loss and rank-zero-only writes")
        print("PASS: two-process CPU backward, synchronization, shared data, optimizer checkpoint and resume")
