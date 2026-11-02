"""Exercise drafts and cluster states without submitting any Ray jobs. Port: TRAINING_DEMO_PORT (default 8096)."""
import os
from playwright.sync_api import sync_playwright
URL=f"http://127.0.0.1:{os.environ.get('TRAINING_DEMO_PORT','8096')}"
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL)
    page.evaluate('localStorage.clear()')
    page.reload()
    page.wait_for_function("document.getElementById('clusterNote').textContent.startsWith('Last check failed')")
    assert page.locator('#clusterChip').inner_text()=='Not connected' and page.locator('#smoke').is_disabled()
    assert 'Ray is not connected' in page.locator('#clusterNotice').inner_text() and page.locator('#gpuCount').inner_text()=='—'
    page.locator('#newJob').click()
    page.get_by_role('button',name='Mistral Small · GRPO + LoRA').click()
    assert page.locator('input[value=grpo]').is_checked() and page.locator('#quant').input_value()=='4bit'
    assert '12 GB' in page.locator('#summaryMem').inner_text() and 'unverified' in page.locator('#summaryMem').inner_text()
    page.locator('#workers').fill('3')
    assert 'plans 2 GPUs' in page.locator('#checks').inner_text()
    page.locator('#quant').select_option('none')
    assert 'Weights alone' in page.locator('#checks').inner_text()
    page.locator('#updates').select_option('full')
    assert not page.locator('#quantField').is_visible()
    page.get_by_role('button',name='Mistral Small · SFT + LoRA').click()
    assert page.locator('#targetColumn').input_value()=='completion' and not page.locator('#rewardField').is_visible()
    page.locator('#name').fill('Support assistant experiment')
    page.locator('#model').fill('example/base-checkpoint')
    page.locator('#dataset').fill('/shared/data/train.jsonl')
    assert page.get_by_role('button',name='Launch training job').is_disabled()
    page.locator('input[value=grpo]').check()
    assert page.locator('#rewardField').is_visible()
    assert page.locator('#targetColumn').input_value()=='answer'
    page.locator('#updates').select_option('full')
    assert not page.locator('#rankField').is_visible()
    page.locator('#updates').select_option('lora')
    for width in [1440,980,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
        page.screenshot(path=f'/tmp/training-job-form-{width}.png',full_page=True)
    page.get_by_role('button',name='Save draft',exact=True).click()
    assert page.locator('#detailName').inner_text()=='Support assistant experiment'
    assert 'GRPO' in page.locator('#detailConfig').inner_text()
    page.locator('#backDetail').click()
    page.reload()
    assert page.locator('#draftCount').inner_text()=='1'
    page.locator('#methodFilter').select_option('sft')
    assert 'No matching jobs' in page.locator('#jobTable').inner_text()
    page.locator('#methodFilter').select_option('grpo')
    page.get_by_role('button',name='Support assistant experiment',exact=True).click()
    page.locator('#duplicate').click()
    assert page.locator('#name').input_value().endswith(' · copy')
    assert page.locator('input[value=grpo]').is_checked()
    page.locator('input[value=sft]').check()
    assert page.locator('#targetColumn').input_value()=='completion'
    assert not page.locator('#rewardField').is_visible()
    page.locator('#backForm').click()
    for width in [1440,980,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
        page.screenshot(path=f'/tmp/training-jobs-{width}.png',full_page=True)
    page.get_by_role('button',name='Support assistant experiment',exact=True).click()
    with page.expect_download() as download:
        page.locator('#downloadDetail').click()
    assert download.value.suggested_filename=='training-job.json'
    assert 'Launch unavailable' in page.locator('#launchNote').inner_text()
    job={'submission_id':'smoke-1','kind':'cluster_smoke','created_at':'2026-11-01T00:00:00+00:00','config':{'config_path':'configs/training/cluster-smoke.json'},'status':'RUNNING','events':[]}
    cluster={'connected':True,'gpu_nodes_alive':2,'smoke_gate':{'passed':False,'run_id':None},'launch':{'cluster_smoke':None,'sft':'Cluster smoke has not passed','grpo':'Cluster smoke has not passed'}}
    page.route('**/api/cluster',lambda r:r.fulfill(json=cluster))
    page.route('**/api/jobs',lambda r:r.fulfill(json={'jobs':[job]}))
    page.route('**/api/jobs/smoke-1',lambda r:r.fulfill(json=job))
    page.route('**/api/jobs/smoke-1/logs',lambda r:r.fulfill(json={'logs':'NCCL ok'}))
    page.reload()
    page.wait_for_function("document.getElementById('clusterChip').textContent==='Connected'")
    assert page.locator('#smoke').is_enabled() and page.locator('#gpuCount').inner_text()=='2' and page.locator('#runCount').inner_text()=='1'
    assert page.get_by_role('button',name='smoke-1',exact=True).is_visible() and page.get_by_role('button',name='Support assistant experiment',exact=True).is_visible()
    page.get_by_role('button',name='smoke-1',exact=True).click()
    page.wait_for_function("document.getElementById('logsBody').textContent==='NCCL ok'")
    assert page.locator('#detailChip').inner_text()=='RUNNING' and page.locator('#stop').is_visible() and 'curves' in page.locator('#progressBody').inner_text()
    for width in [1440,980,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
    page.locator('#backDetail').click()
    page.unroute('**/api/jobs')
    page.route('**/api/jobs',lambda r:r.fulfill(status=502,json={'error':'down'}))
    page.wait_for_function("document.getElementById('runNote').textContent.startsWith('Job list unavailable · last updated')")
    assert page.locator('#runCount').inner_text()=='1'  # last good list kept, labelled stale
    page.reload()
    page.wait_for_function("document.getElementById('runNote').textContent==='Job list unavailable'")
    assert page.locator('#runCount').inner_text()=='—' and page.locator('#doneCount').inner_text()=='—'
    page.unroute('**/api/jobs')
    page.route('**/api/jobs',lambda r:r.fulfill(json={'jobs':[job]}))
    page.locator('#newJob').click()
    page.get_by_role('button',name='Mistral Small · SFT + LoRA').click()
    assert page.get_by_role('button',name='Launch training job').is_disabled() and 'has not passed' in page.locator('#launchNote').inner_text()
    cluster['launch']['sft']=None
    page.reload()
    page.wait_for_function("document.getElementById('clusterChip').textContent==='Connected'")
    page.locator('#newJob').click()
    page.get_by_role('button',name='Mistral Small · SFT + LoRA').click()
    page.wait_for_function("!document.getElementById('launch').disabled")
    assert not errors,errors
    browser.close()
    print('PASS: form modes, drafts, reload, filters, duplication, export, Not connected state, stubbed connected cluster and server job details, three responsive widths.')
