"""Masked objective, class identity and split-view contracts without model downloads."""
import copy
import sys
import types
import unittest
from unittest.mock import patch

import torch

from smart_router.models.laya import prepare_rows
from smart_router.training.laya_trial import masked_binary_loss,summarize


class Tokenizer:
    mask_token='[MASK]'
    def __call__(self,text,**kwargs):return {'input_ids':list(range(len(text)))}


def fake_sequence(tok,state,q,max_len,head_max_len,state_ids):
    return [101,102,103,104]+state_ids,[1,2]


class LayaTrialTests(unittest.TestCase):
    def test_unknown_has_zero_gradient_and_global_normalization(self):
        logits=torch.tensor([[0.,1.],[2.,0.],[0.,-1.]],requires_grad=True)
        target=torch.tensor([1.,0.,0.]);mask=torch.tensor([1.,0.,1.])
        total,count=masked_binary_loss(logits,target,mask)
        (total/count).backward()
        self.assertTrue(torch.equal(logits.grad[1],torch.zeros(2)))
        # Sum of DDP-averaged rank-scaled gradients equals global objective gradient.
        distributed=[]
        for indices in ([0,1],[2]):
            local=logits.detach()[indices].clone().requires_grad_()
            num,_=masked_binary_loss(local,target[indices],mask[indices]);(num*2/count).backward();distributed.append(local.grad/2)
        self.assertTrue(torch.allclose(torch.cat(distributed),logits.grad))

    def test_all_unknown_loss_is_finite_zero(self):
        logits=torch.randn(2,2,requires_grad=True)
        total,count=masked_binary_loss(logits,torch.zeros(2),torch.zeros(2))
        (total/count.clamp_min(1)).backward()
        self.assertEqual(total.item(),0);self.assertTrue(torch.equal(logits.grad,torch.zeros_like(logits)))

    def test_configured_classes_and_no_label_leakage(self):
        task={'task_id':'custom','schema_version':'1','kind':'independent_binary','classes':[{'id':f'c{i}','description':f'Class {i}'} for i in range(5)]}
        record={'example_id':'e','input':{'text':'x'*300},'targets':{c['id']:None for c in task['classes']},'observation_mask':{c['id']:0 for c in task['classes']},'label_evidence':{'future':'SECRET'}}
        fake=types.ModuleType('laya.common');fake.build_sequence=fake_sequence
        with patch.dict(sys.modules,{'laya':types.ModuleType('laya'),'laya.common':fake}):
            rows,audits=prepare_rows([record],task,Tokenizer(),128,64)
            changed=copy.deepcopy(record);changed['label_evidence']={'future':'OTHER'}
            other,_=prepare_rows([changed],task,Tokenizer(),128,64)
        self.assertEqual([r['class_id'] for r in rows],[f'c{i}' for i in range(5)])
        self.assertTrue(all(r['target'] is None and not r['observed'] for r in rows))
        self.assertEqual(rows,other);self.assertTrue(all(a['sequence_tokens']==128 for a in audits))
        self.assertTrue(all(a['omitted_state_tokens']>0 for a in audits))

    def test_metrics_exclude_unknown_and_include_prior(self):
        items=[{'class_id':'a','target':1.,'observed':1,'probability':.75},
               {'class_id':'a','target':None,'observed':0,'probability':.99},
               {'class_id':'b','target':0.,'observed':1,'probability':.25}]
        result=summarize(items,['a','b'],{'a':.5,'b':.5})
        self.assertEqual(result['a']['observed'],1);self.assertEqual(result['a']['unknown'],1)
        self.assertAlmostEqual(result['a']['brier'],.0625);self.assertAlmostEqual(result['a']['prior_brier'],.25)
