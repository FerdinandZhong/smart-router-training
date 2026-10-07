"""Run a resumable candidate phase before the judge configuration is finalized."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from smart_router.annotation.gateway_campaign import GatewayRunner,model_spec
from smart_router.annotation.pipeline import CANDIDATE_SYSTEM,atomic_json,digest,read_jsonl,run_lock
from smart_router.schemas import canonical_json,model_input

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--class-id',required=True);p.add_argument('--limit',type=int,default=1000);p.add_argument('--concurrency',type=int,default=6);p.add_argument('--budget-usd',type=float,default=150);p.add_argument('--requests-per-minute',type=int,default=30);p.add_argument('--retry-errors',action='store_true');p.add_argument('--api-key-file',default='~/tokens/litellm_key_applied_ai');a=p.parse_args()
 source=ROOT/'data/prepared/gateway-pilot-v1';output=ROOT/'runs/gateway-pilot-v1'
 manifest=json.loads((source/'manifest.json').read_text());mapping=manifest['source']['candidate_mapping']
 rows=read_jsonl(source/'records.jsonl');model=model_spec(a.class_id,mapping[a.class_id],a.api_key_file)
 identity={'dataset_manifest':digest(manifest),'mapping':mapping,'candidate_system':CANDIDATE_SYSTEM,'generation_policy':'json-low-reasoning-v1','prices_source':'user_gateway_screenshot','budget_usd':a.budget_usd}
 with run_lock(output):
  path=output/'candidate-source.json'
  if path.exists() and json.loads(path.read_text())!=identity:raise ValueError('Frozen source or budget changed')
  atomic_json(path,identity)
  runner=GatewayRunner(output,a.budget_usd,a.requests_per_minute,a.retry_errors)
  def work(record):
   ctx={'role':'candidate','example_id':record['example_id'],'candidate':model['id'],'trial':0}
   return runner.invoke(model,CANDIDATE_SYSTEM,canonical_json(model_input(record)),ctx)
  states=rows[:a.limit];counts=Counter()
  pool=ThreadPoolExecutor(max_workers=a.concurrency)
  try:
   futures=[pool.submit(work,r) for r in states]
   for i,f in enumerate(as_completed(futures),1):
    result=f.result();counts[result['status']]+=1
    if i%25==0 or i==len(states):print(json.dumps({'class':a.class_id,'completed':i,'statuses':dict(counts),'estimated_cost_committed_usd':runner.budget.committed()}),flush=True)
  finally:
   runner.stop.set();pool.shutdown(wait=True,cancel_futures=True)
  atomic_json(output/(a.class_id.lower()+'-phase.json'),{'class_id':a.class_id,'states':len(states),'statuses':dict(counts),'estimated_cost_committed_usd':runner.budget.committed()})
if __name__=='__main__':main()
