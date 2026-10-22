"""Inline ad regressions with a deterministic AdSense SDK substitute.

No requests reach Google and no live ad impressions/clicks are generated.
The test checks our placement/loading behavior, not AdSense serving approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from lxml import etree, html
from playwright.sync_api import sync_playwright

from listing import ROOT, REVIEW, ORIGIN, SVG, cursor, fixture, ids, wait_state

SDK_URL = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8621160875847917'
SDK = r"""
window.__adPushes = window.__adPushes || [];
const waiting = window.adsbygoogle || [];
window.adsbygoogle = {loaded:true,push() {
  const unit=document.querySelector('ins.adsbygoogle:not([data-adsbygoogle-status])');
  if(!unit) throw new Error('An ad was requested without a new unit');
  unit.setAttribute('data-adsbygoogle-status','done');
  unit.setAttribute('data-ad-status','filled');
  window.__adPushes.push(unit.closest('.feed-ad')?.dataset.afterPost || 'sidebar');
}};
for(const request of waiting) window.adsbygoogle.push(request);
"""


def document(preview, count, *, next_cursor=None, sdk=False, serialized_css=False):
    tree = html.fromstring(fixture(preview, 1, count, next_cursor))
    grid = tree.xpath('.//*[@class="post-grid"]')[0]
    assert grid.get('data-ad-client') == 'ca-pub-8621160875847917', 'Build the current preview first'
    assert grid.get('data-ad-slot') == '7800800754'
    if sdk:
        etree.SubElement(tree.find('head'), 'script', src=SDK_URL, **{'async': 'async'})
    if serialized_css:
        for style in tree.xpath('.//style'):
            style.text = ''.join(f'&#{ord(c)};' if ord(c) > 127 else c for c in style.text or '')
    return '<!doctype html>\n' + etree.tostring(tree, method='html', encoding='unicode')


def run_case(browser, preview, name, *, width=390, initial=24, chain=False,
             sdk=False, blocked=False, observer=True, serialized_css=False):
    context = browser.new_context(viewport={'width': width, 'height': 800}, reduced_motion='reduce')
    if not observer:
        context.add_init_script('delete window.IntersectionObserver;')
    page = context.new_page()
    page_errors, sdk_requests, listing_requests = [], [], []
    page.on('pageerror', lambda error: page_errors.append(str(error)))
    markup = document(preview, initial, next_cursor=cursor(initial) if chain else None,
                      sdk=sdk, serialized_css=serialized_css)

    def handle(route):
        url = route.request.url
        parsed = urlsplit(url)
        if url == ORIGIN + '/':
            route.fulfill(status=200, content_type='text/html', body=markup)
        elif parsed.hostname == 'pagead2.googlesyndication.com':
            sdk_requests.append(url)
            if blocked:
                route.abort('blockedbyclient')
            else:
                route.fulfill(status=200, content_type='application/javascript', headers={'Access-Control-Allow-Origin':'*'}, body=SDK)
        elif parsed.path.startswith('/search/label/'):
            query = parse_qs(parsed.query)
            offset = int(query['updated-max'][0].removeprefix('native-'))
            remaining = int(query['max-results'][0])
            count = min(7, remaining)
            listing_requests.append((offset, remaining))
            route.fulfill(status=200, content_type='text/html', body=fixture(preview, offset+1, count, cursor(offset+count)))
        elif parsed.path.startswith('/feeds/'):
            route.fulfill(status=200, content_type='application/json', body='{"feed":{"entry":[]}}')
        elif route.request.resource_type == 'image':
            route.fulfill(status=200, content_type='image/svg+xml', body=SVG)
        elif parsed.path.endswith('theme.css'):
            route.fulfill(status=200, content_type='text/css', body=(ROOT/'assets/theme.css').read_bytes())
        elif parsed.path.endswith('theme.js'):
            route.fulfill(status=200, content_type='application/javascript', body=(ROOT/'assets/theme.js').read_bytes())
        else:
            route.abort()

    context.route('**/*', handle)
    try:
        page.goto(ORIGIN+'/', wait_until='load')
        wait_state(page, 'ready')
        count = 24 if chain else initial
        assert ids(page) == list(range(1, count+1)), ids(page)
        expected = [n for n in (6,12,18) if count > n]
        positions = page.locator('.post-grid > .feed-ad').evaluate_all('nodes=>nodes.map(n=>({after:Number(n.dataset.afterPost),previous:Number(n.previousElementSibling.dataset.fixtureId),next:Number(n.nextElementSibling.dataset.fixtureId),label:n.textContent}))')
        assert [row['after'] for row in positions] == expected, positions
        assert all(row['after'] == row['previous'] and row['next'] == row['after']+1 and '광고' in row['label'] for row in positions), positions
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
        if chain:
            assert listing_requests == [(5,19),(12,12),(19,5)], listing_requests
            next_query = parse_qs(urlsplit(page.locator('.rel-older').get_attribute('href')).query)
            assert next_query['updated-max'] == ['native-24']
            assert next_query['max-results'] == ['24']

        if serialized_css:
            page.locator('#site-menu > summary').click()
            group = page.locator('.menu-group').first
            summary = group.locator('summary')
            group.evaluate('node=>node.open=true')
            assert summary.evaluate('node=>getComputedStyle(node,"::after").content') == '"−"'
            summary.click()
            assert summary.evaluate('node=>getComputedStyle(node,"::after").content') == '"+"'
            summary.click()
            assert summary.evaluate('node=>getComputedStyle(node,"::after").content') == '"−"'
            page.locator('.menu-close').click()

        if expected and observer:
            assert page.locator('.feed-ad ins').count() == 0, 'Offscreen ads were initialized eagerly'
            if not sdk:
                assert len(sdk_requests) == 0
            for after in expected:
                unit = page.locator(f'.feed-ad[data-after-post="{after}"]')
                if blocked:
                    if after != expected[0]:
                        break
                unit.evaluate('node=>node.scrollIntoView({behavior:"instant",block:"center"})')
                if blocked:
                    page.wait_for_function('Array.from(document.querySelectorAll(".feed-ad")).every(n=>n.hidden||getComputedStyle(n).display==="none")')
                else:
                    page.wait_for_function('(after)=>(window.__adPushes||[]).includes(String(after))', arg=after)
                    ad = unit.locator('ins.adsbygoogle')
                    assert ad.get_attribute('data-ad-client') == 'ca-pub-8621160875847917'
                    assert ad.get_attribute('data-ad-slot') == '7800800754'
                    assert ad.get_attribute('data-full-width-responsive') == 'false'
        elif expected:
            page.wait_for_function('(length)=>(window.__adPushes||[]).length===length', arg=len(expected))

        if expected and not blocked:
            page.evaluate('scrollTo({top:0,behavior:"instant"})')
            page.locator('.feed-ad').last.evaluate('node=>node.scrollIntoView({behavior:"instant"})')
            page.wait_for_timeout(100)
            pushes = page.evaluate('window.__adPushes||[]')
            assert pushes == [str(n) for n in expected], pushes
            assert len(sdk_requests) == 1, sdk_requests
            assert page.locator('script[src*="pagead/js/adsbygoogle.js"]').count() == 1
            page.locator('.feed-ad ins').first.evaluate('node=>node.dataset.adStatus="unfilled"')
            assert page.locator('.feed-ad').first.is_hidden(), 'Unfilled ad space was not collapsed'
        if not expected:
            assert not sdk_requests
        assert not page_errors, page_errors
        return {'case':name,'passed':True,'stories':count,'placements':expected,'sdkRequests':len(sdk_requests)}
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', type=Path, default=REVIEW/'previews-updated/home.html')
    parser.add_argument('--report', type=Path, default=REVIEW/'ads-regression.json')
    args = parser.parse_args()
    results=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        for name, options in [
            ('mobile-24-stories-three-lazy-ads', {'chain':True,'initial':5,'serialized_css':True}),
            ('desktop-24-stories-existing-sdk', {'width':1440,'sdk':True,'serialized_css':True}),
            ('six-stories-no-trailing-ad', {'initial':6}),
            ('seven-stories-one-ad', {'initial':7}),
            ('eighteen-stories-two-ads', {'initial':18}),
            ('observer-unavailable-fallback', {'observer':False}),
            ('blocked-sdk-keeps-stories-readable', {'blocked':True}),
        ]:
            results.append(run_case(browser,args.preview,name,**options))
        browser.close()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({'cases':len(results),'passed':len(results),'results':results,'scope':'AdSense SDK mocked; no live ad serving or impressions tested.'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(results),'passed':len(results),'report':str(args.report)}))


if __name__=='__main__':
    main()
