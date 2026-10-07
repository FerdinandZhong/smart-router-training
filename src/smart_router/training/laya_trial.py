"""Bounded two-GPU Laya head trial with masked targets and reload/resume gates."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import tempfile


def masked_binary_loss(logits, targets, observed):
    import torch
    per = -(torch.stack((1 - targets, targets), dim=-1) * logits.log_softmax(-1)).sum(-1)
    return (per * observed).sum(), observed.sum()


def summarize(items, classes, priors):
    import math
    result = {}
    for cls in classes:
        observed = [x for x in items if x['class_id'] == cls and x['observed']]
        losses, briers, prior_losses, prior_briers = [], [], [], []
        for x in observed:
            target = x['target']; p = min(1 - 1e-7, max(1e-7, x['probability']))
            q = min(1 - 1e-7, max(1e-7, priors[cls]))
            losses.append(-target * math.log(p) - (1-target) * math.log(1-p))
            briers.append((p-target)**2)
            prior_losses.append(-target * math.log(q) - (1-target) * math.log(1-q))
            prior_briers.append((q-target)**2)
        result[cls] = {'observed': len(observed), 'unknown': sum(x['class_id'] == cls and not x['observed'] for x in items),
                       'positive': sum(x['target'] == 1 for x in observed), 'negative': sum(x['target'] == 0 for x in observed),
                       'log_loss': sum(losses)/len(losses) if losses else None,
                       'brier': sum(briers)/len(briers) if briers else None,
                       'prior_log_loss': sum(prior_losses)/len(prior_losses) if prior_losses else None,
                       'prior_brier': sum(prior_briers)/len(prior_briers) if prior_briers else None}
    return result


def train_worker(cfg):
    import random
    import ray
    from ray import train
    from ray.train.torch import get_device, prepare_model
    import torch
    import torch.distributed as dist
    from torch.utils.tensorboard import SummaryWriter
    from smart_router.models.laya import batch, head_state, head_hash, load_model, prepare_rows
    from smart_router.data.pilot_bundle import validate_bundle

    rank = train.get_context().get_world_rank(); world = train.get_context().get_world_size()
    device = get_device(); torch.cuda.set_device(device)
    torch.manual_seed(cfg['seed']); random.seed(cfg['seed'] + rank)
    root = Path(cfg['run_dir']); dataset = Path(cfg['dataset_path'])
    validate_bundle(dataset)
    task = json.loads((dataset/'task.json').read_text()); classes = [c['id'] for c in task['classes']]
    model, tokenizer = load_model(cfg['model_path'])
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('BF16 unavailable for pinned trial recipe')
    records = {split: [json.loads(line) for line in (dataset/f'{split}.jsonl').read_text().splitlines()]
               for split in ['train', 'validation']}
    rows, audits = {}, {}
    for split, samples in records.items():
        rows[split], audits[split] = prepare_rows(samples, task, tokenizer, cfg['max_len'], cfg['head_max_len'])
    if rank == 0:
        for split, entries in audits.items():
            (root/f'{split}-view-audit.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in entries))
    priors = {}
    for cls in classes:
        values = [x['targets'][cls] for x in records['train'] if x['targets'][cls] is not None]
        if not values: raise RuntimeError('No training observations for '+cls)
        priors[cls] = sum(values)/len(values)
    identity = {'rank': rank, 'ray_node_id': ray.get_runtime_context().get_node_id(),
                'device': str(device), 'gpu': torch.cuda.get_device_name(device),
                'dataset_sha256': hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest(),
                'model_revision': cfg['model_revision'], 'source_revision': cfg['source_revision'],
                'torch': torch.__version__, 'ray': ray.__version__, 'cuda': torch.version.cuda,
                'bf16': True, 'class_ids': classes}
    peers = [None]*world; dist.all_gather_object(peers, identity)
    if len({p['ray_node_id'] for p in peers}) != world:raise RuntimeError('Workers must use distinct Ray nodes')
    if len({p['dataset_sha256'] for p in peers}) != 1:raise RuntimeError('Dataset hashes differ')
    (root/f"{cfg['stage']}-worker-{rank}.json").write_text(json.dumps(identity,indent=2))
    model = prepare_model(model, parallel_strategy_kwargs={'broadcast_buffers': False})
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg['learning_rate'])
    start = 0
    if cfg.get('resume_checkpoint'):
        saved = torch.load(cfg['resume_checkpoint'], map_location='cpu', weights_only=False)
        if saved['class_ids'] != classes or saved['dataset_sha256'] != identity['dataset_sha256'] or saved['model_revision'] != cfg['model_revision']:
            raise RuntimeError('Checkpoint schema/data/model mismatch')
        model.module.load_state_dict(saved['head'], strict=False)
        optimizer.load_state_dict(saved['optimizer']); start = saved['step']
        if saved['data_position'] != start*world:raise RuntimeError('Checkpoint data position mismatch')
        torch.set_rng_state(saved['rng'][rank]['torch']); random.setstate(saved['rng'][rank]['python'])
        torch.cuda.set_rng_state(saved['rng'][rank]['cuda'], device)
    before = head_hash(model.module)
    writer = SummaryWriter(str(root/'tensorboard'/cfg['stage'])) if rank == 0 else None
    train_losses = []; grad_nonzero = False
    try:
        model.train()
        for offset in range(cfg['stage_steps']):
            step = start + offset
            row = rows['train'][(step*world+rank) % len(rows['train'])]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.bfloat16):logits = model(**batch(row, device))
            target = torch.tensor([row['target'] if row['target'] is not None else 0.0],device=device)
            observed = torch.tensor([row['observed']],device=device,dtype=torch.float)
            numerator, count = masked_binary_loss(logits, target, observed)
            global_count = count.detach().clone(); dist.all_reduce(global_count)
            # DDP averages rank gradients: compensate by world/global observed count.
            loss = numerator*world/global_count.clamp_min(1)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
            loss.backward()
            grads = [p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
            if not grads or not all(torch.isfinite(g).all() for g in grads):raise RuntimeError('Missing/nonfinite head gradients')
            grad_nonzero |= any(torch.count_nonzero(g).item()>0 for g in grads)
            if global_count.item()>0:optimizer.step()
            total_loss = numerator.detach().clone();dist.all_reduce(total_loss)
            value = total_loss.item()/max(1,global_count.item());train_losses.append(value)
            if writer:writer.add_scalar('train/masked_loss',value,step+1)
        after = head_hash(model.module)
        hashes = [None]*world;dist.all_gather_object(hashes,after)
        if len(set(hashes)) != 1:raise RuntimeError('Trained head hashes differ across ranks')
        if before == after or not grad_nonzero:raise RuntimeError('Head did not receive nonzero gradients and updates')
        model.eval();predictions=[]
        with torch.no_grad():
            for row in rows['validation'][rank::world]:
                with torch.autocast('cuda',dtype=torch.bfloat16):logits=model.module(**batch(row,device))
                probability=logits.softmax(-1)[0,1].item()
                if not 0<=probability<=1:raise RuntimeError('Nonfinite validation probability')
                predictions.append({k:row[k] for k in ['class_id','example_id','target','observed']} | {'probability':probability})
        all_predictions=[None]*world;dist.all_gather_object(all_predictions,predictions)
        metrics = {'stage':cfg['stage'],'start_step':start,'step':start+cfg['stage_steps'],
                   'nonzero_finite_gradients':grad_nonzero,'head_changed':before!=after,'head_hash':after,
                   'weights_synchronized':True,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(device),
                   'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad)}
        rng={'torch':torch.get_rng_state(),'cuda':torch.cuda.get_rng_state(device),'python':random.getstate()}
        states=[None]*world;dist.all_gather_object(states,rng)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint=None
            if rank==0:
                flat=[x for part in all_predictions for x in part]
                if len(flat)!=len(rows['validation']):raise RuntimeError('Validation row count mismatch')
                validation=summarize(flat,classes,priors)
                (root/f"{cfg['stage']}-validation.json").write_text(json.dumps({'class_ids':classes,'training_priors':priors,'metrics':validation,'predictions':flat},indent=2))
                (root/f"{cfg['stage']}-metrics.json").write_text(json.dumps(metrics,indent=2))
                for cls,v in validation.items():
                    if v['log_loss'] is not None:writer.add_scalar('validation/'+cls+'/log_loss',v['log_loss'],metrics['step'])
                    if v['brier'] is not None:writer.add_scalar('validation/'+cls+'/brier',v['brier'],metrics['step'])
                saved={'head':head_state(model.module),'optimizer':optimizer.state_dict(),'step':metrics['step'],
                       'data_position':metrics['step']*world,'rng':states,'class_ids':classes,
                       'task':task,'dataset_sha256':identity['dataset_sha256'],'model_revision':cfg['model_revision'],
                       'source_revision':cfg['source_revision'],'view_policy':'canonical_input_prefix_tail_tokens_v1'}
                torch.save(saved,Path(directory)/'head.pt')
                checkpoint=train.Checkpoint.from_directory(directory)
            train.report(metrics,checkpoint=checkpoint)
    finally:
        if writer:writer.close()


def run(cfg,root,run_id):
    import torch
    import ray
    from ray.train import ScalingConfig,RunConfig,FailureConfig
    from ray.train.torch import TorchTrainer,TorchConfig
    from smart_router.data.pilot_bundle import validate_bundle
    from smart_router.models.laya import batch,head_hash,load_model,prepare_rows
    dataset=root/cfg['dataset'];dataset_manifest=validate_bundle(dataset)
    cache=json.loads((root/'.amp-state/laya-model.json').read_text())
    if cache['revision']!=cfg['model_revision'] or cache['source_revision']!=cfg['source_revision']:raise RuntimeError('Model snapshot revision mismatch')
    run_dir=root/cfg['output_dir']/run_id;run_dir.mkdir(parents=True,exist_ok=False)
    inventory={p:importlib.metadata.version(p) for p in ['laya','torch','ray','transformers','safetensors','huggingface-hub','tokenizers']}
    (run_dir/'run-manifest.json').write_text(json.dumps({'config':cfg,'environment':inventory,'model_cache':cache,
           'dataset_manifest':dataset_manifest,'purpose':'engineering_smoke_not_quality_benchmark','holdouts':['calibration','test']},indent=2))
    ray.init(address='auto')
    try:
        common={**cfg,'model_path':cache['path'],'run_dir':str(run_dir),'dataset_path':str(dataset)}
        def fit(stage,steps,**extra):
            return TorchTrainer(train_worker,train_loop_config={**common,'stage':stage,'stage_steps':steps,**extra},
                scaling_config=ScalingConfig(num_workers=2,use_gpu=True,resources_per_worker={'CPU':cfg['cpus_per_worker']},placement_strategy='SPREAD'),
                torch_config=TorchConfig(backend='nccl',timeout_s=cfg['collective_timeout_seconds']),
                run_config=RunConfig(name=stage,storage_path=str(run_dir/'ray'),failure_config=FailureConfig(max_failures=0))).fit()
        initial=fit('initial',cfg['steps'])
        with initial.checkpoint.as_directory() as directory:shutil.copytree(directory,run_dir/'reload-checkpoint')
        checkpoint=run_dir/'reload-checkpoint/head.pt'
        # Fresh construction on CPU independently reloads head and checks class-aligned scores.
        model,tokenizer=load_model(cache['path']);saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
        model.load_state_dict(saved['head'],strict=False);model.eval()
        if head_hash(model)!=initial.metrics['head_hash']:raise RuntimeError('Fresh head reload hash mismatch')
        sample=json.loads((dataset/'train.jsonl').read_text().splitlines()[0]);task=json.loads((dataset/'task.json').read_text())
        rows,_=prepare_rows([sample],task,tokenizer,cfg['max_len'],cfg['head_max_len'])
        with torch.no_grad(): probabilities={r['class_id']:model(**batch(r,torch.device('cpu'))).softmax(-1)[0,1].item() for r in rows}
        if not all(0<=p<=1 for p in probabilities.values()):raise RuntimeError('Invalid reload predictions')
        (run_dir/'reload-predictions.json').write_text(json.dumps(probabilities,indent=2))
        del model,tokenizer
        resumed=fit('resume',cfg['resume_steps'],resume_checkpoint=str(checkpoint))
        if resumed.metrics['start_step']!=cfg['steps'] or resumed.metrics['step']!=cfg['steps']+cfg['resume_steps']:raise RuntimeError('Resume step mismatch')
        (run_dir/'SUCCESS.json').write_text(json.dumps({'initial':initial.metrics,'resume':resumed.metrics,'reload_predictions':probabilities},indent=2))
        print('Laya pilot smoke passed; artifacts:',run_dir,flush=True)
    finally:ray.shutdown()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--project-root',type=Path,required=True);parser.add_argument('--run-id',required=True)
    args=parser.parse_args();cfg=json.loads(args.config.read_text())
    if cfg.get('purpose')!='laya_pilot_smoke' or cfg.get('num_workers')!=2:raise ValueError('Expected two-worker Laya smoke config')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',args.run_id):raise ValueError('Invalid run ID')
    run(cfg,args.project_root,args.run_id)


if __name__=='__main__':main()
