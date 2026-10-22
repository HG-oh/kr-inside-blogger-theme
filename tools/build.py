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


def navigation() -> tuple[str, set[str]]:
    data = json.loads((ROOT / 'navigation.json').read_text())
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
    if len(urls) != 29:
        raise ValueError('Expected all 29 unique original menu destinations')
    return '\n'.join(markup), urls


def ad_widget() -> str:
    content = (ROOT / 'templates/ad-content.html').read_text()
    return '''<section aria-label="광고" class="rail-section ad-section"><p class="ad-label">광고</p>
<b:section class="ad-widgets" id="advertisement" maxwidgets="1" name="광고" showaddelement="yes">
<b:widget id="HTML2" locked="false" title="광고" type="HTML" version="2" visible="true">
<b:widget-settings><b:widget-setting name="content">''' + html.escape(content) + '''</b:widget-setting></b:widget-settings>
<b:includable id="main"><div class="ad-frame"><data:content/></div></b:includable>
</b:widget></b:section></section>'''


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


def build(output: Path, asset_base: str | None = None) -> dict:
    source = (ROOT / 'templates/theme.xml.in').read_text()
    css = (ROOT / 'assets/theme.css').read_text()
    js = (ROOT / 'assets/theme.js').read_text()
    if ']]>' in css or ']]>' in js or '</script' in js.lower():
        raise ValueError('Unsafe inline asset boundary')
    menu, urls = navigation()
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
        '@@VERIFICATION@@': '<meta content="50883d0c7a986cef2c594d5b344a1a9a3dca774b" name="naver-site-verification"/>',
        '@@AD_WIDGET@@': ad_widget(),
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
    filename = 'kr-inside-new-external.xml' if asset_base else 'kr-inside-new.xml'
    payload = source.encode('utf-8')
    (output / filename).write_bytes(payload)
    manifest = {
        'theme': 'KR Inside Journal', 'version': '1.0.0',
        'mode': 'verified-external' if asset_base else 'portable',
        'xml': {'filename': filename, 'bytes': len(payload), 'sha256': digest(payload)},
        'assets': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                   for p in (ROOT / 'assets/theme.css', ROOT / 'assets/theme.js')},
        'verified_public_assets': verified,
        'original_menu_destinations_retained': len(urls),
        'widgets': [{'id': w.get('id'), 'type': w.get('type')} for w in widgets],
        'blogger_import_performed': False,
    }
    (output / ('external-manifest.json' if asset_base else 'manifest.json')).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    parser.add_argument('--asset-base', help='Already published directory; bytes are verified before output')
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.asset_base), ensure_ascii=False, indent=2))
