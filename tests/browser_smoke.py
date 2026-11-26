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
                edition=json.loads((ROOT/'web/data/index.json').read_text())
                capture_day=max(edition['start'], min(edition['retrieved'][:10], edition['through']))
                frozen=__import__('datetime').datetime.fromisoformat(capture_day+'T17:00:00+00:00')
                page.clock.install(time=frozen)
                def api(route):
                    feed=parse_qs(urlparse(route.request.url).query)['feed'][0]
                    def varint(n):
                        values=[]
                        while n>=128:values.append((n&127)|128);n>>=7
                        return bytes(values+[n])
                    header=bytes([10,3])+b'2.0'+bytes([24])+varint(int(frozen.timestamp()))
                    route.fulfill(status=200,content_type='application/x-protobuf',headers={'X-CoolCode-Fetched-At':frozen.isoformat()},body=bytes([10])+varint(len(header))+header)
                page.route('https://coolcode-visitor-api.jeffdyer.workers.dev/api/**',api)
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
                page.wait_for_function("document.querySelector('#vehicle-status').textContent.includes('no vehicle positions')")
                page.locator('#auto-live').uncheck()
                assert not page.locator('#auto-live').is_checked()
                page.locator('#clear-saved').evaluate('(el)=>el.click()')
                assert page.evaluate("JSON.parse(localStorage.getItem('coolcode:halifaxnext:stops')).length") == 0
                page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
                assert not errors,errors
                # Exercise the direct search landing page in a fresh browser context.
                case_page = browser.new_page(viewport={'width': 390, 'height': 844})
                case_page.route('https://**/*', lambda route: route.abort())
                case_page.goto(f'http://127.0.0.1:{server.server_port}/halifaxnext/alderney-ferry.html')
                case_page.wait_for_function("() => {const q=s=>document.querySelector(s);return q('#stop-code').textContent.includes('1074') && q('#stop-title').textContent.includes('Alderney');}")
                assert case_page.locator('link[rel="canonical"]').get_attribute('href') == 'https://coolcode.ca/halifaxnext/alderney-ferry.html'
                assert case_page.locator('h1').inner_text() in case_page.title()
                assert case_page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                browser.close()
        finally:server.shutdown()
    print('Browser checks passed: schedule, ferries, persisted favourites, safe text, subpath and mobile layout')
if __name__=='__main__':main()
