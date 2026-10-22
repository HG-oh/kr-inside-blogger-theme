"""Validate the new theme's XML contract and representative browser fixtures.

Fixtures contain synthetic posts. This is not a Blogger server renderer or a
live import test. The real new CSS and JavaScript run in Chromium; feed/image
responses are deterministic local test data. No network policy is bypassed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lxml import etree
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REVIEW = Path('/workspace/review/kr-inside-new-theme')
HOSTS = ['www.kr-inside.com', 'news.kr-inside.com', 'trip.kr-inside.com', 'item.kr-inside.com']
NS = {'b': 'http://www.google.com/2005/gml/b', 'h': 'http://www.w3.org/1999/xhtml'}
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#bac8b8"/><path d="M0 460 320 220 650 480 960 250V640H0Z" fill="#59796b"/><circle cx="740" cy="150" r="65" fill="#ebd6ac"/></svg>'
NATIVE_INCLUDES = {'all-head-content', 'comments', 'threadedComments', 'commentPicker',
                   'google-analytics',
                   'super.main', 'super.comments', 'super.commentPicker', 'super.threadedComments',
                   'postMetadataJSON', 'postMetadataJSONImage', 'postMetadataJSONPublisher',
                   'defaultAdUnit', 'commentForm', 'threadedCommentJs', 'threadedCommentForm'}


def normalized_url(value):
    return unquote(value).rstrip('/')


def validate_xml(path, inventory):
    text = path.read_text()
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    tree = etree.fromstring(path.read_bytes(), parser)
    assert tree.find('.//b:skin', NS) is not None, 'Blogger b:skin is required'
    assert tree.get('{%s}defaultwidgetversion' % NS['b']) == '2'
    assert tree.get('{%s}responsive' % NS['b']) == 'true'
    widgets = tree.findall('.//b:widget', NS)
    widget_ids = [node.get('id') for node in widgets]
    assert len(widget_ids) == len(set(widget_ids)), 'Duplicate widget IDs'
    sections = tree.findall('.//b:section', NS)
    section_ids = [node.get('id') for node in sections]
    assert len(section_ids) == len(set(section_ids)), 'Duplicate section IDs'
    for section in sections:
        assert section.get('id'), 'Section missing ID'
        for child in section:
            if isinstance(child.tag, str):
                assert child.tag in {'{%s}widget' % NS['b'], '{%s}comment' % NS['b']}, (
                    'Blogger section has non-widget child', section.get('id'), child.tag)
    types = [node.get('type') for node in widgets]
    assert types.count('Blog') == 1, 'Need exactly one native Blog widget'
    assert types.count('PopularPosts') >= 1, 'Need native PopularPosts widget'
    for widget in widgets:
        ids = [node.get('id') for node in widget.findall('b:includable', NS)]
        assert 'main' in ids, ('Widget missing main includable', widget.get('id'))
        assert len(ids) == len(set(ids)), ('Duplicate local includable', widget.get('id'))
    includes = set(tree.xpath('//b:include/@name', namespaces=NS))
    declared = set(tree.xpath('//b:includable/@id', namespaces=NS))
    unknown = sorted(includes - declared - NATIVE_INCLUDES)
    assert not unknown, ('Unresolved includable names', unknown)
    source_urls = inventory.get('urls') or [row['href'] for row in inventory['link_lists']['LinkList101']
                                           if not row['is_placeholder']]
    expected = {normalized_url(value) for value in source_urls}
    actual = {normalized_url(value) for value in tree.xpath('//h:a/@href', namespaces=NS)}
    assert len(expected) == 29
    assert expected <= actual, ('Lost original menu URLs', sorted(expected - actual))
    assert '{homeIcon}' not in text, 'Old runtime-only home macro remains'
    assert not re.search(r'(kr-inside-styles|typify-runtime|typify-plugins|jquery)', text, re.I)
    assert 'data:post.featuredImage' in text and 'resizeImage(' in text
    assert tree.xpath('//h:img[@expr:src]', namespaces={**NS, 'expr':'http://www.google.com/2005/gml/expr'}), 'Native image sources missing'
    assert not tree.xpath('//*[@onerror or @onload]'), 'Avoid inline JS event handlers'
    assert 'data:post.body' in text or '<data:post.body' in text, 'Post body must remain native'
    assert 'data:olderPageUrl' in text, 'Native pagination URL missing'
    assert 'application/ld+json' in text or 'all-head-content' in text
    css_payload = tree.find('.//b:skin', NS).text or ''
    runtime = tree.find('.//h:script[@id="kr-theme-runtime"]', NS)
    inline_assets = runtime is not None and not runtime.get('src')
    if inline_assets:
        assert css_payload == (ROOT / 'assets/theme.css').read_text(), 'Portable XML CSS differs from current asset'
        assert runtime.text == '\n//\n' + (ROOT / 'assets/theme.js').read_text() + '\n//\n', 'Portable XML JS differs from current asset'
    return {'xml': str(path), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'widgets': len(widgets), 'sections': len(sections),
            'originalUniqueMenuURLsPreserved': len(expected),
            'inlineAssetsMatchSourceExactly': inline_assets,
            'nativeIncludes': sorted(includes & NATIVE_INCLUDES)}


def feed(mode, host):
    entries = []
    for index in range(4):
        row = {'title': {'$t': f'테스트 최근 글 {index + 1}'},
               'link': [{'rel': 'alternate', 'type': 'text/html',
                         'href': f'https://{host}/2026/10/recent-{index}.html'}],
               'published': {'$t': f'2026-10-{20 - index:02d}T08:00:00+09:00'},
               'media$thumbnail': {'url': f'https://{host}/fixture-image-{index}.jpg'},
               'summary': {'$t': '테스트 요약'}}
        if mode == 'missing-images':
            row.pop('media$thumbnail')
        if mode == 'unsafe':
            row['title']['$t'] = '<img src=x onerror="window.__feedXSS=1">'
            if index == 0:
                row['link'][0]['href'] = 'javascript:window.__feedXSS=1'
            if index == 1:
                row['media$thumbnail']['url'] = 'javascript:window.__feedXSS=1'
        entries.append(row)
    if mode == 'empty':
        entries = []
    return {'feed': {'entry': entries}}


def contrast(a, b):
    def luminance(value):
        channels = [float(x) / 255 for x in re.findall(r'[\d.]+', value)[:3]]
        channels = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in channels]
        return sum(x * weight for x, weight in zip(channels, [.2126, .7152, .0722]))
    l1, l2 = sorted([luminance(a), luminance(b)], reverse=True)
    return (l1 + .05) / (l2 + .05)


def run_case(browser, previews, *, host, view, width, javascript=True,
             scheme='light', theme='auto', motion='no-preference', feed_mode='success',
             storage_denied=False, screenshot=None, interactions=False):
    fixture = previews / (view + '.html')
    assert fixture.exists(), ('Preview fixture missing', fixture)
    context = browser.new_context(viewport={'width': width, 'height': 960},
                                  java_script_enabled=javascript, color_scheme=scheme,
                                  reduced_motion=motion)
    if javascript:
        if storage_denied:
            context.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('Storage blocked')}});")
        elif theme != 'auto':
            context.add_init_script("localStorage.setItem('kr-inside-theme'," + json.dumps(theme) + ");")
    page = context.new_page()
    errors, blocked, requests = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    expected_url = f'https://{host}/__preview/{view}'

    def route_request(route):
        url = route.request.url
        parsed = urlsplit(url)
        if url == expected_url:
            document = fixture.read_text()
            if theme != 'auto':
                document = re.sub(r'(<html\b[^>]*)(?=>)',
                                  lambda m: re.sub(r'\sdata-theme=["\'][^"\']*["\']', '', m.group()) + ' data-theme="' + theme + '"', document, count=1)
            route.fulfill(status=200, content_type='text/html', body=document)
        elif parsed.path.endswith('/assets/theme.css') or parsed.path.endswith('/theme.css'):
            requests.append('theme.css')
            route.fulfill(status=200, content_type='text/css', body=(ROOT / 'assets/theme.css').read_bytes())
        elif parsed.path.endswith('/assets/theme.js') or parsed.path.endswith('/theme.js'):
            requests.append('theme.js')
            route.fulfill(status=200, content_type='application/javascript', body=(ROOT / 'assets/theme.js').read_bytes())
        elif '/feeds/posts/default' in parsed.path:
            requests.append('feed')
            if feed_mode == 'failure':
                route.fulfill(status=503, content_type='application/json', body='{}')
            elif feed_mode == 'malformed':
                route.fulfill(status=200, content_type='application/json', body='not json')
            elif feed_mode == 'invalid-shape':
                route.fulfill(status=200, content_type='application/json', body='{"unexpected":true}')
            else:
                route.fulfill(status=200, content_type='application/json', body=json.dumps(feed(feed_mode, host)))
        elif route.request.resource_type == 'image':
            if feed_mode == 'broken-images' and 'fixture-image-' in url:
                route.fulfill(status=404, body='Image unavailable')
            else:
                route.fulfill(status=200, content_type='image/svg+xml', body=SVG)
        else:
            blocked.append(url)
            route.abort()

    context.route('**/*', route_request)
    try:
        page.goto(expected_url, wait_until='load', timeout=15000)
        if javascript:
            page.wait_for_timeout(120)
            state = page.locator('[data-recent-posts]')
            if state.count():
                if feed_mode in {'success', 'missing-images', 'broken-images'}:
                    page.locator('.recent-item').first.wait_for(timeout=4000)
                else:
                    page.wait_for_function("() => { const x=document.querySelector('[data-recent-posts]'); return !x || !['loading','pending'].includes(x.dataset.state || ''); }", timeout=4000)
        if theme != 'auto' and javascript:
            assert page.locator('html').get_attribute('data-theme') == theme, 'Saved explicit theme must be respected'
        assert not errors, errors
        dimensions = page.evaluate('''() => ({width:innerWidth, scroll:document.documentElement.scrollWidth,
            offenders:[...document.querySelectorAll('body *')].filter(n=>{
                const r=n.getBoundingClientRect(),s=getComputedStyle(n);
                return r.width && s.display!=='none' && s.visibility!=='hidden' && (r.right>innerWidth+2 || r.left < -2)
            }).slice(0,12).map(n=>({tag:n.tagName,cls:n.className,left:n.getBoundingClientRect().left,right:n.getBoundingClientRect().right}))})''')
        assert dimensions['scroll'] <= dimensions['width'] + 1, dimensions
        ranks = page.locator('.ranked-item').count()
        assert ranks == 5, ('Native popular posts missing', ranks)
        if view in {'home', 'index', 'search'}:
            assert page.locator('.story-card').count() >= 4
            image = page.locator('.story-image img').first
            assert image.count() and image.evaluate('(x)=>x.complete && x.naturalWidth>0'), 'Native lead image did not load'
            assert page.locator('.pagination a[href]').count() >= 1
        if view in {'post', 'page'}:
            assert page.locator('.post-body').is_visible()
            assert page.locator('h1.article-title').is_visible()
        for payload in page.locator('script[type="application/ld+json"]').all_text_contents():
            json.loads(payload)
        if view == 'empty':
            assert page.locator('.empty-state').is_visible()
        recent_count = page.locator('.recent-item').count()
        if javascript:
            if feed_mode in {'success', 'missing-images', 'broken-images'}:
                assert recent_count == 4, ('Recent posts missing', recent_count)
                if feed_mode == 'missing-images':
                    assert page.locator('.recent-image .image-placeholder').count() == 4
                if feed_mode == 'broken-images':
                    page.locator('.recent-list').scroll_into_view_if_needed()
                    page.wait_for_function("document.querySelectorAll('.recent-image .image-placeholder').length === 4", timeout=4000)
            elif feed_mode in {'empty', 'failure', 'malformed', 'invalid-shape'}:
                assert recent_count == 0
                assert page.locator('[data-recent-posts] a.feed-fallback').is_visible(), 'Feed error fallback must remain usable'
            elif feed_mode == 'unsafe':
                assert 0 < recent_count < 4, 'Unsafe post URL must be rejected'
                assert not page.evaluate('Boolean(window.__feedXSS)')
                assert not page.locator('[data-recent-posts] [onerror], [data-recent-posts] script').count()
                assert '<img src=x onerror=' in page.locator('.recent-title').first.text_content(), 'Feed titles should be literal text'
                for url in page.locator('[data-recent-posts] a').evaluate_all('(nodes)=>nodes.map(x=>x.getAttribute("href"))'):
                    assert not url.startswith(('javascript:', 'data:'))
            edition = host.split('.')[0]
            current = page.locator(f'.edition-nav a[data-edition="{edition}"]')
            assert current.count() and current.get_attribute('aria-current') == 'page', ('Edition not active', host)
        else:
            assert page.locator('[data-recent-posts] a.feed-fallback').is_visible()
        search = page.locator('.search-form')
        assert search.get_attribute('method').lower() == 'get'
        assert urlsplit(search.get_attribute('action')).path == '/search'
        assert search.locator('input[name="q"][type="search"]').count() == 1
        if interactions:
            toggle = page.locator('#site-menu > summary')
            toggle.click()
            assert page.locator('#site-menu').evaluate('(x)=>x.open')
            panel = page.locator('.menu-panel').bounding_box()
            assert panel and panel['x'] >= -1 and panel['x'] + panel['width'] <= width + 1, ('Open menu exceeds viewport', panel, width)
            group = page.locator('.menu-group > summary').first
            was_open = group.evaluate('(x)=>x.parentElement.open')
            group.click()
            assert group.evaluate('(x)=>x.parentElement.open') != was_open
            if javascript:
                page.keyboard.press('Escape')
                assert not page.locator('#site-menu').evaluate('(x)=>x.open')
                assert toggle.evaluate('(x)=>document.activeElement===x'), 'Escape must return focus'
                toggle.click()
                page.locator('.menu-close').click()
                assert not page.locator('#site-menu').evaluate('(x)=>x.open')
                theme_button = page.locator('[data-theme-toggle]')
                start = page.locator('html').get_attribute('data-theme') or 'auto'
                theme_button.click()
                changed = page.locator('html').get_attribute('data-theme') or 'auto'
                assert changed != start, 'Theme button did not change mode'
                assert theme_button.get_attribute('aria-label'), 'Theme button must have an accessible label'
                if not storage_denied:
                    assert page.evaluate("localStorage.getItem('kr-inside-theme')") == changed
            else:
                toggle.click()
                assert not page.locator('#site-menu').evaluate('(x)=>x.open')
        colors = page.evaluate('''() => { const s=getComputedStyle(document.body);return {text:s.color,background:s.backgroundColor,scheme:getComputedStyle(document.documentElement).colorScheme}; }''')
        if colors['background'] not in {'rgba(0, 0, 0, 0)', 'transparent'}:
            assert contrast(colors['text'], colors['background']) >= 4.5, ('Body text contrast', colors)
        if not interactions:
            assert colors['scheme'] == (scheme if theme == 'auto' else theme), ('Effective theme mismatch', colors, scheme, theme)
        if motion == 'reduce':
            assert page.locator('html').evaluate('(x)=>getComputedStyle(x).scrollBehavior') == 'auto'
        if screenshot:
            # Visit the page as a reader would before a full-page capture. Native
            # lazy images outside the initial viewport must not look broken in
            # review screenshots; the theme's loading attributes stay unchanged.
            page.evaluate('''async () => {
                for (let y=0; y<document.documentElement.scrollHeight; y+=700) {
                    window.scrollTo({top:y,behavior:'instant'});
                    await new Promise(resolve=>setTimeout(resolve,35));
                }
                await Promise.race([
                    Promise.all([...document.images].map(image=>image.decode().catch(()=>{}))),
                    new Promise(resolve=>setTimeout(resolve,1500))
                ]);
                window.scrollTo({top:0,behavior:'instant'});
            }''')
            page.screenshot(path=str(screenshot), full_page=True)
        return {'host': host, 'view': view, 'width': width, 'javascript': javascript,
                'scheme': scheme, 'theme': theme, 'motion': motion, 'feedMode': feed_mode,
                'storageDenied': storage_denied, 'nativePopularPosts': ranks,
                'recentPosts': recent_count, 'dimensions': dimensions,
                'errors': errors, 'blockedRequests': sorted(set(blocked)),
                'assetRequests': requests, 'bodyColors': colors}
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--previews', type=Path, default=REVIEW / 'previews')
    parser.add_argument('--report', type=Path, default=REVIEW / 'validation-results.json')
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    inventory = json.loads((ROOT / 'tests/original-menu-urls.json').read_text())
    report = {'status': 'running', 'scope': 'Synthetic representative HTML; no Blogger server import', 'cases': []}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        report['xml'] = validate_xml(args.xml, inventory)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            try:
                cases = []
                for host in HOSTS:
                    for width in ([390, 1440] if args.quick else [360, 390, 768, 1024, 1440]):
                        cases.append(dict(host=host, view='home', width=width, interactions=width in {390, 1440}))
                for javascript in [False]:
                    for width in [390, 1440]:
                        cases.append(dict(host=HOSTS[0], view='home', width=width, javascript=javascript, interactions=True))
                for view in ['index', 'post', 'page', 'search', 'empty']:
                    for width in [390, 1440]:
                        cases.append(dict(host=HOSTS[0], view=view, width=width))
                for scheme, theme, motion in [('dark','auto','no-preference'), ('dark','light','reduce'), ('light','dark','reduce')]:
                    for width in [390, 1440]:
                        cases.append(dict(host=HOSTS[1], view='home', width=width, scheme=scheme, theme=theme, motion=motion))
                for mode in ['empty', 'failure', 'malformed', 'invalid-shape', 'missing-images', 'broken-images', 'unsafe']:
                    cases.append(dict(host=HOSTS[2], view='home', width=390, feed_mode=mode))
                cases.append(dict(host=HOSTS[3], view='home', width=390, storage_denied=True, interactions=True))
                for index, case in enumerate(cases):
                    if case['host'] == HOSTS[0] and case['view'] in {'home','post'} and case['width'] in {390,1440} and case.get('javascript',True):
                        case['screenshot'] = args.report.parent / f'{case["view"]}-{case["width"]}.png'
                    result = run_case(browser, args.previews, **case)
                    report['cases'].append(result)
                    print(f'PASS {index+1}/{len(cases)} {case["host"]} {case["view"]} {case["width"]}px JS={case.get("javascript",True)} {case.get("feed_mode","success")}', flush=True)
            finally:
                browser.close()
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('PASS', len(report['cases']), 'browser cases; report:', args.report, flush=True)


if __name__ == '__main__':
    main()
