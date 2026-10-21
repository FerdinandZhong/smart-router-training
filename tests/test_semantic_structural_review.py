"""Structural relevance must not imply complete context or physical verification."""
from copy import deepcopy
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from smart_router.semantic_structural_review import evidence_input, validate, run

class StructuralReviewTests(unittest.TestCase):
    def setUp(self):
        self.units={
            'a':{'unit_id':'a','kind':'table','catalog_id':'c','name':'broadcast','definition':{},'dependencies':[]},
            'b':{'unit_id':'b','kind':'table','catalog_id':'c','name':'program','definition':{},'dependencies':[]},
            'f':{'unit_id':'f','kind':'field','catalog_id':'c','parent_id':'b','name':'status','definition':{'description':'x'*200+' extinct means disappeared'},'dependencies':['b']},
            'g':{'unit_id':'g','kind':'field','catalog_id':'c','parent_id':'a','name':'program_id','definition':{},'dependencies':['a']},
            'r':{'unit_id':'r','kind':'relationship','catalog_id':'c','definition':{'from':'broadcast','to':'program'},'dependencies':['g','f']}}
        packet={'input':{'question':'programs','confirmed_history':[]},'supervision_only':{'sql':'LEAK_SENTINEL'}}
        self.store=SimpleNamespace(units=self.units,record=lambda k:{'packet':packet,'review':{'candidate_judgments':[{'unit_id':'a'}]},'rankings':{'dense':['a']}})
        self.evidence,self.coverage=evidence_input(self.store,'k',{'seed_tables':1,'max_tables':8,'metadata_bytes':10000})
        self.result={'summary':'fixture','table_judgments':[{'unit_id':t['unit_id'],'label':1,'reason':'relevant','evidence_ids':[t['unit_id']]} for t in self.evidence['tables']], 'context_status':'needs_metadata','context_sets':[],'clarification_options':[],'missing_evidence':['definition unclear']}
    def test_evidence_expands_without_sql_and_preserves_full_definition(self):
        self.assertEqual(self.coverage['added_table_ids'],['b'])
        self.assertNotIn('LEAK_SENTINEL',str(self.evidence))
        self.assertIn('extinct means disappeared',str(self.evidence))
        self.assertEqual(len(self.evidence['relationships']),1)
    def test_relevance_without_complete_context_is_valid(self):
        validate(self.result,self.evidence,self.units)
        self.result['table_judgments'][0]['label']=None
        validate(self.result,self.evidence,self.units)
    def test_unseen_evidence_and_incomplete_context_fail(self):
        bad=deepcopy(self.result);bad['table_judgments'][0]['evidence_ids']=['invented']
        with self.assertRaises(ValueError):validate(bad,self.evidence,self.units)
        bad=deepcopy(self.result);bad.update(context_status='sufficient_within_evidence',missing_evidence=[],context_sets=[['a','b','r']])
        with self.assertRaisesRegex(ValueError,'dependency'):validate(bad,self.evidence,self.units)
        bad['context_sets']=[['a','b','f','g','r']]
        validate(bad,self.evidence,self.units)
    def test_budget_omits_whole_units_without_truncating(self):
        e,c=evidence_input(self.store,'k',{'seed_tables':1,'max_tables':1,'metadata_bytes':10000})
        self.assertEqual([t['unit_id'] for t in e['tables']],['a'])
        self.assertIn('b',c['omitted_planned_tables']);self.assertFalse(c['descriptions_clipped'])

    def test_run_reuses_receipts_and_keeps_physical_checks_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            self.store.pilot=Path(td)/'pilot';self.store.pilot.mkdir()
            (self.store.pilot/'manifest.json').write_text('{}')
            config={'model':'fixture','protocol':'fixture','seed_tables':1,'max_tables':8,
                    'metadata_bytes':10000,'request_interval_seconds':0,'retry_seconds':0,
                    'api':'chat_completions','max_output_tokens':1000}
            output=Path(td)/'run'
            response={'text':json.dumps(self.result),'actual_model':'fixture'}
            with patch('smart_router.semantic_structural_review.call',return_value=response) as invoke:
                self.assertEqual(run(self.store,['k'],config,output)['reviewed'],1)
                self.assertEqual(run(self.store,['k'],config,output)['reviewed'],1)
                self.assertEqual(invoke.call_count,1)
            receipt=json.loads((output/'automated-reviews.jsonl').read_text())
            self.assertFalse(receipt['human_approved'])
            self.assertTrue(all(v is None for v in receipt['verification'].values()))
            self.assertNotIn('LEAK_SENTINEL',str(receipt))
