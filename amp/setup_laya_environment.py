#!/usr/bin/env python3
"""Extend the idle training environment once and cache the pinned Laya snapshot."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from amp.environment import isolated_environment


def main():
    if ROOT!=Path('/home/cdsw'):raise RuntimeError('Run setup in the remote CAI project')
    cfg=json.loads((ROOT/'configs/training/laya-first-trial.json').read_text())
    python=ROOT/'.venv-router-train/bin/python';env=isolated_environment(ROOT,python)
    state=ROOT/'.amp-state';state.mkdir(exist_ok=True)
    with (state/'environment.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        subprocess.run([str(python),'-m','pip','install',
            'ray[default,train]==2.58.0','torch==2.8.0','tensorboard==2.20.0',
            'transformers==4.57.6','safetensors==0.7.0','huggingface-hub==0.36.0','tokenizers==0.22.2'],env=env,check=True)
        subprocess.run([str(python),'-m','pip','install','--no-deps',
            'laya @ git+https://github.com/NandhaKishorM/laya.git@'+cfg['source_revision']],env=env,check=True)
        subprocess.run([str(python),'-m','pip','check'],env=env,check=True)
        (state/'laya-environment.txt').write_text(subprocess.check_output([str(python),'-m','pip','freeze'],env=env,text=True))
        code='''import hashlib,json
from pathlib import Path
from huggingface_hub import snapshot_download
from importlib.metadata import distribution
cfg=json.loads(Path('/home/cdsw/configs/training/laya-first-trial.json').read_text())
source=json.loads(distribution('laya').read_text('direct_url.json'))
assert source['vcs_info']['commit_id']==cfg['source_revision'],source
path=Path(snapshot_download(cfg['model_id'],revision=cfg['model_revision'],cache_dir='/home/cdsw/model-cache',allow_patterns=['model.safetensors','rl_agent_config.json','encoder/config.json','tokenizer/*']))
assert path.name==cfg['model_revision'],path
hashes={str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
Path('/home/cdsw/.amp-state/laya-model.json').write_text(json.dumps({'model_id':cfg['model_id'],'revision':cfg['model_revision'],'source_revision':cfg['source_revision'],'path':str(path),'files_sha256':hashes},indent=2))
print('LAYA_ENVIRONMENT_AND_SNAPSHOT_READY',path)
'''
        subprocess.run([str(python),'-c',code],env=env,check=True)


if __name__=='__main__':main()
