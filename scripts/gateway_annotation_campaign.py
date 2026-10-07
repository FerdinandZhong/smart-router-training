"""Finish staged gateway candidates, independently judge, and freeze training data."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
from smart_router.annotation.gateway_campaign import GatewayRunner,model_spec,PRICES,Budget
from smart_router.annotation.pipeline import Runner,CANDIDATE_SYSTEM,atomic_json,digest,prepare,plan,read_jsonl,run,run_lock
from smart_router.schemas import canonical_json,model_input
from smart_router.annotation.checks import check_action
from smart_router.data.pilot_bundle import validate_bundle
from export_smoke_training_data import export
SOURCE=ROOT/'data/prepared/gateway-pilot-v1';OUT=ROOT/'runs/gateway-pilot-v1';CONFIG=ROOT/'configs/annotation/gateway-pilot-v1.json'


def freeze_config():
 mapping=json.loads((SOURCE/'manifest.json').read_text())['source']['candidate_mapping']
 models=[model_spec(cls,name,'~/tokens/litellm_key_applied_ai') for cls,name in mapping.items()]
 judge=model_spec('JUDGE','gpt-5.6-terra','~/tokens/litellm_key_applied_ai');judge.pop('class_id');judge['max_output_tokens']=1024
 cfg={'config_version':'1.0','label_scope':'local_step','records':'../../data/prepared/gateway-pilot-v1/records.jsonl','task':'../../data/prepared/gateway-pilot-v1/task.json','contracts':'../../data/prepared/gateway-pilot-v1/contracts.jsonl','candidates':models,'judges':[judge],'candidate_system':CANDIDATE_SYSTEM,'trials_per_candidate':1,'min_valid_trials':1,'max_attempts_per_call':3,'judge_confidence_threshold':.8,'max_calls':18000,'max_reserved_output_tokens':36_864_000,'cost_policy':{'estimated_ceiling_usd':150,'input_output_rates_per_million':PRICES,'source':'user_gateway_screenshot','cache_discount_assumed':False}}
 # JSON round trip normalizes tuple pricing for frozen comparisons.
 cfg=json.loads(json.dumps(cfg))
 if CONFIG.exists() and json.loads(CONFIG.read_text())!=cfg:raise ValueError('Frozen campaign configuration changed')
 CONFIG.parent.mkdir(parents=True,exist_ok=True);CONFIG.write_text(json.dumps(cfg,indent=2)+'\n')
 frozen=prepare(CONFIG)
 if digest(json.loads((SOURCE/'manifest.json').read_text()))!=json.loads((OUT/'candidate-source.json').read_text())['dataset_manifest']:raise ValueError('Candidate source changed')
 return frozen


def judge_stage(frozen,limit=None):
 with run_lock(OUT):
  identity=digest(frozen)
  if (OUT/'run.json').exists():
   if json.loads((OUT/'run.json').read_text())['run_hash']!=identity:raise ValueError('Run identity changed')
  else:
   atomic_json(OUT/'inputs.json',frozen);atomic_json(OUT/'run.json',{'run_hash':identity,'pipeline_version':'local-step-v1','plan':plan(frozen),'candidate_receipts_reused':True})
  gateway=GatewayRunner(OUT,150,30,True)
  runner=Runner(frozen,OUT);runner.invoke=gateway.invoke
  # Candidates must be present. Judging may never silently run an expensive candidate.
  jobs=[]
  for record in frozen['records']:
   for model in frozen['config']['candidates']:
    context={'role':'candidate','example_id':record['example_id'],'candidate':model['id'],'trial':0}
    from smart_router.annotation.backends import request_body
    body=request_body(model,frozen['prompts']['candidate'],canonical_json(model_input(record)))
    key=digest({'pipeline_version':'local-step-v1','model':model,'body':body,'context':context})
    if not (OUT/'calls'/(key+'.json')).exists():raise ValueError('Candidate phase not complete')
    jobs.append((record,model))
  selected=jobs[:limit] if limit else jobs
  pool=ThreadPoolExecutor(max_workers=6)
  try:
   futures=[pool.submit(runner.trial,record,model,0) for record,model in selected]
   counts=Counter()
   for i,f in enumerate(as_completed(futures),1):
    verdict=f.result();counts[str(verdict['verdict'])]+=1
    if i%25==0 or i==len(selected):print(json.dumps({'phase':'judge','completed':i,'verdicts':dict(counts),'estimated_committed_usd':gateway.budget.committed()}),flush=True)
  finally:gateway.stop.set();pool.shutdown(wait=True,cancel_futures=True)


def finalize(frozen):
 # The normal annotation pipeline assembles identical blinded judgments from cached calls.
 # Refuse fresh calls during finalization: missing receipts stay explicit errors.
 from unittest.mock import patch
 with patch('smart_router.annotation.backends.call',side_effect=AssertionError('No network in finalization')):
  report=run(frozen,OUT,live=True)
 destination=ROOT/'data/pilot/gateway-pilot-v1'
 if destination.exists():
  manifest=validate_bundle(destination)
 else:
  manifest=export(SOURCE,[OUT/'silver_labels.jsonl'],destination,dataset_id='gateway-pilot-v1',purpose='pilot_training')
  validate_bundle(destination)
 # Raw outputs retain every judgment; the bundle carries the annotation receipt hashes.
 results=[json.loads(p.read_text()) for p in (OUT/'calls').glob('*.json') if '.attempt-' not in p.name]
 costs=Counter()
 for result in results:
  if not result.get('fallback_call'):costs[result['requested_model']]+=result.get('estimated_cost_usd',0)
 summary={'states':1000,'splits':manifest['splits'],'class_support':manifest['class_support'],'judge':sorted({r.get('fallback_model',r['requested_model']) for r in results if r.get('context',{}).get('role')=='judge' and r.get('status')=='ok'}),'annotation_report':report,'candidate_mapping':manifest['source']['candidate_mapping'],'current_receipt_cost_estimates_usd':dict(costs),'conservative_estimated_campaign_spend_usd':Budget(OUT/'cost-ledger.jsonl',150).committed(),'artifact':str(destination),'runtime_replayed':False,'calibrated':False}
 atomic_json(OUT/'campaign-summary.json',summary);print(json.dumps(summary,indent=2),flush=True)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['plan','all','judge','finalize']);p.add_argument('--judge-limit',type=int);a=p.parse_args()
 frozen=freeze_config()
 if a.operation=='plan':print(json.dumps(plan(frozen),indent=2));return
 if a.operation=='all':
  atomic_json(OUT/'campaign-state.json',{'status':'running','pid':os.getpid(),'phase':'waiting_for_fast'})
  # A prior live FAST process may still be finishing. Never overlap phases sharing the same ledger.
  while (OUT/'run.lock').exists():
   try:os.kill(int((OUT/'run.lock').read_text().strip()),0)
   except ProcessLookupError:
    (OUT/'run.lock').unlink();continue
   except (ValueError,PermissionError):pass
   print('Waiting for the existing candidate phase lock',flush=True);time.sleep(30)
  for cls in ['FAST','GENERAL','REASONING']:
   atomic_json(OUT/'campaign-state.json',{'status':'running','pid':os.getpid(),'phase':cls})
   subprocess.run([sys.executable,str(ROOT/'scripts/gateway_candidate_stage.py'),'--class-id',cls,'--retry-errors'],check=True)
 if a.operation in ['all','judge']:
  atomic_json(OUT/'campaign-state.json',{'status':'running','pid':os.getpid(),'phase':'judge'})
  judge_stage(frozen,a.judge_limit)
 if a.operation=='finalize' or a.operation=='all':
  finalize(frozen)
  atomic_json(OUT/'campaign-state.json',{'status':'completed','pid':os.getpid(),'phase':'exported'})
if __name__=='__main__':
 try:main()
 except Exception as exc:
  atomic_json(OUT/'campaign-state.json',{'status':'failed','pid':os.getpid(),'error_type':type(exc).__name__})
  raise
