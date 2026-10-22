"""Check domain-specific migrations against independently captured source XML facts.

SOURCE_FACTS is a small audit snapshot extracted directly from the three uploaded
XML files, not from sites/*.json. The source hash ties each expected inventory to
its original backup. All browser requests are intercepted, including trackers
and ads; these checks do not import into Blogger or prove live ad delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lxml import etree
from playwright.sync_api import sync_playwright

from validate import ROOT, NS, SVG, feed, run_case, validate_xml

REVIEW = Path('/workspace/review/kr-inside-domain-themes')
CLASS = 'contains(concat(" ",normalize-space(@class)," ")," %s ")'

# Independently extracted from the source backups; do not regenerate from the
# implementation profiles, since that would hide a mistaken menu migration.
SOURCE_FACTS = {'www': {'source': {'filename': 'www.xml',
                    'bytes': 811122,
                    'sha256': 'b3e498be1bd8ba154a3a703a8bc87495c73125e7192acc56356f86726df2a59c'},
         'host': 'www.kr-inside.com',
         'primary_urls': ['https://www.kr-inside.com/search/label/%EA%B2%BD%EC%A0%9C%EC%A0%81%EC%9E%90%EC%9C%A0',
                          'https://kr-inside.com/search/label/부산시%20고시%20공고',
                          'https://kr-inside.com/search/label/부산시%20아파트%20분양',
                          'https://kr-inside.com/search/label/부산울산경남개발정보',
                          'https://kr-inside.com/search/label/손품발품임장기',
                          'https://kr-inside.com/search/label/이런저런생각',
                          'https://kr-inside.com/search/label/재테크%20투자후기',
                          'https://news.kr-inside.com/2025/04/main.html',
                          'https://trip.kr-inside.com/',
                          'https://kr-inside.com/search/label/English',
                          'https://kr-inside.com/search/label/Domestic%20Travel',
                          'https://kr-inside.com/search/label/Financial%20Freedom',
                          'https://kr-inside.com/search/label/%E6%97%A5%E6%9C%AC%E8%AA%9E',
                          'https://kr-inside.com/search/label/%E5%9B%BD%E5%86%85%E6%97%85%E8%A1%8C',
                          'https://kr-inside.com/search/label/%E7%B5%8C%E6%B8%88%E7%9A%84%E8%87%AA%E7%94%B1',
                          'https://kr-inside.com/search/label/Ti%E1%BA%BFng%20Vi%E1%BB%87t',
                          'https://kr-inside.com/search/label/Du%20l%E1%BB%8Bch%20n%E1%BB%99i%20%C4%91%E1%BB%8Ba',
                          'https://kr-inside.com/search/label/T%E1%BB%B1%20do%20t%C3%A0i%20ch%C3%ADnh',
                          'https://kr-inside.com/search/label/中文',
                          'https://kr-inside.com/search/label/國內旅行',
                          'https://kr-inside.com/search/label/經濟自由',
                          'https://item.kr-inside.com/',
                          'https://blog.naver.com/yak-bang'],
         'home_macro': False,
         'groups': 9,
         'tags': ['Du lịch nội địa',
                  'English',
                  'Financial Freedom',
                  'Tiếng Việt',
                  'Tự do tài chính',
                  '国内旅行',
                  '日本語',
                  '経済的自由',
                  '국내여행',
                  '부산시 고시 공고',
                  '부산울산경남개발정보',
                  '정보글'],
         'footer': [{'label': 'Home', 'href': '/'}, {'label': 'RTL Version', 'href': '?hl=ar'}],
         'verification': {'naver-site-verification': '489748095966e0969d561fd8f3f884774add7926'},
         'gtm': 'GTM-PT6SHJ9W',
         'clarity': 'sges1u0ufq',
         'client': 'ca-pub-8621160875847917',
         'slot': '7800800754',
         'intro_title': '경제를 읽고, 내일을 준비하다.'},
 'news': {'source': {'filename': 'news.xml',
                     'bytes': 779381,
                     'sha256': 'c76bd1d403d17e39bf47a56974c2682137fb5e3f8705bebb7725a28876851b9c'},
          'host': 'news.kr-inside.com',
          'primary_urls': ['https://www.kr-inside.com/search/label/경제적자유',
                           'https://kr-inside.com/search/label/부산시%20고시%20공고',
                           'https://kr-inside.com/search/label/부산시%20아파트%20분양',
                           'https://kr-inside.com/search/label/부산울산경남개발정보',
                           'https://kr-inside.com/search/label/손품발품임장기',
                           'https://kr-inside.com/search/label/이런저런생각',
                           'https://kr-inside.com/search/label/재테크%20투자후기',
                           'https://news.kr-inside.com/2025/04/main.html',
                           'https://news.kr-inside.com/search/label/%EC%84%9C%EC%9A%B8%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EB%B6%80%EC%82%B0%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EB%8C%80%EC%A0%84%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EB%8C%80%EA%B5%AC%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EA%B4%91%EC%A3%BC%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EC%9D%B8%EC%B2%9C%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EC%9A%B8%EC%82%B0%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://news.kr-inside.com/search/label/%EA%B2%BD%EA%B8%B0%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://trip.kr-inside.com/search/label/%EA%B5%AD%EB%82%B4%EC%97%AC%ED%96%89',
                           'https://trip.kr-inside.com/search/label/%ED%95%B4%EC%99%B8%EC%97%AC%ED%96%89',
                           'https://kr-inside.com/search/label/%E6%97%A5%E6%9C%AC%E8%AA%9E',
                           'https://kr-inside.com/search/label/%E5%9B%BD%E5%86%85%E6%97%85%E8%A1%8C',
                           'https://kr-inside.com/search/label/%E7%B5%8C%E6%B8%88%E7%9A%84%E8%87%AA%E7%94%B1',
                           'https://item.kr-inside.com/',
                           'https://blog.naver.com/yak-bang'],
          'home_macro': True,
          'groups': 6,
          'tags': ['경기 부동산 뉴스',
                   '광주 부동산 뉴스',
                   '대구 부동산 뉴스',
                   '대전 부동산 뉴스',
                   '부산 부동산 뉴스',
                   '서울 부동산 뉴스',
                   '울산 부동산 뉴스',
                   '인천 부동산 뉴스'],
          'footer': [{'label': 'Home', 'href': '/'}, {'label': 'RTL Version', 'href': '?hl=ar'}],
          'verification': {'naver-site-verification': '3a4e424753c00cf9cb8f542f83cd76228db66171'},
          'gtm': 'GTM-PT6SHJ9W',
          'clarity': 'sges1u0ufq',
          'client': 'ca-pub-8621160875847917',
          'slot': '7800800754',
          'intro_title': '지금 알아야 할, 부동산의 흐름.'},
 'trip': {'source': {'filename': 'trip.xml',
                     'bytes': 813603,
                     'sha256': '28be3a363328200624218b49cb8472d78b9850aac32855c437783d8398cf9f6d'},
          'host': 'trip.kr-inside.com',
          'primary_urls': ['https://www.kr-inside.com/search/label/%EA%B2%BD%EC%A0%9C%EC%A0%81%20%EC%9E%90%EC%9C%A0',
                           'https://kr-inside.com/search/label/부산시%20고시%20공고',
                           'https://kr-inside.com/search/label/부산시%20아파트%20분양',
                           'https://kr-inside.com/search/label/부산울산경남개발정보',
                           'https://kr-inside.com/search/label/손품발품임장기',
                           'https://kr-inside.com/search/label/이런저런생각',
                           'https://kr-inside.com/search/label/재테크%20투자후기',
                           'https://news.kr-inside.com/2025/04/main.html',
                           'https://korean-economist.blogspot.com/search/label/%EC%84%9C%EC%9A%B8%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://korean-economist.blogspot.com/search/label/%EB%B6%80%EC%82%B0%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://korean-economist.blogspot.com/search/label/%EB%8C%80%EC%A0%84%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://korean-economist.blogspot.com/search/label/%EB%8C%80%EA%B5%AC%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://korean-economist.blogspot.com/search/label/%EA%B4%91%EC%A3%BC%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://korean-economist.blogspot.com/search/label/%EC%9D%B8%EC%B2%9C%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://korean-economist.blogspot.com/search/label/%EC%9A%B8%EC%82%B0%20%EB%B6%80%EB%8F%99%EC%82%B0%20%EB%89%B4%EC%8A%A4',
                           'https://trip.kr-inside.com/search/label/%EA%B5%AD%EB%82%B4%EC%97%AC%ED%96%89',
                           'https://trip.kr-inside.com/search/label/해외여행',
                           'https://trip.kr-inside.com/search/label/English',
                           'https://trip.kr-inside.com/search/label/Domestic%20Travel',
                           'https://trip.kr-inside.com/search/label/International Travel',
                           'https://trip.kr-inside.com/search/label/%E6%97%A5%E6%9C%AC%E8%AA%9E',
                           'https://trip.kr-inside.com/search/label/%E5%9B%BD%E5%86%85%E6%97%85%E8%A1%8C',
                           'https://trip.kr-inside.com/search/label/海外旅行',
                           'https://trip.kr-inside.com/search/label/Ti%E1%BA%BFng%20Vi%E1%BB%87t',
                           'https://trip.kr-inside.com/search/label/Du%20l%E1%BB%8Bch%20n%E1%BB%99i%20%C4%91%E1%BB%8Ba',
                           'https://trip.kr-inside.com/search/label/Du%20l%E1%BB%8Bch%20qu%E1%BB%91c%20t%E1%BA%BF',
                           'https://trip.kr-inside.com/search/label/中文',
                           'https://trip.kr-inside.com/search/label/國內旅行',
                           'https://trip.kr-inside.com/search/label/國際旅行',
                           'https://item.kr-inside.com/',
                           'https://blog.naver.com/yak-bang'],
          'home_macro': True,
          'groups': 8,
          'tags': ['Du lịch nội địa',
                   'English',
                   'Financial Freedom',
                   'Tiếng Việt',
                   'Tự do tài chính',
                   '国内旅行',
                   '日本語',
                   '経済的自由',
                   '국내여행',
                   '부산시 고시 공고',
                   '부산울산경남개발정보',
                   '정보글'],
          'footer': [{'label': 'Home', 'href': '/'}, {'label': 'RTL Version', 'href': '?hl=ar'}],
          'verification': {'naver-site-verification': '967234663296f09ed4f4a8a9926b8db77b0b0808'},
          'gtm': 'GTM-PT6SHJ9W',
          'clarity': 'sges1u0ufq',
          'client': 'ca-pub-8621160875847917',
          'slot': '7800800754',
          'intro_title': '여행의 시작은, 좋은 발견에서.'}}

def nodes_with_class(tree, name):
    return tree.xpath('//*[' + CLASS % name + ']')


def source_check(directory):
    checked = []
    if directory is None:
        return {'mode': 'independent source audit snapshot', 'files': []}
    for site, facts in SOURCE_FACTS.items():
        matches = [p for p in directory.rglob(f'{site}.xml')
                   if hashlib.sha256(p.read_bytes()).hexdigest() == facts['source']['sha256']]
        assert len(matches) == 1, ('Original source not found uniquely', site, matches)
        source = matches[0]
        assert source.stat().st_size == facts['source']['bytes']
        tree = etree.fromstring(source.read_bytes(), etree.XMLParser(resolve_entities=False, no_network=True))
        settings = {n.get('name'): n.text or '' for n in tree.xpath(
            '//b:widget[@id="LinkList101"]/b:widget-settings/b:widget-setting', namespaces=NS)}
        links = [settings[k] for k in sorted((k for k in settings if k.startswith('link-')),
                                             key=lambda k: int(k.split('-')[1]))
                 if settings[k].startswith(('https://', 'http://'))]
        assert links == facts['primary_urls'], ('Audit snapshot differs from actual backup', site)
        checked.append({'site': site, **facts['source']})
    return {'mode': 'source files hashed and primary URLs parsed independently', 'files': checked}


def xml_check(path, site):
    facts = SOURCE_FACTS[site]
    result = validate_xml(path, {'urls': facts['primary_urls']})
    tree = etree.fromstring(path.read_bytes(), etree.XMLParser(resolve_entities=False, no_network=True))
    menu = nodes_with_class(tree, 'menu-groups')[0]
    actual = menu.xpath('.//h:a/@href', namespaces=NS)
    # Exact source strings matter: even bare-host/encoded variants are retained.
    assert set(facts['primary_urls']) <= set(actual), (site, set(facts['primary_urls']) - set(actual))
    if facts['home_macro']:
        assert f'https://{facts["host"]}/' in actual, ('Home macro needs a working site home', site)
    assert len(nodes_with_class(tree, 'menu-group')) == facts['groups']
    assert len(facts['primary_urls']) == {'www': 23, 'news': 23, 'trip': 31}[site]
    for name, value in facts['verification'].items():
        assert tree.xpath('//h:meta[@name=$name]/@content', namespaces=NS, name=name) == [value]
    scripts = '\n'.join(tree.xpath('//h:script/text()', namespaces=NS))
    assert facts['gtm'] in scripts and 'googletagmanager.com/gtm.js' in scripts
    assert facts['clarity'] in scripts and 'clarity.ms/tag/' in scripts
    assert tree.xpath('//h:noscript/h:iframe/@src', namespaces=NS) == [
        'https://www.googletagmanager.com/ns.html?id=' + facts['gtm']]
    topic = nodes_with_class(tree, 'topic-links')[0]
    links = topic.xpath('./h:a', namespaces=NS)
    actual_tags = []
    for link in links:
        href = urlsplit(link.get('href'))
        assert href.hostname == facts['host']
        assert href.path.startswith('/search/label/')
        actual_tags.append(unquote(href.path[len('/search/label/'):]))
    assert set(actual_tags) == set(facts['tags']), (site, actual_tags, facts['tags'])
    assert len(links) == len(facts['tags'])
    footer_urls = set(nodes_with_class(tree, 'footer-links')[0].xpath('.//h:a/@href', namespaces=NS))
    assert {row['href'] for row in facts['footer']} <= footer_urls
    grid = nodes_with_class(tree, 'post-grid')[0]
    assert grid.get('data-page-size') == '24'
    assert grid.get('data-ad-client') == facts['client']
    assert grid.get('data-ad-slot') == facts['slot']
    assert tree.xpath('//h:div[@data-recent-posts]/@data-limit', namespaces=NS) == ['4']
    assert tree.xpath('//b:widget[@type="PopularPosts"]', namespaces=NS)
    assert tree.xpath('//b:include[@name="comments"]', namespaces=NS)
    assert tree.xpath('//b:include[@name="google-analytics"]', namespaces=NS)
    # Also catch accidental reuse of the item profile's verification/menu.
    profile = json.loads((ROOT / 'sites' / f'{site}.json').read_text())
    assert profile['source'] == facts['source']
    assert set(profile['navigation']['required_urls']) == set(facts['primary_urls'])
    runtime = tree.find('.//h:script[@id="kr-theme-runtime"]', NS)
    stylesheet = tree.find('.//b:skin', NS)
    if runtime.get('src'):
        css = tree.xpath('//h:link[@rel="stylesheet"]/@href', namespaces=NS)
        assert len(css) == 1
        asset_identity = {'mode': 'external', 'css': css[0], 'js': runtime.get('src')}
    else:
        asset_identity = {'mode': 'inline',
                          'css': hashlib.sha256((stylesheet.text or '').encode()).hexdigest(),
                          'js': hashlib.sha256((runtime.text or '').encode()).hexdigest()}
    result.update(site=site, menuGroups=facts['groups'], primaryLinks=len(facts['primary_urls']),
                  tags=len(facts['tags']), source=facts['source'], assets=asset_identity)
    return result


def profile_browser(browser, preview, site, width, javascript):
    facts = SOURCE_FACTS[site]
    origin = 'https://' + facts['host']
    context = browser.new_context(viewport={'width': width, 'height': 960},
                                  java_script_enabled=javascript, reduced_motion='reduce')
    page = context.new_page()
    errors, mocked_tracking = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def route_request(route):
        parsed = urlsplit(route.request.url)
        if route.request.url == origin + '/':
            route.fulfill(status=200, content_type='text/html', body=(preview / 'home.html').read_text())
        elif parsed.path.endswith('/theme.css'):
            route.fulfill(status=200, content_type='text/css', body=(ROOT / 'assets/theme.css').read_bytes())
        elif parsed.path.endswith('/theme.js'):
            route.fulfill(status=200, content_type='application/javascript', body=(ROOT / 'assets/theme.js').read_bytes())
        elif parsed.path.startswith('/feeds/posts/default'):
            route.fulfill(status=200, content_type='application/json', body=json.dumps(feed('success', facts['host'])))
        elif any(name in (parsed.hostname or '') for name in ('googletagmanager.com', 'clarity.ms', 'googlesyndication.com')):
            mocked_tracking.append(route.request.url)
            route.fulfill(status=200, content_type='application/javascript' if route.request.resource_type == 'script' else 'text/html', body='')
        elif route.request.resource_type == 'image':
            route.fulfill(status=200, content_type='image/svg+xml', body=SVG)
        else:
            route.abort()

    context.route('**/*', route_request)
    try:
        page.goto(origin + '/', wait_until='load')
        if javascript:
            page.locator('.recent-item').first.wait_for(timeout=4000)
        assert page.locator('[data-edition-title]').text_content().strip() == facts['intro_title']
        assert page.locator('.topic-links > a').count() == len(facts['tags'])
        toggle = page.locator('#site-menu > summary')
        toggle.click()
        assert page.locator('#site-menu').evaluate('node=>node.open')
        groups = page.locator('.menu-group')
        assert groups.count() == facts['groups']
        links = page.locator('.menu-groups a')
        actual = links.evaluate_all('nodes=>nodes.map(n=>n.getAttribute("href"))')
        assert set(facts['primary_urls']) <= set(actual)
        # All groups can be reached and expanded; no lost links behind a clipped
        # overlay or an inaccessible collapsed branch on mobile.
        for index in range(groups.count()):
            group = groups.nth(index)
            summary = group.locator('summary')
            if group.evaluate('node=>node.open'):
                summary.click()
            assert not group.evaluate('node=>node.open')
            assert summary.evaluate('node=>getComputedStyle(node,"::after").content') == '"+"'
            summary.click()
            assert group.evaluate('node=>node.open')
            assert summary.evaluate('node=>getComputedStyle(node,"::after").content') == '"−"'
            for link in group.locator('a').all():
                link.scroll_into_view_if_needed()
                assert link.is_visible()
                box = link.bounding_box()
                assert box and box['x'] >= -1 and box['x'] + box['width'] <= width + 1
        if javascript:
            page.keyboard.press('Escape')
        else:
            toggle.click()
        assert not page.locator('#site-menu').evaluate('node=>node.open')
        assert not errors, errors
        return {'site': site, 'width': width, 'javascript': javascript,
                'menuGroups': groups.count(), 'exactSourceLinks': len(facts['primary_urls']),
                'allMenuLinksReachable': True, 'mockedTracking': mocked_tracking}
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REVIEW)
    parser.add_argument('--sources', type=Path, help='Optional original upload directory; hashes and parsed links must match audit facts')
    parser.add_argument('--report', type=Path, default=REVIEW / 'validation-domains.json')
    args = parser.parse_args()
    report = {'status': 'running', 'scope': 'Independent source XML audit plus offline browser fixtures; no live Blogger import or ad serving', 'xml': [], 'browser': []}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        report['sourceVerification'] = source_check(args.sources)
        identities = {'inline': [], 'external': []}
        for site in SOURCE_FACTS:
            directory = args.root / site
            paths = [p for p in (directory / f'kr-inside-{site}.xml', directory / f'kr-inside-{site}-external.xml') if p.exists()]
            assert paths, ('Missing built XML', site, directory)
            for path in paths:
                result = xml_check(path, site)
                report['xml'].append(result)
                identities[result['assets']['mode']].append(result['assets'])
        for mode, group in identities.items():
            if group:
                assert len({(row['css'], row['js']) for row in group}) == 1, ('Domains do not share identical assets', mode, group)
        report['sharedAssetsIdentical'] = True
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                                  args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                for site, facts in SOURCE_FACTS.items():
                    preview = args.root / site / 'previews'
                    for width in (390, 1440):
                        result = run_case(browser, preview, host=facts['host'], view='home', width=width, interactions=True)
                        report['browser'].append({'kind': 'common-home', **result})
                        for javascript in (True, False):
                            result = profile_browser(browser, preview, site, width, javascript)
                            report['browser'].append({'kind': 'profile-menu', **result})
                    result = run_case(browser, preview, host=facts['host'], view='post', width=390)
                    report['browser'].append({'kind': 'common-article', **result})
                    print('PASS', site, 'source links, metadata, tags, shared assets and 7 browser cases', flush=True)
            finally:
                browser.close()
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'xmls': len(report['xml']), 'browserCases': len(report['browser']), 'report': str(args.report)}))


if __name__ == '__main__':
    main()
