"""Independent language/region navigation and native-page regressions.

Tag inventories below were read from the uploaded legacy menus, independently
of sites/*.json. Mixed translations, native cursors, feeds and image bytes are
deterministic fixtures. This runs the actual XML through the limited preview
renderer and the real shared assets in Chromium; it does not import Blogger.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, quote, unquote, urlsplit

from lxml import etree, html
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REVIEW = Path('/workspace/review/kr-inside-selectors/tests')
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#97afa1"/></svg>'
LABELS = {
    'www': {'ko': [], 'en': ['English', 'Domestic Travel', 'Financial Freedom'],
            'ja': ['日本語', '国内旅行', '経済的自由'],
            'vi': ['Tiếng Việt', 'Du lịch nội địa', 'Tự do tài chính'],
            'zh': ['中文', '國內旅行', '經濟自由']},
    'trip': {'ko': [], 'en': ['English', 'Domestic Travel', 'Financial Freedom', 'International Travel'],
             'ja': ['日本語', '国内旅行', '経済的自由', '海外旅行'],
             'vi': ['Tiếng Việt', 'Du lịch nội địa', 'Tự do tài chính', 'Du lịch quốc tế'],
             'zh': ['中文', '國內旅行', '國際旅行']},
}
REGIONS = {'all': '', 'seoul': '서울', 'busan': '부산', 'daejeon': '대전',
           'daegu': '대구', 'gwangju': '광주', 'incheon': '인천',
           'ulsan': '울산', 'gyeonggi': '경기'}
CLASS = 'contains(concat(" ",normalize-space(@class)," ")," %s ")'


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preview = load_module('kr_selector_preview', ROOT / 'tools/preview.py')
builder = load_module('kr_selector_builder', ROOT / 'tools/build.py')


def tag_path(label):
    return '/search/label/' + quote(label, safe='') + '?max-results=24'


def post(number, labels=()):
    row = copy.deepcopy(preview.sample_posts()[0])
    row.update(id=str(number), title=f'같은 기사 번역 fixture {number}',
               url=f'/2026/10/story-{number}.html',
               featuredImage=f'/fixture-image-{number}.jpg',
               labels=[{'name': label, 'url': '/search/label/' + quote(label, safe='')} for label in labels])
    return row


def mixed(site, count=5, start=1):
    keys = ('en', 'ja', 'vi', 'zh', 'ko')
    return [post(start + index, [LABELS[site][keys[index % 5]][0]] if keys[index % 5] != 'ko' else ['국내여행'])
            for index in range(count)]


def render(tree, posts, *, label='', cursor=None, article=False):
    context = preview.context_for('post' if article else 'index' if label else 'home')
    context['posts'] = posts
    context['olderPageUrl'] = cursor or ''
    context['newerPageUrl'] = ''
    context['blog']['searchLabel'] = label
    return '<!doctype html>\n' + preview.Renderer().node(tree, context)


def card_ids(page):
    return page.locator('.post-grid .story-title a').evaluate_all(
        '(nodes)=>nodes.map(node=>Number(node.href.match(/story-(\\d+)\\.html/)[1]))')


def html_card_ids(document):
    tree = html.fromstring(document)
    return [int(re.search(r'story-(\d+)\.html', href)[1]) for href in
            tree.xpath('.//*[' + CLASS % 'post-grid' + ']//*[' + CLASS % 'story-title' + ']/a/@href')]


def entry(number, labels):
    return {'title': {'$t': f'Recent fixture {number}'},
            'link': [{'rel': 'alternate', 'href': f'/2026/10/recent-{number}.html'}],
            'category': [{'term': label} for label in labels],
            'published': {'$t': '2026-10-21T09:00:00+09:00'},
            'content': {'$t': f'<p>본문 이미지</p><img src="/fixture-image-{number}.jpg">'}}


def recent_ids(page):
    return page.locator('.recent-title').evaluate_all(
        '(nodes)=>nodes.map(node=>Number(node.href.match(/recent-(\\d+)\\.html/)[1]))')


class FixtureBrowser:
    def __init__(self, browser, site, documents, feeds=None, *, width=390, javascript=True):
        self.origin = 'https://' + site + '.kr-inside.com'
        self.context = browser.new_context(viewport={'width': width, 'height': 900},
                                          java_script_enabled=javascript, reduced_motion='reduce')
        self.page = self.context.new_page()
        self.errors, self.documents, self.feeds, self.unexpected = [], [], [], []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

        def route_request(route):
            url = urlsplit(route.request.url)
            if url.hostname == site + '.kr-inside.com' and url.path.startswith('/feeds/'):
                self.feeds.append(route.request.url)
                body = feeds(url) if feeds else {'feed': {'entry': []}}
                if isinstance(body, int):
                    route.fulfill(status=body, body='fixture unavailable')
                else:
                    route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
            elif url.path.endswith('/theme.css'):
                route.fulfill(status=200, content_type='text/css', body=(ROOT / 'assets/theme.css').read_bytes())
            elif url.path.endswith('/theme.js'):
                route.fulfill(status=200, content_type='application/javascript', body=(ROOT / 'assets/theme.js').read_bytes())
            elif route.request.resource_type == 'image':
                route.fulfill(status=200, content_type='image/svg+xml', body=SVG)
            elif url.hostname == site + '.kr-inside.com' and url.path in ('/', '/search') or (
                    url.hostname == site + '.kr-inside.com' and (url.path.startswith('/search/label/') or url.path.endswith('.html'))):
                self.documents.append(route.request.url)
                body = documents(url)
                route.fulfill(status=200, content_type='text/html', body=body)
            elif any(domain in (url.hostname or '') for domain in ('googletagmanager.com', 'clarity.ms', 'googlesyndication.com')):
                route.fulfill(status=200, content_type='application/javascript' if route.request.resource_type == 'script' else 'text/html', body='')
            else:
                self.unexpected.append(route.request.url)
                route.abort()

        self.context.route('**/*', route_request)

    def goto(self, path='/'):
        self.page.goto(self.origin + path, wait_until='load')

    def ready(self):
        self.page.wait_for_function('document.querySelector(".post-grid").dataset.listState === "ready"', timeout=10000)

    def active(self):
        return self.page.locator('.filter-option[aria-current="page"]').get_attribute('data-filter-key')

    def close(self):
        assert not self.errors, self.errors
        assert not self.unexpected, self.unexpected
        self.context.close()


def static_case(trees, site):
    tree = trees[site]
    doc = html.fromstring(render(tree, mixed(site)))
    options = doc.xpath('.//a[' + CLASS % 'filter-option' + ']')
    assert [node.get('data-filter-key') for node in options] == list(LABELS[site])
    for node, (key, labels) in zip(options, LABELS[site].items()):
        assert json.loads(node.get('data-filter-labels')) == labels
        assert node.get('href') == ('/' if key == 'ko' else tag_path(labels[0]))
    assert html_card_ids(render(tree, mixed(site))) == [5], 'Default SSR must hide all four translations'
    assert html_card_ids(render(tree, [post(1, [])])) == [1], 'Unlabeled legacy Korean post must remain reachable'
    for key, labels in LABELS[site].items():
        if key == 'ko':
            continue
        for label in labels:
            assert html_card_ids(render(tree, [post(1, [label]), post(2, ['국내여행'])])) == [2], label
            assert html_card_ids(render(tree, [post(1, [label])], label=label)) == [1], label
    return {'case': site + '-native-korean-exclusion-and-existing-tag-inventory', 'passed': True}


def language_navigation_case(browser, trees, site, width):
    def documents(url):
        label = unquote(url.path.removeprefix('/search/label/')) if url.path.startswith('/search/label/') else ''
        selected = next((labels for labels in LABELS[site].values() if label in labels), [])
        return render(trees[site], [post(1, selected or ['국내여행'])], label=label)

    def feeds(url):
        label = unquote(url.path.split('/-/')[1]) if '/-/' in url.path else '국내여행'
        return {'feed': {'entry': [entry(number, [label]) for number in range(1, 5)]}}

    app = FixtureBrowser(browser, site, documents, feeds, width=width)
    try:
        app.goto()
        assert app.active() == 'ko'
        assert app.page.locator('.filter-option').count() == 5
        if width == 390:
            REVIEW.mkdir(parents=True, exist_ok=True)
            app.page.screenshot(path=str(REVIEW / (site + '-language-390.png')))
        for key, labels in LABELS[site].items():
            if key == 'ko':
                continue
            app.page.locator(f'.filter-option[data-filter-key="{key}"]').click()
            app.page.wait_for_url('**/search/label/**')
            app.ready()
            assert app.active() == key
            app.page.wait_for_function('document.querySelector("[data-recent-posts]").dataset.state === "ready"')
            assert unquote(urlsplit(app.feeds[-1]).path) == '/feeds/posts/default/-/' + labels[0]
            assert parse_qs(urlsplit(app.feeds[-1]).query)['max-results'] == ['4']
            assert recent_ids(app.page) == [1, 2, 3, 4]
            assert card_ids(app.page) == [1]
            app.page.screenshot()
            bounds = app.page.locator(f'.filter-option[data-filter-key="{key}"]').bounding_box()
            assert bounds['height'] >= 42 and bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1, bounds
            assert app.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        # A later home visit must default to Korean, regardless of past choices.
        app.page.locator('.filter-option[data-filter-key="ko"]').click()
        app.page.wait_for_url(app.origin + '/')
        app.ready()
        assert app.active() == 'ko'
        app.page.wait_for_function('document.querySelector("[data-recent-posts]").dataset.state === "ready"')
        assert '/-/' not in urlsplit(app.feeds[-1]).path
        return {'case': f'{site}-all-five-native-language-links-{width}', 'passed': True}
    finally:
        app.close()


def region_case(browser, trees, width):
    def documents(url):
        label = unquote(url.path.removeprefix('/search/label/')) if url.path.startswith('/search/label/') else ''
        return render(trees['news'], [post(1, [label or '서울 부동산 뉴스'])], label=label)

    def feeds(url):
        label = unquote(url.path.split('/-/')[1]) if '/-/' in url.path else '서울 부동산 뉴스'
        return {'feed': {'entry': [entry(1, [label])]}}

    app = FixtureBrowser(browser, 'news', documents, feeds, width=width)
    try:
        app.goto()
        assert app.active() == 'all'
        assert app.page.locator('.filter-option').count() == 9
        if width == 360:
            REVIEW.mkdir(parents=True, exist_ok=True)
            app.page.screenshot(path=str(REVIEW / 'news-region-360.png'))
        for key, name in REGIONS.items():
            locator = app.page.locator(f'.filter-option[data-filter-key="{key}"]')
            assert locator.get_attribute('href') == ('/' if key == 'all' else tag_path(name + ' 부동산 뉴스'))
            locator.click()
            app.page.wait_for_url(app.origin + ('/' if key == 'all' else tag_path(name + ' 부동산 뉴스')))
            app.ready()
            assert app.active() == key
            app.page.wait_for_function('document.querySelector("[data-recent-posts]").dataset.state === "ready"')
            expected = '/feeds/posts/default' + ('/-/' + name + ' 부동산 뉴스' if name else '')
            assert unquote(urlsplit(app.feeds[-1]).path) == expected
            assert app.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        return {'case': f'news-all-nine-native-region-links-{width}', 'passed': True}
    finally:
        app.close()


def korean_pages_case(browser, trees, site, *, repeated=False, raw_leak=False):
    # An initial native page consisting entirely of translations is valid and
    # must continue through its native cursor until 24 Korean stories exist.
    records = [post(number, ['English']) for number in range(1, 6)]
    for number in range(6, 106):
        records.append(post(number, ['국내여행'] if number % 2 == 0 else ['English']))
    expected = [row['id'] for row in records if row['labels'][0]['name'] == '국내여행']
    requests = []

    def documents(url):
        query = parse_qs(url.query)
        offset = int(query.get('updated-max', ['native-0'])[0].removeprefix('native-'))
        limit = int(query.get('max-results', ['5'])[0])
        end = min(offset + min(limit, 7), len(records))
        selected = records[offset:end]
        if repeated and offset:
            selected = [post(999, ['English'])]
            end = offset
        requests.append({'offset': offset, 'limit': limit, 'end': end})
        next_url = f'/search?updated-max=native-{end}&max-results=7' if end < len(records) else None
        # A defensive runtime check must also reject an unexpected mixed page
        # even if an older native render bypassed the new SSR default guard.
        return render(trees[site], selected, cursor=next_url, label='English' if raw_leak else '')

    app = FixtureBrowser(browser, site, documents)
    try:
        app.goto()
        if repeated:
            app.page.wait_for_function('document.querySelector(".post-grid").dataset.listState === "error"')
            assert card_ids(app.page) == []
            assert len(requests) <= 3
            assert app.page.locator('.rel-older').is_visible()
        else:
            app.ready()
            assert card_ids(app.page) == list(map(int, expected[:24])), (card_ids(app.page), requests)
            assert len(requests) > 2 and requests[0]['end'] == 5
            assert all(row['limit'] <= 24 for row in requests)
            placements = app.page.locator('.post-grid .feed-ad').evaluate_all(
                '(nodes)=>nodes.map(n=>({after:Number(n.dataset.afterPost),actual:[...n.parentElement.children].slice(0,[...n.parentElement.children].indexOf(n)).filter(x=>x.classList.contains("story-card")).length}))')
            assert placements == [{'after': value, 'actual': value} for value in (6, 12, 18)], placements
            app.page.locator('.rel-older').click()
            app.page.wait_for_url('**/search?**')
            app.ready()
            assert card_ids(app.page) == list(map(int, expected[24:48])), (card_ids(app.page), requests)
        return {'case': site + '-korean-native-pagination' + ('-repeated-cursor' if repeated else '-mixed-defence' if raw_leak else '-empty-first-page'),
                'passed': True, 'requests': requests}
    finally:
        app.close()


def recent_korean_case(browser, trees, site, *, foreign_next=False, failure=False):
    def documents(url):
        return render(trees[site], [post(1, ['국내여행'])])

    def feeds(url):
        query = parse_qs(url.query)
        if 'start-index' not in query:
            next_url = ('https://other.example' if foreign_next else 'https://' + site + '.kr-inside.com') + '/feeds/posts/default?start-index=21&max-results=20'
            return {'feed': {'entry': [entry(1, ['English']), entry(2, ['日本語']), entry(3, ['국내여행']), entry(4, ['Tiếng Việt']), entry(5, ['中文'])],
                             'link': [{'rel': 'next', 'href': next_url}]}}
        if failure:
            return 503
        assert query['alt'] == ['json'], query
        return {'feed': {'entry': [entry(6, ['Domestic Travel']), entry(7, []), entry(8, ['국내여행']), entry(9, ['국내여행'])]}}

    app = FixtureBrowser(browser, site, documents, feeds)
    try:
        app.goto()
        state = 'error' if failure or foreign_next else 'ready'
        app.page.wait_for_function('(state)=>document.querySelector("[data-recent-posts]").dataset.state===state', arg=state)
        assert parse_qs(urlsplit(app.feeds[0]).query)['max-results'] == ['20']
        assert recent_ids(app.page) == ([3] if failure or foreign_next else [3, 7, 8, 9])
        assert len(app.feeds) == (1 if foreign_next else 2)
        if failure or foreign_next:
            fallback = app.page.locator('[data-recent-posts] > a')
            assert urlsplit(fallback.get_attribute('href')).path == '/'
        else:
            app.page.locator('.recent-list').scroll_into_view_if_needed()
            app.page.wait_for_function('Array.from(document.querySelectorAll(".recent-image img")).every(img=>img.complete && img.naturalWidth>0)')
            assert app.page.locator('.recent-image img').count() == 4
        return {'case': site + '-korean-recent-' + ('foreign-next-rejected' if foreign_next else 'partial-failure' if failure else 'mixed-feed-two-pages'),
                'passed': True, 'feeds': app.feeds}
    finally:
        app.close()


def alias_article_case(browser, trees, site):
    for article in (False, True):
        alias = LABELS[site]['vi'][-1]
        app = FixtureBrowser(browser, site, lambda url: render(trees[site], [post(1, [alias])], label='' if article else alias, article=article),
                             lambda url: {'feed': {'entry': [entry(1, ['Tiếng Việt'])]}})
        try:
            app.goto('/2026/10/story-1.html' if article else tag_path(alias))
            assert app.active() == 'vi'
            app.page.wait_for_function('document.querySelector("[data-recent-posts]").dataset.state === "ready"')
            assert unquote(urlsplit(app.feeds[-1]).path) == '/feeds/posts/default/-/Tiếng Việt'
        finally:
            app.close()
    return {'case': site + '-existing-subcategory-and-article-language', 'passed': True}


def foreign_and_empty_case(browser, trees, site):
    alias = LABELS[site]['en'][-1]
    records = [post(1, ['국내여행']), post(2, ['English']), post(3, ['日本語']), post(4, [alias])]
    app = FixtureBrowser(browser, site, lambda url: render(trees[site], records, label='English'),
                         lambda url: 503)
    try:
        app.goto(tag_path('English'))
        app.ready()
        assert card_ids(app.page) == [2, 4], 'Selected foreign language must also reject other translations'
        app.page.wait_for_function('document.querySelector("[data-recent-posts]").dataset.state === "error"')
        fallback = app.page.locator('[data-recent-posts] > a').get_attribute('href')
        assert unquote(urlsplit(fallback).path) == '/search/label/English'
    finally:
        app.close()
    app = FixtureBrowser(browser, site, lambda url: render(trees[site], [post(1, ['English'])]))
    try:
        app.goto()
        app.ready()
        assert card_ids(app.page) == []
        assert '이 언어의 게시물이 아직 없습니다.' in app.page.locator('.listing-status').inner_text()
        assert app.page.locator('.rel-older:visible').count() == 0
    finally:
        app.close()
    return {'case': site + '-foreign-list-isolation-and-empty-korean-tail', 'passed': True}


def nojs_and_item_case(browser, trees):
    for site in ('www', 'trip', 'item'):
        records = mixed('www')
        app = FixtureBrowser(browser, site, lambda url: render(trees[site], records, cursor='/search?updated-max=native-5&max-results=24'), javascript=False)
        try:
            app.goto()
            assert card_ids(app.page) == ([1, 2, 3, 4, 5] if site == 'item' else [5])
            assert app.page.locator('.filter-option').count() == (0 if site == 'item' else 5)
            assert app.page.locator('.rel-older').is_visible()
            assert len(app.documents) == 1 and not app.feeds
        finally:
            app.close()
    return {'case': 'javascript-disabled-korean-default-and-item-isolation', 'passed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml-root', type=Path, help='Existing root containing site/*.xml; otherwise build current portable XML')
    parser.add_argument('--report', type=Path, default=REVIEW / 'results.json')
    args = parser.parse_args()
    trees = {}
    for site in ('www', 'trip', 'news', 'item'):
        folder = (args.xml_root or REVIEW / 'build') / site
        if not args.xml_root:
            manifest = builder.build(folder, site=site)
            xml_path = folder / manifest['xml']['filename']
        else:
            names = sorted(folder.glob('*.xml'))
            assert len(names) == 1, (site, names)
            xml_path = names[0]
        trees[site] = etree.fromstring(xml_path.read_bytes(), etree.XMLParser(resolve_entities=False, no_network=True))
    results = [static_case(trees, site) for site in ('www', 'trip')]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                             args=['--no-sandbox', '--disable-dev-shm-usage'])
        for site in ('www', 'trip'):
            for width in (390, 1440):
                results.append(language_navigation_case(browser, trees, site, width))
            results.append(korean_pages_case(browser, trees, site))
            results.append(recent_korean_case(browser, trees, site))
            results.append(alias_article_case(browser, trees, site))
            results.append(foreign_and_empty_case(browser, trees, site))
        results.extend([region_case(browser, trees, width) for width in (360, 1440)])
        results.append(korean_pages_case(browser, trees, 'www', repeated=True))
        results.append(korean_pages_case(browser, trees, 'www', raw_leak=True))
        results.append(recent_korean_case(browser, trees, 'www', foreign_next=True))
        results.append(recent_korean_case(browser, trees, 'www', failure=True))
        results.append(nojs_and_item_case(browser, trees))
        browser.close()
    report = {'cases': len(results), 'passed': len(results), 'results': results,
              'limits': 'Actual XML and current shared runtime against deterministic mixed-language native pages/feeds. Preview renderer is not Blogger compiler; live imports and remote image availability are not verified.'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'passed': len(results), 'report': str(args.report)}))


if __name__ == '__main__':
    main()
