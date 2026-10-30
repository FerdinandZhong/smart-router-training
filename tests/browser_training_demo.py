from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch()
 page=b.new_page()
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 for w in [1440,980,390]:
  page.set_viewport_size({'width':w,'height':1000})
  page.goto('http://127.0.0.1:8096')
  page.wait_for_function("document.getElementById('stage').textContent === 'Dataset prepared'")
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),w
  assert page.locator('#gpu').inner_text()=='—'
  page.locator('#refresh').click()
  page.screenshot(path=f'/tmp/training-demo-{w}.png',full_page=True)
 assert not errors,errors
 b.close()
 print('Browser passed at 1440, 980 and 390 pixels; no JS errors or horizontal overflow.')
