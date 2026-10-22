"""Browser regressions for native Blogger pagination and recent-body thumbnails.

Uses current local CSS/JS in the generated template preview. Listing responses
are deterministic native-card fixtures; thumbnail URL assertions use a saved
real Blogger feed. Image bytes are local SVG fixtures, not a claim that remote
image hosting was available during this test.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from lxml import etree, html
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REVIEW = Path('/workspace/review/kr-inside-new-theme')
ORIGIN = 'https://item.kr-inside.com'
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#97afa1"/></svg>'
CLASS = 'contains(concat(" ",normalize-space(@class)," ")," %s ")'


def first(tree, class_name):
    return tree.xpath('.//*[' + CLASS % class_name + ']')[0]


def fixture(preview, start, count, cursor, *, malicious=False):
    tree = html.fromstring(preview.read_text())
    grid = first(tree, 'post-grid')
    original = copy.deepcopy(first(grid, 'story-card'))
    grid.clear()
    grid.set('class', 'post-grid')
    grid.set('data-page-size', '24')
    for index in range(start, start + count):
        card = copy.deepcopy(original)
        card.set('data-fixture-id', str(index))
        card.set('class', 'story-card story-card--lead' if index == start else 'story-card')
        for node in card.xpath('.//a[' + CLASS % 'story-image' + '] | .//*[' + CLASS % 'story-title' + ']/a'):
            node.set('href', ORIGIN + f'/2026/10/story-{index}.html')
        title = first(card, 'story-title')[0]
        title.text = f'{index:02d}. 여러 줄로 나타나는 긴 한국어 상품 제목과 블로그 이야기를 읽습니다'
        grid.append(card)
    if malicious:
        # A normal Blogger document has scripts outside its story cards.
        script = etree.Element('script')
        script.text = 'window.__transportExecuted = true;'
        tree.append(script)
        remote = etree.Element('iframe', src=ORIGIN + '/transport-frame')
        tree.append(remote)
    nav = first(tree, 'pagination')
    for node in nav.xpath('.//a[' + CLASS % 'rel-older' + ']'):
        node.getparent().remove(node)
    if cursor is not None:
        node = etree.SubElement(nav, 'a', {'class': 'rel-older', 'href': cursor, 'rel': 'next'})
        node.text = '다음 페이지 →'
    runtime = tree.xpath('.//script[@id="kr-theme-runtime" or contains(@src,"/assets/theme.js")]')[0]
    runtime.attrib.pop('src', None)
    runtime.text = (ROOT / 'assets/theme.js').read_text()
    css = etree.Element('style')
    css.text = (ROOT / 'assets/theme.css').read_text()
    tree.find('head').append(css)
    return '<!doctype html>\n' + etree.tostring(tree, method='html', encoding='unicode')


def cursor(number):
    # Preserve an opaque Blogger cursor plus a label/query through every request.
    return ORIGIN + f'/search/label/%EC%83%81%ED%92%88?updated-max=native-{number}&max-results=7&q=good%20item'


def ids(page):
    return page.locator('.post-grid .story-card').evaluate_all('(nodes)=>nodes.map(x=>Number(x.dataset.fixtureId))')


def wait_state(page, state):
    page.wait_for_function('(state)=>document.querySelector(".post-grid").dataset.listState===state', arg=state, timeout=10000)


def listing_case(browser, preview, name, *, width=390, terminal=False, fail=False,
                 oversized=False, duplicate=False, foreign=False, javascript=True):
    context = browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript)
    page = context.new_page()
    initial_cursor = 'https://other.example/search?cursor=1' if foreign else cursor(5)
    initial = fixture(preview, 1, 5, initial_cursor)
    requests, page_errors, unexpected = [], [], []
    attempts = {}
    page.on('pageerror', lambda error: page_errors.append(str(error)))

    def route_request(route):
        url = route.request.url
        parsed = urlsplit(url)
        if url == ORIGIN + '/':
            route.fulfill(status=200, content_type='text/html', body=initial)
        elif parsed.path.startswith('/feeds/'):
            route.fulfill(status=200, content_type='application/json', body='{"feed":{"entry":[]}}')
        elif parsed.path.startswith('/search/label/'):
            query = parse_qs(parsed.query)
            offset = int(query['updated-max'][0].removeprefix('native-'))
            limit = int(query['max-results'][0])
            attempts[offset] = attempts.get(offset, 0) + 1
            requests.append({'offset': offset, 'limit': limit, 'q': query.get('q')})
            if fail and offset == 12 and attempts[offset] == 1:
                route.fulfill(status=503, content_type='text/html', body='temporarily unavailable')
                return
            if oversized:
                body = fixture(preview, 6, 20, cursor(25))
            elif duplicate:
                body = fixture(preview, 1, 5, cursor(5))
            elif terminal:
                body = fixture(preview, 6, 3, None, malicious=True)
            else:
                count = min(7, limit, 48 - offset)
                body = fixture(preview, offset + 1, count, cursor(offset + count) if offset + count < 48 else None,
                               malicious=route.request.resource_type != 'document')
            route.fulfill(status=200, content_type='text/html', body=body)
        elif route.request.resource_type == 'image':
            route.fulfill(status=200, content_type='image/svg+xml', body=SVG)
        elif parsed.path.endswith('theme.css'):
            route.fulfill(status=200, content_type='text/css', body=(ROOT / 'assets/theme.css').read_bytes())
        elif parsed.path.endswith('theme.js'):
            route.fulfill(status=200, content_type='application/javascript', body=(ROOT / 'assets/theme.js').read_bytes())
        else:
            unexpected.append(url)
            route.abort()

    context.route('**/*', route_request)
    try:
        page.goto(ORIGIN + '/', wait_until='load')
        if not javascript:
            assert ids(page) == list(range(1, 6))
            assert page.locator('.rel-older').is_visible()
            assert not requests
        elif oversized or duplicate or foreign:
            wait_state(page, 'ready' if foreign else 'error')
            assert ids(page) == list(range(1, 6)), (name, ids(page))
            # An unreachable or rejected source must not erase the native list.
            assert not foreign or not requests
            if not foreign:
                assert page.locator('.rel-older').is_visible()
        elif fail:
            wait_state(page, 'error')
            assert ids(page) == list(range(1, 13)), ids(page)
            next_url = page.locator('.rel-older').get_attribute('href')
            assert parse_qs(urlsplit(next_url).query)['updated-max'] == ['native-12']
            assert page.locator('.rel-older').is_visible()
            page.locator('.listing-retry').click()
            wait_state(page, 'ready')
            assert ids(page) == list(range(1, 25))
            assert [row['offset'] for row in requests] == [5, 12, 12, 19]
        else:
            wait_state(page, 'ready')
            if terminal:
                assert ids(page) == list(range(1, 9))
                assert page.locator('.rel-older:visible').count() == 0
            else:
                assert ids(page) == list(range(1, 25)), ids(page)
                assert [(row['offset'], row['limit']) for row in requests] == [(5, 19), (12, 12), (19, 5)], requests
                assert all(row['q'] == ['good item'] for row in requests)
                next_url = page.locator('.rel-older').get_attribute('href')
                next_query = parse_qs(urlsplit(next_url).query)
                assert next_query['updated-max'] == ['native-24'], next_url
                assert next_query['max-results'] == ['24'], next_url
                assert next_query['q'] == ['good item']
                assert page.locator('.story-card--lead').count() == 1
                assert page.locator('.story-card').nth(5).locator('img').get_attribute('loading') == 'lazy'
                positions = page.locator('.post-grid .story-card').evaluate_all('(nodes)=>nodes.map(x=>({x:x.getBoundingClientRect().x,y:x.getBoundingClientRect().y}))')
                assert len({round(row['x']) for row in positions}) == 1, positions
                assert all(positions[i]['y'] < positions[i+1]['y'] for i in range(23))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                # Exercise real navigation: the next document begins after the 24th item.
                page.locator('.rel-older').click()
                page.wait_for_url('**/search/label/**')
                wait_state(page, 'ready')
                assert ids(page) == list(range(25, 49)), ids(page)
                assert page.locator('.rel-older:visible').count() == 0
        assert not page_errors, page_errors
        assert not page.evaluate('Boolean(window.__transportExecuted)'), 'Fetched document scripts executed'
        assert not any('/transport-frame' in url for url in unexpected), unexpected
        return {'case': name, 'passed': True, 'cards': len(ids(page)), 'nativePageRequests': requests}
    finally:
        context.close()


def thumbnails_case(browser, preview, feed_path, *, bad_media=False):
    feed = json.loads(feed_path.read_text())
    entries = feed['feed']['entry'][:4]
    assert len(entries) == 4 and all('media$thumbnail' not in row for row in entries)
    expected = []
    for row in entries:
        content = html.fragment_fromstring(row['content']['$t'], create_parent='div')
        expected.append(content.xpath('.//img/@src')[0])
        if bad_media:
            row['media$thumbnail'] = {'url': ORIGIN + '/broken-media-thumbnail.jpg'}
    fixture_feed = {'feed': {'entry': entries}}
    context = browser.new_context(viewport={'width': 390, 'height': 900})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    requested_images = []
    page_html = fixture(preview, 1, 5, None)

    def route_request(route):
        parsed = urlsplit(route.request.url)
        if route.request.url == ORIGIN + '/':
            route.fulfill(status=200, content_type='text/html', body=page_html)
        elif parsed.path.startswith('/feeds/'):
            route.fulfill(status=200, content_type='application/json', body=json.dumps(fixture_feed))
        elif route.request.resource_type == 'image':
            requested_images.append(route.request.url)
            if parsed.path.endswith('/broken-media-thumbnail.jpg'):
                route.fulfill(status=404, body='Unavailable')
            else:
                route.fulfill(status=200, content_type='image/svg+xml', body=SVG)
        elif parsed.path.endswith('theme.css'):
            route.fulfill(status=200, content_type='text/css', body=(ROOT / 'assets/theme.css').read_bytes())
        elif parsed.path.endswith('theme.js'):
            route.fulfill(status=200, content_type='application/javascript', body=(ROOT / 'assets/theme.js').read_bytes())
        else:
            route.abort()

    context.route('**/*', route_request)
    try:
        page.goto(ORIGIN + '/', wait_until='load')
        page.locator('.recent-list').wait_for()
        page.locator('.recent-list').scroll_into_view_if_needed()
        page.wait_for_function('(expected)=>{const images=[...document.querySelectorAll(".recent-image img")];return images.length===4&&images.every((img,i)=>img.src===expected[i]&&img.complete&&img.naturalWidth>2);}', arg=expected, timeout=10000)
        assert all(url in requested_images for url in expected)
        assert page.locator('.recent-image .image-placeholder').count() == 0
        assert not errors, errors
        return {'case': 'real-feed-body-thumbnails' + ('-after-media-error' if bad_media else ''),
                'passed': True, 'imageURLs': expected, 'imageBytes': 'local deterministic SVG fixtures'}
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', type=Path, default=REVIEW / 'previews/home.html')
    parser.add_argument('--feed', type=Path, default=ROOT / 'tests/fixtures/recent-feed.json')
    parser.add_argument('--report', type=Path, default=REVIEW / 'listing-regression.json')
    args = parser.parse_args()
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                             args=['--no-sandbox', '--disable-dev-shm-usage'])
        for name, kwargs in [
            ('24-cards-mobile-next-page', {'width': 390}),
            ('24-cards-desktop-next-page', {'width': 1440}),
            ('terminal-eight-cards', {'terminal': True}),
            ('partial-failure-then-retry', {'fail': True}),
            ('overfull-page-preserves-native-posts', {'oversized': True}),
            ('duplicate-cursor-preserves-native-posts', {'duplicate': True}),
            ('foreign-cursor-never-fetched', {'foreign': True}),
            ('javascript-disabled-native-navigation', {'javascript': False}),
        ]:
            results.append(listing_case(browser, args.preview, name, **kwargs))
        results.append(thumbnails_case(browser, args.preview, args.feed))
        results.append(thumbnails_case(browser, args.preview, args.feed, bad_media=True))
        browser.close()
    report = {'cases': len(results), 'passed': len(results), 'results': results,
              'limits': 'Browser runs real current assets against deterministic native-page responses. Real saved feed determines thumbnail URL choices; remote image bytes are not tested.'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'passed': len(results), 'report': str(args.report)}))


if __name__ == '__main__':
    main()
