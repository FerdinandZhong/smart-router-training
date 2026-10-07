"""Full pilot epochs over independent route labels; selection uses validation only."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import re
import shutil
import tempfile
import time

from smart_router.schemas import canonical_json
from smart_router.training.laya_trial import masked_binary_loss, summarize


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    if cfg.get('purpose') != 'laya_pilot_training' or cfg.get('num_workers') != 2:
        raise ValueError('Expected two-worker laya_pilot_training config')
    for key in ['cpus_per_worker', 'batch_size_per_worker', 'max_epochs', 'min_epochs',
                'early_stopping_patience', 'max_len', 'head_max_len',
                'collective_timeout_seconds', 'job_timeout_seconds']:
        if type(cfg.get(key)) is not int or cfg[key] <= 0:
            raise ValueError(f'{key} must be a positive integer')
    if not 64 <= cfg['head_max_len'] < cfg['max_len'] <= 8192:
        raise ValueError('Require 64 <= head_max_len < max_len <= 8192')
    if cfg['min_epochs'] > cfg['max_epochs']:
        raise ValueError('min_epochs exceeds max_epochs')
    for key in ['learning_rate', 'weight_decay', 'warmup_fraction', 'max_grad_norm']:
        value = cfg.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f'{key} must be finite and nonnegative')
    if not cfg['learning_rate'] or not cfg['max_grad_norm'] or cfg['warmup_fraction'] >= 1:
        raise ValueError('Invalid optimizer/scheduler configuration')
    for key in ['model_revision', 'source_revision']:
        if not re.fullmatch('[a-f0-9]{40}', cfg.get(key, '')):
            raise ValueError(f'{key} must be a pinned commit')
    allowed = {'NCCL_IB_DISABLE', 'NCCL_SOCKET_IFNAME', 'GLOO_SOCKET_IFNAME', 'NCCL_DEBUG'}
    if set(cfg.get('collective_env', {})) - allowed or not all(isinstance(v, str) for v in cfg['collective_env'].values()):
        raise ValueError('Unsupported collective environment')
    return cfg


def epoch_indices(count, world, batch_size, seed, epoch):
    """Every real question once; None pads the last global batch without a target."""
    order = list(range(count))
    random.Random(seed + epoch).shuffle(order)
    width = world * batch_size
    return [order[start:start + width] + [None] * max(0, start + width - count)
            for start in range(0, count, width)]


def collate(rows, device, pad_id):
    import torch
    size = max(len(row['input_ids']) for row in rows)
    ids = torch.full((len(rows), size), pad_id, dtype=torch.long, device=device)
    attention = torch.zeros_like(ids)
    for i, row in enumerate(rows):
        length = len(row['input_ids'])
        ids[i, :length] = torch.tensor(row['input_ids'], device=device)
        attention[i, :length] = 1
    inputs = {'input_ids': ids, 'attention_mask': attention,
              'marker_pos': torch.tensor([row['marker_pos'] for row in rows], device=device),
              'marker_mask': torch.ones((len(rows), 2), dtype=torch.bool, device=device),
              'qtype': torch.full((len(rows),), 2, dtype=torch.long, device=device)}
    targets = torch.tensor([row['target'] if row['target'] is not None else 0.0 for row in rows], device=device)
    mask = torch.tensor([row['observed'] for row in rows], dtype=torch.float32, device=device)
    return inputs, targets, mask


def macro_loss(metrics):
    values = [value['log_loss'] for value in metrics.values() if value['observed']]
    if not values:
        raise ValueError('No validation observations')
    return sum(values) / len(values)


def selection_state(score, epoch, best_score, best_epoch, stale_epochs):
    improved = score < best_score
    return (score, epoch, 0, True) if improved else (best_score, best_epoch, stale_epochs + 1, False)


def training_fingerprint(cfg, task, data_hash):
    # Execution/output paths do not change optimizer or data semantics.
    recipe = {k: v for k, v in cfg.items() if k not in ['output_dir', 'job_timeout_seconds']}
    return hashlib.sha256(canonical_json({'recipe': recipe, 'task': task, 'dataset': data_hash}).encode()).hexdigest()


def train_worker(cfg):
    import ray
    from ray import train
    from ray.train.torch import get_device, prepare_model
    import torch
    import torch.distributed as dist
    from torch.utils.tensorboard import SummaryWriter
    from smart_router.data.pilot_bundle import validate_bundle
    from smart_router.models.laya import head_hash, head_state, load_model, prepare_rows

    rank = train.get_context().get_world_rank()
    world = train.get_context().get_world_size()
    device = get_device()
    torch.cuda.set_device(device)
    torch.manual_seed(cfg['seed'] + rank)
    random.seed(cfg['seed'] + rank)
    root = Path(cfg['run_dir'])
    dataset = Path(cfg['dataset_path'])
    manifest = validate_bundle(dataset)
    task = json.loads((dataset / 'task.json').read_text())
    classes = [c['id'] for c in task['classes']]
    data_hash = hashlib.sha256((dataset / 'manifest.json').read_bytes()).hexdigest()
    fingerprint = training_fingerprint(cfg['recipe'], task, data_hash)
    model, tokenizer = load_model(cfg['model_path'])
    if cfg['max_len'] > model.inner.encoder.config.max_position_embeddings:
        raise ValueError('Context exceeds pinned encoder position budget')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('BF16 unavailable')
    records = {split: [json.loads(line) for line in (dataset / f'{split}.jsonl').read_text().splitlines()]
               for split in ['train', 'validation']}
    rows, audits = {}, {}
    for split, samples in records.items():
        rows[split], audits[split] = prepare_rows(samples, task, tokenizer, cfg['max_len'], cfg['head_max_len'])
    if rank == 0:
        for split, entries in audits.items():
            (root / f'{split}-view-audit.jsonl').write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
    priors = {}
    for cls in classes:
        values = [record['targets'][cls] for record in records['train'] if record['targets'][cls] is not None]
        if not values:
            raise ValueError(f'No training observations for {cls}')
        priors[cls] = sum(values) / len(values)
    identity = {'rank': rank, 'ray_node_id': ray.get_runtime_context().get_node_id(),
                'gpu': torch.cuda.get_device_name(device), 'device': str(device),
                'dataset_sha256': data_hash, 'recipe_fingerprint': fingerprint, 'class_ids': classes,
                'torch': torch.__version__, 'ray': ray.__version__, 'cuda': torch.version.cuda}
    peers = [None] * world
    dist.all_gather_object(peers, identity)
    if len({p['ray_node_id'] for p in peers}) != world or len({p['recipe_fingerprint'] for p in peers}) != 1:
        raise RuntimeError('Distinct nodes and identical task/data/recipe required')
    (root / f'worker-{rank}.json').write_text(json.dumps(identity, indent=2))
    model = prepare_model(model, parallel_strategy_kwargs={'broadcast_buffers': False})
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                                 lr=cfg['learning_rate'], weight_decay=cfg['weight_decay'])
    steps_per_epoch = math.ceil(len(rows['train']) / (world * cfg['batch_size_per_worker']))
    total_steps = steps_per_epoch * cfg['max_epochs']
    warmup = max(1, int(total_steps * cfg['warmup_fraction']))
    def lr_multiplier(step):
        if step < warmup:
            return (step + 1) / warmup
        progress = min(1, (step - warmup) / max(1, total_steps - warmup))
        return 0.5 * (1 + math.cos(math.pi * progress))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_multiplier)
    original_hash = head_hash(model.module)
    start_epoch = 1
    global_step = optimizer_steps = 0
    best_score, best_epoch, stale = float('inf'), 0, 0
    saved_best_path = None
    if cfg.get('resume_checkpoint'):
        saved = torch.load(cfg['resume_checkpoint'], map_location='cpu', weights_only=False)
        if saved['recipe_fingerprint'] != fingerprint or saved['world_size'] != world:
            raise ValueError('Resume data/task/recipe/world-size mismatch')
        model.module.load_state_dict(saved['head'], strict=False)
        optimizer.load_state_dict(saved['optimizer'])
        scheduler.load_state_dict(saved['scheduler'])
        start_epoch = saved['next_epoch']
        global_step, optimizer_steps = saved['global_step'], saved['optimizer_steps']
        best_score, best_epoch, stale = saved['best_score'], saved['best_epoch'], saved['stale_epochs']
        saved_best_path = saved['best_checkpoint']
        torch.set_rng_state(saved['rng'][rank]['torch'])
        torch.cuda.set_rng_state(saved['rng'][rank]['cuda'], device)
        random.setstate(saved['rng'][rank]['python'])
        if start_epoch > cfg['max_epochs']:
            raise ValueError('Resume checkpoint already completed all configured epochs')

    writer = SummaryWriter(str(root / 'tensorboard' / 'pilot')) if rank == 0 else None
    def evaluate(epoch):
        model.eval()
        predictions = []
        with torch.no_grad():
            for start in range(rank * cfg['batch_size_per_worker'], len(rows['validation']), world * cfg['batch_size_per_worker']):
                chunk = rows['validation'][start:start + cfg['batch_size_per_worker']]
                inputs, _, _ = collate(chunk, device, tokenizer.pad_token_id)
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    scores = model.module(**inputs).softmax(-1)[:, 1]
                if not torch.isfinite(scores).all():
                    raise RuntimeError('Nonfinite validation probabilities')
                for row, probability in zip(chunk, scores.cpu().tolist()):
                    predictions.append({k: row[k] for k in ['example_id', 'class_id', 'target', 'observed']} | {'probability': probability})
        parts = [None] * world
        dist.all_gather_object(parts, predictions)
        flat = [item for part in parts for item in part]
        keys = {(item['example_id'], item['class_id']) for item in flat}
        if len(flat) != len(rows['validation']) or len(keys) != len(flat):
            raise RuntimeError('Validation rows duplicated or omitted')
        metrics = summarize(flat, classes, priors)
        if rank == 0:
            (root / f'epoch-{epoch:03d}-validation.json').write_text(json.dumps(
                {'epoch': epoch, 'training_priors': priors, 'metrics': metrics, 'predictions': flat}, indent=2))
            writer.add_scalar('validation/macro_log_loss', macro_loss(metrics), global_step)
            for cls, value in metrics.items():
                for metric in ['log_loss', 'brier', 'prior_log_loss', 'prior_brier']:
                    if value[metric] is not None:
                        writer.add_scalar(f'validation/{cls}/{metric}', value[metric], global_step)
        model.train()
        return metrics

    try:
        # Preflight uses the longest observed questions, without updating weights.
        state = {'torch': torch.get_rng_state(), 'cuda': torch.cuda.get_rng_state(device), 'python': random.getstate()}
        longest = sorted([row for row in rows['train'] if row['observed']], key=lambda row: len(row['input_ids']), reverse=True)
        chunk = longest[rank * cfg['batch_size_per_worker']:(rank + 1) * cfg['batch_size_per_worker']]
        inputs, target, mask = collate(chunk, device, tokenizer.pad_token_id)
        model.train()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(**inputs)
        numerator, count = masked_binary_loss(logits, target, mask)
        total_count = count.detach().clone()
        dist.all_reduce(total_count)
        (numerator * world / total_count).backward()
        gradients = [p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
        if not gradients or not all(torch.isfinite(g).all() for g in gradients):
            raise RuntimeError('Context/batch preflight produced invalid gradients')
        optimizer.zero_grad(set_to_none=True)
        torch.set_rng_state(state['torch'])
        torch.cuda.set_rng_state(state['cuda'], device)
        random.setstate(state['python'])
        preflight = {'rank': rank, 'max_sequence_tokens': inputs['input_ids'].shape[1],
                     'batch_size': inputs['input_ids'].shape[0], 'finite_gradients': True,
                     'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated(device)}
        (root / f'preflight-worker-{rank}.json').write_text(json.dumps(preflight, indent=2))
        del logits, gradients, inputs
        if rank == 0:
            print('Context/batch GPU preflight passed:', preflight, flush=True)
        evaluate(0)
        dummy = dict(rows['train'][0], observed=0, target=None, example_id=None)
        history = []
        for epoch in range(start_epoch, cfg['max_epochs'] + 1):
            epoch_started = time.monotonic()
            sum_loss = sum_observed = 0.0
            seen = []
            for global_indices in epoch_indices(len(rows['train']), world, cfg['batch_size_per_worker'], cfg['seed'], epoch):
                local_indices = global_indices[rank * cfg['batch_size_per_worker']:(rank + 1) * cfg['batch_size_per_worker']]
                seen.extend(index for index in local_indices if index is not None)
                chunk = [rows['train'][index] if index is not None else dummy for index in local_indices]
                inputs, target, mask = collate(chunk, device, tokenizer.pad_token_id)
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    logits = model(**inputs)
                numerator, count = masked_binary_loss(logits, target, mask)
                totals = torch.stack((numerator.detach(), count.detach()))
                dist.all_reduce(totals)
                loss = numerator * world / totals[1].clamp_min(1)
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite training loss')
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], cfg['max_grad_norm'], error_if_nonfinite=True)
                if totals[1].item() > 0:
                    optimizer.step()
                    optimizer_steps += 1
                scheduler.step()
                global_step += 1
                sum_loss += totals[0].item()
                sum_observed += totals[1].item()
                if writer:
                    writer.add_scalar('train/masked_loss', totals[0].item() / max(1, totals[1].item()), global_step)
                    writer.add_scalar('train/learning_rate', optimizer.param_groups[0]['lr'], global_step)
                    writer.add_scalar('train/gradient_norm', norm.item(), global_step)
            coverage = [None] * world
            dist.all_gather_object(coverage, seen)
            covered = [index for part in coverage for index in part]
            if sorted(covered) != list(range(len(rows['train']))):
                raise RuntimeError('Epoch did not cover every training question exactly once')
            if int(sum_observed) != sum(row['observed'] for row in rows['train']):
                raise RuntimeError('Observed-target coverage mismatch')
            validation = evaluate(epoch)
            score = macro_loss(validation)
            best_score, best_epoch, stale, improved = selection_state(score, epoch, best_score, best_epoch, stale)
            epoch_hash = head_hash(model.module)
            hashes = [None] * world
            dist.all_gather_object(hashes, epoch_hash)
            if len(set(hashes)) != 1 or epoch_hash == original_hash:
                raise RuntimeError('Head updates missing or ranks diverged')
            metrics = {'epoch': epoch, 'global_step': global_step, 'optimizer_steps': optimizer_steps,
                       'train_epoch_log_loss': sum_loss / sum_observed, 'validation_macro_log_loss': score,
                       'best_epoch': best_epoch, 'best_validation_macro_log_loss': best_score,
                       'head_hash': epoch_hash, 'weights_synchronized': True,
                       'train_questions_covered': len(covered), 'train_states': len(records['train']),
                       'observed_targets_covered': int(sum_observed), 'epoch_seconds': time.monotonic() - epoch_started,
                       'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated(device)}
            history.append(metrics)
            rng = {'torch': torch.get_rng_state(), 'cuda': torch.cuda.get_rng_state(device), 'python': random.getstate()}
            all_rng = [None] * world
            dist.all_gather_object(all_rng, rng)
            with tempfile.TemporaryDirectory() as directory:
                checkpoint = None
                if rank == 0:
                    if improved:
                        saved_best_path = str(root / f'best-epoch-{epoch:03d}.pt')
                    saved = {'head': head_state(model.module), 'optimizer': optimizer.state_dict(),
                             'scheduler': scheduler.state_dict(), 'next_epoch': epoch + 1,
                             'global_step': global_step, 'optimizer_steps': optimizer_steps,
                             'rng': all_rng, 'world_size': world, 'task': task, 'class_ids': classes,
                             'recipe_fingerprint': fingerprint, 'recipe': cfg['recipe'],
                             'dataset_manifest': manifest, 'model_revision': cfg['model_revision'],
                             'source_revision': cfg['source_revision'], 'best_score': best_score,
                             'best_epoch': best_epoch, 'stale_epochs': stale, 'best_checkpoint': saved_best_path,
                             'metrics': metrics, 'validation_metrics': validation}
                    torch.save(saved, Path(directory) / 'head.pt')
                    if improved:
                        shutil.copy2(Path(directory) / 'head.pt', saved_best_path)
                    (root / f'epoch-{epoch:03d}-metrics.json').write_text(json.dumps(metrics, indent=2))
                    writer.add_scalar('train/epoch_log_loss', metrics['train_epoch_log_loss'], global_step)
                    writer.add_scalar('perf/epoch_seconds', metrics['epoch_seconds'], global_step)
                    writer.flush()
                    print(f"Epoch {epoch}: train={metrics['train_epoch_log_loss']:.5f} validation={score:.5f} best={best_epoch} coverage={len(covered)}", flush=True)
                    checkpoint = train.Checkpoint.from_directory(directory)
                train.report(metrics, checkpoint=checkpoint)
            if epoch >= cfg['min_epochs'] and stale >= cfg['early_stopping_patience']:
                break
        if rank == 0:
            (root / 'training-summary.json').write_text(json.dumps({'history': history, 'best_epoch': best_epoch,
                    'best_checkpoint': saved_best_path, 'selection_metric': 'validation_macro_log_loss',
                    'early_stopped': epoch < cfg['max_epochs'], 'holdouts': ['calibration', 'test']}, indent=2))
    finally:
        if writer:
            writer.close()


def run(cfg, root, run_id, resume_checkpoint=None):
    import ray
    import torch
    from ray.train import FailureConfig, RunConfig, ScalingConfig
    from ray.train.torch import TorchConfig, TorchTrainer
    from smart_router.data.pilot_bundle import validate_bundle
    from smart_router.models.laya import batch, head_hash, head_state, load_model, prepare_rows

    dataset = root / cfg['dataset']
    data_manifest = validate_bundle(dataset)
    cache = json.loads((root / '.amp-state/laya-model.json').read_text())
    if cache['revision'] != cfg['model_revision'] or cache['source_revision'] != cfg['source_revision']:
        raise ValueError('Pinned source/model cache mismatch')
    run_dir = root / cfg['output_dir'] / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    inventory = {package: importlib.metadata.version(package) for package in
                 ['laya', 'torch', 'ray', 'transformers', 'safetensors', 'huggingface-hub', 'tokenizers']}
    files = ['src/smart_router/training/laya_pilot.py', 'src/smart_router/models/laya.py', 'configs/training/laya-pilot.json']
    source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
    manifest = {'run_id': run_id, 'config': cfg, 'environment': inventory, 'model_cache': cache,
                'dataset_manifest': data_manifest, 'source_sha256': source_hashes,
                'holdouts': ['calibration', 'test'], 'resume_checkpoint': resume_checkpoint,
                'selection_metric': 'validation_macro_log_loss', 'train_mode': 'frozen_encoder_decision_head',
                'probabilities': 'independent_uncalibrated', 'view_policy': 'canonical_input_prefix_tail_tokens_v1'}
    (run_dir / 'run-manifest.json').write_text(json.dumps(manifest, indent=2))
    ray.init(address='auto')
    try:
        if ray.available_resources().get('GPU', 0) < 2:
            raise RuntimeError('Two available GPUs required')
        common = {**cfg, 'recipe': cfg, 'model_path': cache['path'], 'run_dir': str(run_dir),
                  'dataset_path': str(dataset), 'resume_checkpoint': resume_checkpoint}
        result = TorchTrainer(train_worker, train_loop_config=common,
            scaling_config=ScalingConfig(num_workers=2, use_gpu=True,
                resources_per_worker={'CPU': cfg['cpus_per_worker']}, placement_strategy='SPREAD'),
            torch_config=TorchConfig(backend='nccl', timeout_s=cfg['collective_timeout_seconds']),
            run_config=RunConfig(name='pilot', storage_path=str(run_dir / 'ray'), failure_config=FailureConfig(max_failures=0))).fit()
        summary = json.loads((run_dir / 'training-summary.json').read_text())
        selected = torch.load(summary['best_checkpoint'], map_location='cpu', weights_only=False)
        model, tokenizer = load_model(cache['path'])
        model.load_state_dict(selected['head'], strict=False)
        model.eval()
        if head_hash(model) != selected['metrics']['head_hash']:
            raise RuntimeError('Selected checkpoint reload hash mismatch')
        sample = json.loads((dataset / 'validation.jsonl').read_text().splitlines()[0])
        task = json.loads((dataset / 'task.json').read_text())
        prepared, _ = prepare_rows([sample], task, tokenizer, cfg['max_len'], cfg['head_max_len'])
        with torch.no_grad():
            probabilities = {row['class_id']: model(**batch(row, torch.device('cpu'))).softmax(-1)[0, 1].item() for row in prepared}
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities.values()):
            raise RuntimeError('Invalid fresh reload predictions')
        export = run_dir / 'artifact'
        export.mkdir()
        torch.save(head_state(model), export / 'decision-head.pt')
        artifact = {'task': task, 'model_cache': cache, 'source_revision': cfg['source_revision'],
                    'recipe': cfg, 'selected_epoch': summary['best_epoch'],
                    'head_hash': selected['metrics']['head_hash'], 'dataset_manifest': data_manifest,
                    'class_ids': selected['class_ids'], 'probabilities': 'independent_uncalibrated',
                    'view_policy': manifest['view_policy'], 'validation_metrics': selected['validation_metrics'],
                    'head_sha256': hashlib.sha256((export / 'decision-head.pt').read_bytes()).hexdigest()}
        (export / 'manifest.json').write_text(json.dumps(artifact, indent=2))
        (run_dir / 'reload-predictions.json').write_text(json.dumps(probabilities, indent=2))
        success = {'best_epoch': summary['best_epoch'], 'epochs_completed': result.metrics['epoch'],
                   'best_validation_macro_log_loss': summary['history'][summary['best_epoch'] - summary['history'][0]['epoch']]['validation_macro_log_loss']
                   if summary['best_epoch'] >= summary['history'][0]['epoch'] else selected['best_score'],
                   'weights_synchronized': True, 'fresh_reload_verified': True,
                   'artifact': str(export), 'validation_metrics': selected['validation_metrics'],
                   'early_stopped': summary['early_stopped'], 'calibration_test_held_out': True}
        (run_dir / 'SUCCESS.json').write_text(json.dumps(success, indent=2))
        print('Full Laya pilot training passed; artifacts:', run_dir, flush=True)
    finally:
        ray.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--resume-checkpoint')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', args.run_id):
        raise ValueError('Invalid run ID')
    run(load_config(args.config), args.project_root, args.run_id, args.resume_checkpoint)


if __name__ == '__main__':
    main()
