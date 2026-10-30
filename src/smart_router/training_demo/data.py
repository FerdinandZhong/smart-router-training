"""Freeze deterministic, disjoint GSM8K subsets for SFT and GRPO."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

REVISION = '3101c7d5072418e28b9008a6636bde82a006892c'
BASE = f'https://raw.githubusercontent.com/openai/grade-school-math/{REVISION}/'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def prepare(output):
    if output.exists():
        raise ValueError('Use a new output directory')
    assets = {}
    for name in ['grade_school_math/data/train.jsonl', 'grade_school_math/data/test.jsonl', 'LICENSE']:
        with urllib.request.urlopen(BASE + name, timeout=60) as response:
            assets[name] = response.read()
    def rows(name):
        unique = {}
        for line in assets[f'grade_school_math/data/{name}.jsonl'].decode().splitlines():
            row = json.loads(line)
            key = sha(' '.join(row['question'].casefold().split()).encode())
            unique.setdefault(key, row)
        return sorted(unique.items())
    train, test = rows('train'), rows('test')
    if set(k for k,_ in train) & set(k for k,_ in test):
        raise ValueError('Train/test question overlap')
    selections = {'sft':train[:1024], 'grpo':train[1024:1536], 'validation':train[1536:1664], 'test':test[:256]}
    output.mkdir(parents=True)
    counts = {}
    for split, selection in selections.items():
        records = []
        for key, row in selection:
            if '####' not in row['answer']:
                raise ValueError('Missing final answer marker')
            answer = row['answer'].rsplit('####',1)[1].strip()
            prompt = [{'role':'user','content':row['question']+'\nEnd with: #### <numeric answer>'}]
            record = {'id':key,'prompt':prompt,'answer':answer}
            if split == 'sft':
                record['completion'] = [{'role':'assistant','content':row['answer']}]
            records.append(record)
        (output/f'{split}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
        counts[split] = len(records)
    (output/'LICENSE').write_bytes(assets['LICENSE'])
    manifest = {'source':'openai/grade-school-math','revision':REVISION,'license':'MIT',
                'counts':counts,'selection':'normalized-question SHA256 order; disjoint slices',
                'source_sha256':{k:sha(v) for k,v in assets.items()},
                'files':{p.name:sha(p.read_bytes()) for p in output.iterdir()},
                'limitations':['Demo subsets, not a benchmark claim','Pretraining contamination unknown','Test must not select checkpoints']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
