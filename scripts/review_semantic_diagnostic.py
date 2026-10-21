#!/usr/bin/env python3
"""Run the eleven-case structural diagnostic without changing earlier review artifacts."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from smart_router.semantic_review_ui import ReviewStore
from smart_router.semantic_structural_review import run
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--dry-run',action='store_true')
p.add_argument('--output',type=Path,default=ROOT/'data/semantic-research/structural-diagnostic-20261020-v2c')
a=p.parse_args()
audit=json.loads((ROOT/'docs/status/2026-10-20-semantic-deferral-audit.json').read_text())
keys=[c['record_id'] for c in audit['cases']]+[audit['approved_control']['record_id']]
store=ReviewStore(ROOT/'data/semantic-research/pilot-20261010-v3',ROOT/'data/semantic-research/review-work-20261010-v2',ROOT/'data/semantic-research/baselines-20261010-v3')
config=json.loads((ROOT/'configs/semantic_retrieval/structural-reviewer-v2.json').read_text())
status=run(store,keys,config,a.output,a.dry_run)
print(json.dumps(status),flush=True)

if not a.dry_run:
    from collections import Counter
    from smart_router.semantic_review_judge import atomic_json
    prior={c['record_id']:c for c in audit['cases']}
    rows=[]
    for line in (a.output/'automated-reviews.jsonl').read_text().splitlines():
        receipt=json.loads(line);key=receipt['record_id'];result=receipt.get('result',{})
        rows.append({'record_id':key,'question':store.packets[key]['input']['question'],
                     'old_disposition':prior.get(key,{}).get('original_disposition','approved'),
                     'new_context_status':result.get('context_status','failed'),
                     'relevance_counts':dict(Counter(str(j['label']) for j in result.get('table_judgments',[]))),
                     'error':receipt.get('error') if receipt['status']=='failed' else None})
    atomic_json(a.output/'comparison.json', {'status':status,'records':rows,
        'limits':'Purposive diagnostic; new relevance labels differ from old required-table labels. Not an accuracy estimate or training release.'})
