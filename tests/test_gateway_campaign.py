import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from smart_router.annotation.gateway_campaign import Budget, GatewayRunner, usage_cost

class GatewayBudgetTests(unittest.TestCase):
 def test_reasoning_tokens_not_double_charged(self):
  self.assertEqual(usage_cost('gpt-5.6-sol',{'input_tokens':1000,'output_tokens':100,'output_tokens_details':{'reasoning_tokens':80}}),.006)
  self.assertIsNone(usage_cost('gpt-5.6-sol',{}))
 def test_reservations_survive_restart(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cost.jsonl';b=Budget(p,1);b.reserve('a',.8)
   with self.assertRaises(RuntimeError):Budget(p,1).reserve('b',.3)
   b.settle('a',.1);Budget(p,1).reserve('b',.3)
   self.assertAlmostEqual(Budget(p,1).committed(),.4)
 def test_resume_uses_receipt_without_network_or_extra_charge(self):
  with tempfile.TemporaryDirectory() as d:
   r=GatewayRunner(d,1);model={'model':'gpt-5.6-sol','api':'responses','max_output_tokens':100}
   with patch('smart_router.annotation.backends.call',return_value={'text':'ok','usage':{'input_tokens':10,'output_tokens':1}}) as call:
    first=r.invoke(model,'system','user',{'role':'candidate'})
    self.assertEqual(r.invoke(model,'system','user',{'role':'candidate'}),first)
    self.assertEqual(call.call_count,1)
   self.assertAlmostEqual(r.budget.committed(),.00006)

class GatewayFormatTests(unittest.TestCase):
 def test_only_explicit_json_object_formats_are_allowed(self):
  from smart_router.annotation.pipeline import resolve_model
  base={'id':'m','model':'m','api':'responses','base_url':'https://example.test','api_key_env':'TEST_KEY'}
  resolve_model(base|{'generation':{'text':{'format':{'type':'json_object'}}}})
  resolve_model(base|{'api':'chat_completions','generation':{'response_format':{'type':'json_object'}}})
  for generation in [{'text':{'format':{'type':'json_schema'}}},{'text':{'format':{'type':'json_object'},'extra':1}}]:
   with self.assertRaises(ValueError):resolve_model(base|{'generation':generation})

 def test_rate_limit_stops_new_requests(self):
  from smart_router.annotation.backends import CallError
  with tempfile.TemporaryDirectory() as d:
   runner=GatewayRunner(d,1)
   model={'model':'gpt-5.6-sol','api':'responses','max_output_tokens':100}
   with patch('smart_router.annotation.backends.call',side_effect=CallError('http_429')) as call:
    with self.assertRaises(RuntimeError):runner.invoke(model,'system','user',{'id':1})
    with self.assertRaises(RuntimeError):runner.invoke(model,'system','user',{'id':2})
    self.assertEqual(call.call_count,1)
