"""Build the original KR Inside Blogger theme. No network is needed for portable XML.

External mode verifies the actual published CSS/JS bytes before writing the XML.
Usage: python3 tools/build.py --out /path/to/output
       python3 tools/build.py --out /path/to/output --asset-base https://.../assets
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'b': 'http://www.google.com/2005/gml/b', 'h': 'http://www.w3.org/1999/xhtml'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def site_config(site: str) -> dict:
    if site not in ('item', 'www', 'news', 'trip'):
        raise ValueError('Unknown site')
    data = json.loads((ROOT / 'sites' / (site + '.json')).read_text())
    if data['id'] != site or data['host'] != site + '.kr-inside.com':
        raise ValueError('Site identity mismatch')
    return data


def navigation(data: dict) -> tuple[str, set[str]]:
    markup, urls = [], set()
    for group in data['groups']:
        links = []
        for item in group['links']:
            parsed = urlsplit(item['href'])
            if parsed.scheme != 'https' or not parsed.netloc:
                raise ValueError('Menu needs an actual HTTPS destination')
            urls.add(item['href'])
            links.append('<li><a href="' + html.escape(item['href'], quote=True) + '">' + html.escape(item['label']) + '</a></li>')
        markup.append('<details class="menu-group" open="open"><summary>' + html.escape(group['title']) + '</summary><ul>' + ''.join(links) + '</ul></details>')
    if not set(data['required_urls']).issubset(urls):
        raise ValueError('An original menu destination is missing')
    return '\n'.join(markup), urls


def ad_widget(settings: dict) -> str:
    content = (ROOT / 'templates/ad-content.html').read_text()
    content = re.sub(r'ca-pub-\d+', settings['client'], content)
    content = re.sub(r'(data-ad-slot=[\"\'])\d+', lambda m: m[1] + settings['slot'], content)
    return '''<section aria-label="광고" class="rail-section ad-section"><p class="ad-label">광고</p>
<b:section class="ad-widgets" id="advertisement" maxwidgets="1" name="광고" showaddelement="yes">
<b:widget id="HTML2" locked="false" title="광고" type="HTML" version="2" visible="true">
<b:widget-settings><b:widget-setting name="content">''' + html.escape(content) + '''</b:widget-setting></b:widget-settings>
<b:includable id="main"><div class="ad-frame"><data:content/></div></b:includable>
</b:widget></b:section></section>'''


def listing_ad_settings(settings: dict) -> str:
    # Reuse the owner's existing responsive ad unit; never invent publisher IDs.
    client, slot = settings['client'], settings['slot']
    if not re.fullmatch(r'ca-pub-\d+', client) or not re.fullmatch(r'\d+', slot):
        raise ValueError('Existing AdSense client and slot are required for listing ads')
    return f'data-ad-client="{client}" data-ad-slot="{slot}"'


def link_markup(links: list[dict]) -> str:
    output = []
    for link in links:
        value = link['href']
        parsed = urlsplit(value)
        if not ((parsed.scheme == 'https' and parsed.netloc) or
                (not parsed.scheme and not parsed.netloc and value.startswith(('/', '?')))):
            raise ValueError('Invalid navigation URL')
        output.append('<a href="' + html.escape(value, quote=True) + '">' + html.escape(link['label']) + '</a>')
    return ''.join(output)


def filter_markup(settings: dict | None) -> tuple[str, str]:
    """Use existing labels for native routes and for the Korean default view."""
    story = '<b:include data="post" name="krStory"/>'
    if not settings:
        return '', story
    kind = settings['kind']
    if kind not in ('language', 'region'):
        raise ValueError('Unknown content filter')
    options = settings['options']
    labels = [label for option in options for label in option['labels']]
    if len(labels) != len(set(labels)):
        raise ValueError('A label cannot select multiple languages or regions')

    links = []
    for option in options:
        href = option['href']
        if not href.startswith('/') or href.startswith('//'):
            raise ValueError('Content filters must use same-site paths')
        attrs = {
            'class': 'filter-option', 'href': href,
            'data-filter-key': option['key'],
            'data-filter-labels': json.dumps(option['labels'], ensure_ascii=False, separators=(',', ':')),
        }
        if option.get('feed_label'):
            attrs['data-filter-feed-label'] = option['feed_label']
        links.append('<a' + ''.join(' ' + key + '="' + html.escape(value, quote=True) + '"' for key, value in attrs.items()) + '>' + html.escape(option['label']) + '</a>')
    title = html.escape(settings['label'])
    markup = '<nav class="edition-filters" aria-label="' + title + ' 선택" data-filter-kind="' + kind + '"><div class="site-container filter-inner"><span class="filter-label">' + title + '</span><div class="filter-options">' + ''.join(links) + '</div></div></nav>'
    # Selection highlighting is already handled by the shared runtime. Avoid
    # the header expr:aria-current expression that Blogger rejected on import.
    # For server-rendered Korean lists, use the data path and separate native
    # `in` / unparenthesized `any` idioms present in the original working XML.
    if kind == 'language':
        label_list = json.dumps(labels, ensure_ascii=False, separators=(',', ':'))
        route = html.escape('data:view.search.label in ' + label_list, quote=True)
        foreign = html.escape('data:post.labels any label => label.name in ' + label_list, quote=True)
        story = '<b:if cond="' + route + '">' + story + '<b:else/><b:if cond="' + foreign + '"><b:else/>' + story + '</b:if></b:if>'
    return markup, story


def tracking_markup(settings: dict) -> tuple[str, str]:
    head, body = [], ''
    gtm, clarity = settings.get('google_tag_manager'), settings.get('microsoft_clarity')
    if gtm:
        if not re.fullmatch(r'GTM-[A-Z0-9]+', gtm):
            raise ValueError('Invalid source GTM ID')
        code = "(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','" + gtm + "');"
        head.append('<script id="kr-gtm" type="text/javascript">\n//<![CDATA[\n' + code + '\n//]]>\n</script>')
        body = '<noscript><iframe height="0" src="https://www.googletagmanager.com/ns.html?id=' + gtm + '" style="display:none;visibility:hidden" title="Google Tag Manager" width="0"></iframe></noscript>'
    if clarity:
        ref = settings.get('clarity_ref', '')
        if not re.fullmatch(r'[a-z0-9]+', clarity) or (ref and not re.fullmatch(r'[a-z0-9]+', ref)):
            raise ValueError('Invalid source Clarity ID')
        code = '(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","' + clarity + ('?ref=' + ref if ref else '') + '");'
        head.append('<script id="kr-clarity" type="text/javascript">\n//<![CDATA[\n' + code + '\n//]]>\n</script>')
    return '\n'.join(head), body


def verify_assets(base: str) -> list[dict]:
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('--asset-base must be an HTTPS directory without credentials/query/fragment')
    verified = []
    for filename in ('theme.css', 'theme.js'):
        expected = (ROOT / 'assets' / filename).read_bytes()
        url = base.rstrip('/') + '/' + filename
        with urlopen(Request(url, headers={'Accept-Encoding': 'identity'}), timeout=30) as response:
            actual = response.read()
            mime = response.headers.get_content_type()
            allowed = {'text/css'} if filename.endswith('.css') else {'text/javascript', 'application/javascript'}
            if response.status != 200 or mime not in allowed or actual != expected:
                raise ValueError('Published asset is unavailable, wrong type, or differs: ' + url)
            verified.append({'url': url, 'status': response.status, 'mime': mime,
                             'bytes': len(actual), 'sha256': digest(actual)})
    return verified


def build(output: Path, asset_base: str | None = None, site: str = 'item') -> dict:
    profile = site_config(site)
    source = (ROOT / 'templates/theme.xml.in').read_text()
    css = (ROOT / 'assets/theme.css').read_text()
    js = (ROOT / 'assets/theme.js').read_text()
    if ']]>' in css or ']]>' in js or '</script' in js.lower():
        raise ValueError('Unsafe inline asset boundary')
    menu, urls = navigation(profile['navigation'])
    filter_bar, story_include = filter_markup(profile.get('filters'))
    tracking_head, tracking_body = tracking_markup(profile['tracking'])
    verified = verify_assets(asset_base) if asset_base else []
    if asset_base:
        base = html.escape(asset_base.rstrip('/'), quote=True)
        styles = '<link href="' + base + '/theme.css" rel="stylesheet"/><b:skin><![CDATA[/* KR Inside Journal */ body{margin:0}]]></b:skin>'
        scripts = '<script defer="defer" id="kr-theme-runtime" src="' + base + '/theme.js" type="text/javascript"></script>'
    else:
        styles = '<b:skin><![CDATA[' + css + ']]></b:skin>'
        scripts = '<script id="kr-theme-runtime" type="text/javascript">\n//<![CDATA[\n' + js + '\n//]]>\n</script>'
    replacements = {
        '@@STYLES@@': styles,
        '@@SCRIPTS@@': scripts,
        '@@MENU@@': menu,
        '@@FILTER_BAR@@': filter_bar,
        '@@STORY_INCLUDE@@': story_include,
        '@@VERIFICATION@@': '\n'.join('<meta name="' + html.escape(meta['name'], quote=True) + '" content="' + html.escape(meta['content'], quote=True) + '"/>' for meta in profile['verification']),
        '@@AD_WIDGET@@': ad_widget(profile['ads']),
        '@@LISTING_AD_SETTINGS@@': listing_ad_settings(profile['ads']),
        '@@TRACKING_HEAD@@': tracking_head,
        '@@TRACKING_BODY@@': tracking_body,
        '@@SITE_ID@@': site,
        '@@BRAND_CAPTION@@': html.escape(profile['brand_caption']),
        '@@INTRO_EYEBROW@@': html.escape(profile['intro']['eyebrow']),
        '@@INTRO_TITLE@@': html.escape(profile['intro']['title']),
        '@@INTRO_DESCRIPTION@@': html.escape(profile['intro']['description']),
        '@@TOPIC_LINKS@@': link_markup(profile['topics']),
        '@@FOOTER_MENU@@': link_markup(profile['footer_links']),
    }
    for token, value in replacements.items():
        if source.count(token) != 1:
            raise ValueError('Missing or duplicate template token ' + token)
        source = source.replace(token, value)
    if '@@' in source:
        raise ValueError('Unresolved template token')
    tree = ET.fromstring(source)
    ids = [n.get('id') for n in tree.iter() if n.get('id') and not n.tag.endswith('includable')]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate DOM or widget IDs')
    for section in tree.findall('.//b:section', NS):
        if any(child.tag != '{' + NS['b'] + '}widget' for child in section):
            raise ValueError('Blogger sections must contain only widgets')
    widgets = tree.findall('.//b:widget', NS)
    if sum(w.get('type') == 'Blog' for w in widgets) != 1:
        raise ValueError('Exactly one native Blog widget required')
    hrefs = {n.get('href') for n in tree.iter() if n.get('href')}
    if not urls.issubset(hrefs):
        raise ValueError('Original menu destination missing from output')
    for legacy in ('typify-', 'kr-inside-styles', 'jquery', '{getWidget}', '{homeIcon}'):
        if legacy in source.lower():
            raise ValueError('Old theme dependency remains: ' + legacy)
    output.mkdir(parents=True, exist_ok=True)
    stem = 'kr-inside-new' if site == 'item' else 'kr-inside-' + site
    filename = stem + ('-external' if asset_base else '') + '.xml'
    payload = source.encode('utf-8')
    (output / filename).write_bytes(payload)
    manifest = {
        'theme': 'KR Inside Journal', 'version': '1.4.1',
        'site': site, 'host': profile['host'], 'source': profile['source'],
        'mode': 'verified-external' if asset_base else 'portable',
        'xml': {'filename': filename, 'bytes': len(payload), 'sha256': digest(payload)},
        'assets': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                   for p in (ROOT / 'assets/theme.css', ROOT / 'assets/theme.js')},
        'verified_public_assets': verified,
        'original_menu_destinations_retained': len(set(profile['navigation']['required_urls'])),
        'menu_groups': len(profile['navigation']['groups']),
        'topic_links': len(profile['topics']),
        'content_filters': profile.get('filters'),
        'widgets': [{'id': w.get('id'), 'type': w.get('type')} for w in widgets],
        'blogger_import_performed': False,
    }
    (output / ('external-manifest.json' if asset_base else 'manifest.json')).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    parser.add_argument('--asset-base', help='Already published directory; bytes are verified before output')
    parser.add_argument('--site', choices=('item', 'www', 'news', 'trip', 'all'), default='item')
    args = parser.parse_args()
    result = [build(args.out / site, args.asset_base, site) for site in ('item', 'www', 'news', 'trip')] if args.site == 'all' else build(args.out, args.asset_base, args.site)
    print(json.dumps(result, ensure_ascii=False, indent=2))
