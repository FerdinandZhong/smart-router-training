"""Two-node infrastructure diagnostic; reads pilot data, trains a controlled model.

This deliberately does not claim to fine-tune Laya or learn a useful router.
"""
import argparse
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
import time


def train_worker(config):
    import ray
    from ray import train
    import torch
    import torch.distributed as dist
    from ray.train.torch import get_device, prepare_model
    from smart_router.data.pilot_bundle import validate_bundle

    rank = train.get_context().get_world_rank()
    world_size = train.get_context().get_world_size()
    device = get_device()
    torch.manual_seed(config["seed"]); random.seed(config["seed"] + rank)
    manifest = validate_bundle(config["dataset_path"])
    root = Path(config["run_dir"])
    # Every worker must write its own file and read all peers' files on shared NFS.
    marker = root / f"{config['stage']}-worker-{rank}.json"
    identity = {"rank": rank, "ray_node_id": ray.get_runtime_context().get_node_id(),
                "device": str(device), "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "torch": torch.__version__, "ray": ray.__version__, "splits": manifest["splits"],
                "dataset_manifest_sha256": hashlib.sha256((Path(config["dataset_path"]) / "manifest.json").read_bytes()).hexdigest(),
                "bf16_supported": bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported())}
    marker.write_text(json.dumps(identity, indent=2))
    dist.barrier()
    identities = [json.loads((root / f"{config['stage']}-worker-{r}.json").read_text()) for r in range(world_size)]
    if config["use_gpu"] and len({i["ray_node_id"] for i in identities}) != world_size:
        raise RuntimeError("GPU diagnostic requires distinct Ray nodes")
    if len({i["dataset_manifest_sha256"] for i in identities}) != 1:
        raise RuntimeError("Workers see different pilot data")
    model = torch.nn.Linear(1, 1, bias=False)
    torch.nn.init.zeros_(model.weight)
    model = prepare_model(model)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1, momentum=0.9)
    start = 0
    if config.get("resume_checkpoint"):
        saved = torch.load(config["resume_checkpoint"], map_location=device, weights_only=False)
        model.module.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        start = saved["step"]
        torch.set_rng_state(saved["rng_by_rank"][rank]["torch"].cpu())
        random.setstate(saved["rng_by_rank"][rank]["python"])
        if device.type == "cuda":
            torch.cuda.set_rng_state(saved["rng_by_rank"][rank]["cuda"].cpu(), device)
    # Different, deterministic shards. This is a controlled y=2x diagnostic.
    x = torch.tensor([[rank + 1.0], [-(rank + 1.0)]], device=device)
    y = 2 * x
    def global_loss():
        with torch.no_grad():
            loss = torch.nn.functional.mse_loss(model(x), y)
            dist.all_reduce(loss)
            return loss.item() / world_size
    before = global_loss()
    for _ in range(config["steps"]):
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(x), y)
        loss.backward()
        if not all(torch.isfinite(p.grad).all() for p in model.parameters()):
            raise RuntimeError("Nonfinite gradients")
        optimizer.step()
    after = global_loss()
    weight = model.module.weight.detach().clone()
    weights = [torch.zeros_like(weight) for _ in range(world_size)]
    dist.all_gather(weights, weight)
    if not all(torch.allclose(weight, other, atol=1e-6) for other in weights):
        raise RuntimeError("DDP weights are not synchronized")
    if config["stage"] == "initial" and not after < before:
        raise RuntimeError("Controlled diagnostic loss did not decrease")
    rng = {"torch": torch.get_rng_state(), "python": random.getstate(),
           "cuda": torch.cuda.get_rng_state(device) if device.type == "cuda" else None}
    states = [None] * world_size
    dist.all_gather_object(states, rng)
    metrics = {"stage": config["stage"], "initial_loss": before, "final_loss": after,
               "start_step": start, "step": start + config["steps"], "weights_synchronized": True,
               "pilot_samples": sum(manifest["splits"].values()), "model": "controlled_linear_diagnostic"}
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = None
        if rank == 0:
            torch.save({"model": model.module.state_dict(), "optimizer": optimizer.state_dict(),
                        "step": metrics["step"], "rng_by_rank": states, "data_policy": "fixed_per_rank_controlled_inputs",
                        "identities": identities}, Path(directory) / "model.pt")
            checkpoint = train.Checkpoint.from_directory(directory)
            (root / f"{config['stage']}-metrics.json").write_text(json.dumps(metrics, indent=2))
        train.report(metrics, checkpoint=checkpoint)


def run(config, root, run_id):
    import ray
    from ray.train import FailureConfig, RunConfig, ScalingConfig
    from ray.train.torch import TorchConfig, TorchTrainer
    from smart_router.data.pilot_bundle import validate_bundle

    if ray.__version__ != "2.58.0":
        raise RuntimeError("Cluster smoke requires Ray 2.58.0")
    dataset = root / config["dataset"]
    manifest = validate_bundle(dataset)
    run_dir = root / config["output_dir"] / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "run-manifest.json").write_text(json.dumps({"config": config, "dataset_manifest": manifest}, indent=2))
    ray.init(address="auto")
    try:
        required = config["num_workers"] if config["use_gpu"] else 0
        deadline = time.monotonic() + config["collective_timeout_seconds"]
        while ray.available_resources().get("GPU", 0) < required:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Need {required} free GPUs; found {ray.available_resources().get('GPU', 0)}")
            time.sleep(5)
        common = {**config, "dataset_path": str(dataset), "run_dir": str(run_dir)}
        def fit(stage, **overrides):
            return TorchTrainer(
                train_worker, train_loop_config={**common, "stage": stage, **overrides},
                scaling_config=ScalingConfig(num_workers=config["num_workers"], use_gpu=config["use_gpu"],
                                             resources_per_worker={"CPU": config["cpus_per_worker"]}, placement_strategy="SPREAD"),
                torch_config=TorchConfig(backend="nccl" if config["use_gpu"] else "gloo",
                                         timeout_s=config["collective_timeout_seconds"]),
                run_config=RunConfig(name=stage, storage_path=str(run_dir / "ray"), failure_config=FailureConfig(max_failures=0)),
            ).fit()
        result = fit("initial")
        checkpoint_dir = run_dir / "reload-checkpoint"
        with result.checkpoint.as_directory() as directory:
            shutil.copytree(directory, checkpoint_dir)
        resumed = fit("resume", steps=2, resume_checkpoint=str(checkpoint_dir / "model.pt"))
        if resumed.metrics["start_step"] != config["steps"] or resumed.metrics["step"] != config["steps"] + 2:
            raise RuntimeError("Checkpoint step was not restored")
        (run_dir / "SUCCESS.json").write_text(json.dumps({"initial": result.metrics, "resume": resumed.metrics}, indent=2, default=str))
        print(f"Infrastructure smoke passed; artifacts: {run_dir}", flush=True)
    finally:
        ray.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    from amp.jobs import load_config
    run(load_config(args.config), args.project_root.resolve(), args.run_id)


if __name__ == "__main__":
    main()
