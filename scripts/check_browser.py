"""Optional real Chromium acceptance test and app preview capture (not Power BI exports)."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


root = Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
out = root/'docs/previews'
out.mkdir(exist_ok=True)
env = {**os.environ, 'MEDSUPPLY_ROOT':str(root)}
server = subprocess.Popen([sys.executable,'-m','uvicorn','medsupply.api:app','--host','127.0.0.1','--port','8765'],
                          env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=1)
            break
        except OSError:
            time.sleep(.1)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:8765')
        page.wait_for_selector('.investigate')
        assert page.locator('#rows tr').count()==15
        page.screenshot(path=str(out/'monitor.png'),full_page=True)
        page.locator('#search').fill('NIPRUSS')
        page.locator('#filters button').click()
        page.wait_for_function("document.querySelector('#rows').textContent.includes('NIPRUSS')")
        page.locator('.investigate').first.click()
        page.wait_for_function("document.querySelector('#answer-mode').textContent.includes('extractive')")
        assert 'Herstellung' in page.locator('#answer').inner_text()
        assert page.locator('#sources a').count()>=1
        page.screenshot(path=str(out/'evidence.png'),full_page=True)
        page.locator('[data-page=quality]').click()
        page.screenshot(path=str(out/'quality.png'),full_page=True)
        assert page.locator('#quarantine tr').count()==3
        page.set_viewport_size({'width':390,'height':844})
        page.locator('[data-page=monitor]').click()
        page.screenshot(path=str(out/'mobile.png'),full_page=True)
        overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        assert not overflow, 'Mobile layout has horizontal overflow'
        assert not errors
        browser.close()
        result={'desktop':'1440×1100','mobile':'390×844','javascript_errors':errors,
                'checks':['live API data loads','15-row pagination','NIPRUSS filter','product evidence and citation',
                          '3 quarantine rows','mobile no horizontal overflow']}
        (out/'browser-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
finally:
    server.terminate()
    server.wait(timeout=10)
