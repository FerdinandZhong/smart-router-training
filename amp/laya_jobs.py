#!/usr/bin/env python3
"""Plan/submit the bounded Laya pilot trial using the shared training virtualenv."""
import argparse
import json
import os
import shlex
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from amp.environment import isolated_environment
from amp.jobs import build_submission,cluster_address,wait_for_job


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['plan','submit','status','logs','stop'])
    parser.add_argument('--submission-id',required=True)
    parser.add_argument('--config',default='configs/training/laya-first-trial.json')
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--resume-checkpoint')
    args=parser.parse_args();path=(ROOT/args.config).resolve();cfg=json.loads(path.read_text())
    modules={'laya_pilot_smoke':'laya_trial','laya_pilot_training':'laya_pilot'}
    if cfg.get('purpose') not in modules:raise ValueError('Expected a Laya training configuration')
    if cfg['purpose']=='laya_pilot_training':
        from smart_router.training.laya_pilot import load_config
        cfg=load_config(path)
    elif args.resume_checkpoint:raise ValueError('Explicit resume is supported by the full pilot')
    payload=build_submission(ROOT,path,args.submission_id,cfg['collective_env'])
    payload['entrypoint']=payload['entrypoint'].replace('smart_router.training.cluster_smoke','smart_router.training.'+modules[cfg['purpose']])
    if args.resume_checkpoint:payload['entrypoint']+=' --resume-checkpoint '+shlex.quote(args.resume_checkpoint)
    payload['runtime_env']['env_vars']['HF_HUB_OFFLINE']='1'
    if args.operation=='plan':print(json.dumps(payload,indent=2));return
    python=ROOT/'.venv-router-train/bin/python';env=isolated_environment(ROOT,python)
    if Path(sys.prefix).resolve()!=python.parent.parent.resolve() or any(os.environ.get(k)!=env.get(k) for k in ['PYTHONHOME','PYTHONPATH','PYTHONNOUSERSITE']):
        os.execve(str(python),[str(python),str(ROOT/'amp/laya_jobs.py'),*sys.argv[1:]],env)
    from ray.job_submission import JobSubmissionClient
    token=os.environ.get('CDSW_APIV2_KEY') or os.environ.get('CML_API_KEY')
    if not token:raise RuntimeError('Run inside CAI with injected credentials')
    client=JobSubmissionClient(cluster_address(ROOT),headers={'Authorization':'Bearer '+token.strip()})
    if args.operation=='submit':
        if any(j.submission_id==args.submission_id for j in client.list_jobs()):raise ValueError('Choose a new submission ID')
        from smart_router.data.pilot_bundle import validate_bundle
        validate_bundle(ROOT/cfg['dataset'])
        if (ROOT/cfg['output_dir']/args.submission_id).exists():raise ValueError('Output directory already exists')
        print(client.submit_job(**payload))
        if args.wait:wait_for_job(client,args.submission_id,cfg.get("job_timeout_seconds",1800))
    elif args.operation=='status':print(client.get_job_status(args.submission_id))
    elif args.operation=='logs':print(client.get_job_logs(args.submission_id))
    else:print(client.stop_job(args.submission_id))


if __name__=='__main__':main()
