import copy
import json
from pathlib import Path
import pytest
from smart_router.training.laya_pilot import epoch_indices, load_config, macro_loss, selection_state, training_fingerprint

ROOT=Path(__file__).resolve().parents[1]

def test_epoch_coverage_and_masked_padding():
    batches=epoch_indices(630,2,2,42,1)
    assert len(batches)==158
    assert all(len(b)==4 for b in batches)
    real=[i for b in batches for i in b if i is not None]
    assert sorted(real)==list(range(630))
    assert sum(i is None for b in batches for i in b)==2
    assert batches==epoch_indices(630,2,2,42,1)
    assert batches!=epoch_indices(630,2,2,42,2)
    for rank in range(2):
        assert sum(i is not None for b in batches for i in b[rank*2:(rank+1)*2]) in [314,316]

def test_validation_selection_and_empty_class():
    assert macro_loss({'a':{'observed':2,'log_loss':.2},'b':{'observed':1,'log_loss':.8},'c':{'observed':0,'log_loss':None}})==.5
    assert selection_state(.5,2,.6,1,1)==(.5,2,0,True)
    assert selection_state(.5,3,.5,2,0)==(.5,2,1,False)
    with pytest.raises(ValueError):macro_loss({'a':{'observed':0,'log_loss':None}})

def test_resume_fingerprint_guards_data_and_recipe():
    cfg=load_config(ROOT/'configs/training/laya-pilot.json')
    original=training_fingerprint(cfg,{'classes':['a']},'data1')
    moved=copy.deepcopy(cfg);moved['output_dir']='elsewhere';moved['job_timeout_seconds']=5
    assert original==training_fingerprint(moved,{'classes':['a']},'data1')
    moved['max_len']=512
    assert original!=training_fingerprint(moved,{'classes':['a']},'data1')
    assert original!=training_fingerprint(cfg,{'classes':['b']},'data1')
    assert original!=training_fingerprint(cfg,{'classes':['a']},'data2')

def test_config_rejects_unpinned_and_invalid_optimizer(tmp_path):
    cfg=load_config(ROOT/'configs/training/laya-pilot.json')
    for key,value in [('model_revision','main'),('learning_rate',0),('warmup_fraction',1),('max_len',8193),('min_epochs',6)]:
        bad=cfg|{key:value};path=tmp_path/'bad.json';path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):load_config(path)
