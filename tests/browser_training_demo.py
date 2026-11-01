"""Exercise independent job drafts without submitting any Ray jobs."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8096')
    page.evaluate('localStorage.clear()')
    page.reload()
    page.locator('#newJob').click()
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
    assert not errors,errors
    browser.close()
    print('PASS: form modes, saved drafts, reload, filters, duplication, export, disabled launch, three responsive widths.')
