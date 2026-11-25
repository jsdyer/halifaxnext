"""Exercise the passenger app at a project subpath with deterministic public-feed fixtures."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os,json,shutil,tempfile,threading
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    screenshots=ROOT/'browser-checks';screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT/'dist',Path(temporary)/'halifaxnext')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temporary));threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH'))
                page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.clock.install(time=__import__('datetime').datetime(2026,11,25,17,0,tzinfo=__import__('datetime').timezone.utc))
                def api(route):
                    feed=parse_qs(urlparse(route.request.url).query)['feed'][0]
                    route.fulfill(status=200,content_type='application/json',body=json.dumps({'fetched_at':'2026-11-25T17:00:00Z','data':{'schema':1,'feed':feed,'timestamp':1795626000,'entities':[]}}))
                page.route('https://coolcode.ca/api/**',api)
                page.goto(f'http://127.0.0.1:{server.server_port}/halifaxnext/')
                page.wait_for_selector('.departure')
                assert 'Spring Garden' in page.locator('#stop-title').inner_text()
                assert page.locator('#route option').count()>81
                page.locator('#save').click();page.reload();page.wait_for_selector('.departure')
                assert 'Remove saved stop' in page.locator('#save').inner_text()
                page.locator('#search').fill('ferry')
                assert page.locator('#stop-results button').count()>0
                page.locator('#stop-results button').first.click();page.wait_for_selector('.departure')
                assert 'Ferry' in page.locator('#stop-title').inner_text()
                page.locator('#search').fill('<img src=x onerror=alert(1)>')
                assert page.locator('#stop-results img').count()==0
                assert '0 matching' in page.locator('#search-status').inner_text()
                assert 'positions' in page.locator('#vehicle-status').inner_text()
                page.locator('#clear-saved').evaluate('(el)=>el.click()')
                assert page.evaluate("JSON.parse(localStorage.getItem('coolcode:halifaxnext:stops')).length") == 0
                page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
                assert not errors,errors
                browser.close()
        finally:server.shutdown()
    print('Browser checks passed: schedule, ferries, persisted favourites, safe text, subpath and mobile layout')
if __name__=='__main__':main()
