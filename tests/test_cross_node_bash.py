"""Local contract tests with a fake Kubernetes client; no cluster changes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'docs/customer-share/cross-node-nccl/setup_cross_node_gpu.sh'
FAKE='''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
a=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f:f.write(json.dumps(a)+'\\n')
if 'auth' in a:print('yes')
elif 'get' in a:
 i=a.index('get');resource=a[i+1]
 if resource=='pods':
  if '-l' in a:print(json.dumps({'items':[]}))
  else:print(json.dumps({'items':[{'metadata':{'name':n,'uid':n+'-uid','resourceVersion':'1','labels':{}},'spec':{'nodeName':'node-'+n,'containers':[{'name':'engine'},{'name':'istio-proxy'}]},'status':{'phase':'Running','podIP':'10.0.0.'+str(j)}} for j,n in enumerate(['pod-a','pod-b'],1)]}))
 elif resource=='envoyfilter' and '--ignore-not-found' in a:pass
 elif resource=='peerauthentication':
  policy=os.environ.get('POLICY','PERMISSIVE')
  items=[{'metadata':{'name':'default'},'spec':{'mtls':{'mode':'PERMISSIVE' if policy=='WORKLOAD_STRICT' else policy}}}]
  if policy=='WORKLOAD_STRICT':items.append({'metadata':{'name':'strict-worker'},'spec':{'selector':{'matchLabels':{'ray-collective-change':'chg123'}},'mtls':{'mode':'STRICT'}}})
  print(json.dumps({'items':items}))
 else:print(json.dumps({'items':[]}))
else:sys.exit('Unexpected mutation or exec')
'''
class BashReviewTests(unittest.TestCase):
 def invoke(self,*extra,policy="PERMISSIVE"):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);fake=root/'kubectl';fake.write_text(FAKE);fake.chmod(0o755)
   env={**os.environ,'PATH':directory+os.pathsep+os.environ['PATH'],'CALLS':str(root/'calls'),'POLICY':policy}
   args=['bash',str(SCRIPT),'--context','review-context','--namespace','review-ns','--pod0','pod-a','--pod1','pod-b','--change-id','chg123','--evidence',str(root/'evidence'),*extra]
   result=subprocess.run(args,env=env,text=True,capture_output=True)
   calls=[json.loads(x) for x in (root/'calls').read_text().splitlines()]
   manifest=root/'evidence/collective-filter.json'
   return result,calls,json.loads(manifest.read_text()) if manifest.exists() else None
 def test_default_is_read_only_and_scoped(self):
  result,calls,manifest=self.invoke()
  self.assertEqual(result.returncode,0,result.stderr)
  for call in calls:
   self.assertIn('--context',call);self.assertIn('review-context',call)
   self.assertIn('-n',call);self.assertIn('review-ns',call)
   self.assertFalse(any(v in call for v in ['patch','create','delete','apply','exec']))
  self.assertEqual(manifest['spec']['workloadSelector']['labels'],{'ray-collective-change':'chg123'})
  self.assertEqual(manifest['metadata']['namespace'],'review-ns')
  for patch in manifest['spec']['configPatches']:
   self.assertEqual(patch['match']['context'],'SIDECAR_INBOUND')
   self.assertEqual(patch['patch']['operation'],'REPLACE')
   ranges=[r['destination_port_range'] for r in patch['patch']['value']['filter_disabled']['or_match']['rules']]
   self.assertIn({'start':32768,'end':61000},ranges)
 def test_apply_requires_explicit_approval_flags(self):
  result,calls,_=self.invoke('--mode','apply')
  self.assertNotEqual(result.returncode,0)
  self.assertIn('requires',result.stderr)
  self.assertFalse(any('patch' in c or 'exec' in c or 'create' in c for c in calls))
 def test_matching_strict_workload_blocks_mutation(self):
  result,calls,_=self.invoke('--mode','apply','--maintenance-confirmed','--plaintext-approved',policy='WORKLOAD_STRICT')
  self.assertNotEqual(result.returncode,0)
  self.assertIn('matching explicit STRICT policy',result.stderr)
  for call in calls:
   if 'auth' not in call:
    self.assertFalse(any(v in call for v in ['patch','create','delete','apply','exec']))
 def test_help_and_shell_syntax(self):
  for name in ['setup_cross_node_gpu.sh','run_collective_probe.sh','rollback_cross_node_gpu.sh']:
   subprocess.run(['bash','-n',str(SCRIPT.with_name(name))],check=True)
  help_result=subprocess.run(['bash',str(SCRIPT),'--help'],capture_output=True,text=True)
  self.assertEqual(help_result.returncode,0)
  self.assertIn('Default mode: plan',help_result.stdout)

if __name__=='__main__':unittest.main()
