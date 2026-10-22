"""Render synthetic preview cases from the actual Blogger XML for browser checks.

This is a deliberately small renderer for this template's trusted expression
subset, not the Blogger compiler. Native head, comments, analytics, and ad
widgets are explicit fixtures. It never accesses a blog or downloads content.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import quote

from lxml import etree

B = "http://www.google.com/2005/gml/b"
D = "http://www.google.com/2005/gml/data"
E = "http://www.google.com/2005/gml/expr"
H = "http://www.w3.org/1999/xhtml"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
CASES = ("home", "index", "post", "page", "search", "empty", "error")


def value(item):
    return item.get("_text", "") if isinstance(item, dict) else item


def resolve(path, context):
    path = path.removeprefix("data:")
    parts = path.split(".")
    item = context.get(parts.pop(0), "")
    for part in parts:
        if part == "empty":
            item = not bool(item)
        elif part == "first":
            item = item[0] if item else ""
        elif part == "escaped":
            item = value(item)
        elif part == "jsonEscaped":
            item = json.dumps(str(value(item)), ensure_ascii=False)[1:-1]
        elif part == "canonical" and isinstance(item, str):
            item = item
        elif isinstance(item, dict):
            item = item.get(part, "")
        else:
            item = ""
    return item


def find_operator(text, operator):
    """Find an operator outside quoted literals and parentheses."""
    quote_char = None
    depth = 0
    i = 0
    while i < len(text):
        char = text[i]
        if quote_char:
            if char == "\\":
                i += 2
                continue
            if char == quote_char:
                quote_char = None
        elif char in "\"'":
            quote_char = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif depth == 0 and text.startswith(operator, i):
            return i
        i += 1
    return -1


def expression(text, context):
    text = text.strip()
    if not text:
        return ""
    question = find_operator(text, "?")
    if question >= 0:
        # Every ternary in this template has a simple true arm; the false arm
        # may itself be another ternary.
        rest = text[question + 1:]
        colon = find_operator(rest, ":")
        if colon < 0:
            raise ValueError("Unsupported ternary: " + text)
        return expression(rest[:colon] if bool(value(expression(text[:question], context))) else rest[colon + 1:], context)
    for operator in (" or ", " and ", " != ", " == ", " + "):
        index = find_operator(text, operator)
        if index >= 0:
            left, right = expression(text[:index], context), expression(text[index + len(operator):], context)
            if operator == " or ":
                return bool(value(left)) or bool(value(right))
            if operator == " and ":
                return bool(value(left)) and bool(value(right))
            if operator == " != ":
                return value(left) != value(right)
            if operator == " == ":
                return value(left) == value(right)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left + right
            return str(value(left)) + str(value(right))
    if text.startswith("not "):
        return not bool(value(expression(text[4:], context)))
    if text.startswith("!"):
        return not bool(value(expression(text[1:], context)))
    if text.startswith("resizeImage(") and text.endswith(")"):
        args = text[len("resizeImage("):-1]
        comma = find_operator(args, ",")
        return expression(args if comma < 0 else args[:comma], context)
    if text.startswith("(") and text.endswith(")"):
        return expression(text[1:-1], context)
    collection = re.fullmatch(r"((?:data:)?[A-Za-z_][\w.]*) any \(([A-Za-z_]\w*)\s*=>\s*(.+)\)", text)
    if collection:
        path, variable, predicate = collection.groups()
        return any(bool(value(expression(predicate, dict(context, **{variable: item}))))
                   for item in (resolve(path, context) or []))
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in {"true", "false"}:
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"(?:data:)?[A-Za-z_][\w.]*", text):
        return resolve(text, context)
    raise ValueError("Unsupported preview expression: " + text)


def fixture_image(kind):
    scenes = {
        "city": "<rect width='960' height='640' fill='#c9d5d2'/><path d='M0 470 960 360V640H0' fill='#738e86'/><rect x='100' y='170' width='240' height='400' fill='#eeeae0'/><rect x='360' y='90' width='250' height='500' fill='#e0dbce'/><rect x='635' y='210' width='230' height='350' fill='#f6f1e6'/><path d='M390 120h190v430H390z' fill='#929f9c'/><path d='M125 200h190v35H125zm0 70h190v35H125zm0 70h190v35H125zm0 70h190v35H125z' fill='#7a8f8b'/><path d='M660 240h180v40H660zm0 85h180v40H660zm0 85h180v40H660z' fill='#9ba7a1'/><circle cx='820' cy='90' r='48' fill='#f4e2b8'/>",
        "travel": "<rect width='960' height='640' fill='#c4ddd8'/><rect y='295' width='960' height='345' fill='#5a9d9b'/><path d='M0 550 300 350 500 450 960 380V640H0' fill='#e6d8b9'/><path d='M0 425 220 260 390 370 110 530Z' fill='#5d7564'/><path d='M780 320 820 175 860 320Z' fill='#f8f3e8'/><path d='M770 335h100l-24 18h-55Z' fill='#6b6053'/><circle cx='720' cy='110' r='48' fill='#f9e5bd'/><path d='M500 500q100-30 260-20M350 565q180-25 340-25' stroke='#f9f3e8' stroke-width='9' fill='none'/>",
        "product": "<rect width='960' height='640' fill='#ded5c9'/><path d='M0 420h960v220H0' fill='#b3a18e'/><ellipse cx='470' cy='520' rx='220' ry='40' fill='#958775'/><path d='M450 250h35v240h-35Z' fill='#655d53'/><path d='M315 275 385 100h165l70 175Z' fill='#f1e7cd'/><ellipse cx='467' cy='490' rx='115' ry='25' fill='#756b5d'/><rect x='675' y='350' width='115' height='145' rx='12' fill='#eae7df'/><path d='M730 350q-75-80-35-165 65 25 35 165M735 350q85-120 45-170-70 60-45 170' fill='#4c6b50'/>",
    }
    svg = "<svg xmlns='http://www.w3.org/2000/svg' width='960' height='640' viewBox='0 0 960 640'>" + scenes[kind] + "</svg>"
    return "data:image/svg+xml," + quote(svg, safe="")


def sample_posts():
    titles = ["도시의 다음 장면을 읽는 법", "익숙한 일상에서 발견한 새로운 여행", "오래 곁에 두고 싶은 좋은 물건", "우리 동네의 변화를 기록합니다", "가볍게 떠나 깊게 머무는 주말", "나에게 맞는 경제적 자유의 속도"]
    labels = ["부동산 이야기", "국내여행", "좋은 상품", "도시와 생활", "여행의 기록", "경제적 자유"]
    snippets = ["숫자와 뉴스 너머, 우리가 살아가는 도시의 변화를 차분하게 살펴봅니다.", "멀리 떠나지 않아도 괜찮습니다. 익숙한 풍경을 다른 시선으로 만나는 시간.", "매일 사용하는 물건일수록 천천히 고릅니다. 오래 쓸 수 있는 선택의 기준.", "거리의 작은 변화가 일상을 바꿉니다. 가까운 곳에서 시작하는 관찰과 기록.", "빽빽한 일정 대신 여유를 담았습니다. 산책과 한 잔의 커피로 채운 여행.", "남과 비교하기보다 나의 기준을 세우는 일. 꾸준히 이어가는 생활과 투자의 기록."]
    posts = []
    for i, title in enumerate(titles):
        img = fixture_image(["city", "travel", "product"][i % 3]) if i != 5 else ""
        posts.append({"id": str(1001 + i), "title": title, "url": f"/2026/10/sample-{i + 1}.html", "featuredImage": img, "snippets": {"short": snippets[i]}, "date": {"_text": f"2026. 10. {22 - i:02d}", "iso8601": f"2026-10-{22 - i:02d}T09:00:00+09:00"}, "lastUpdated": {"iso8601": "2026-10-22T11:00:00+09:00"}, "author": {"name": "KR Inside"}, "labels": [{"name": labels[i], "url": "/search/label/" + quote(labels[i])}], "allowComments": True, "body": ""})
    return posts


def article_body(post):
    table = "<table><thead><tr><th>지역</th><th>주요 변화</th><th>살펴볼 점</th></tr></thead><tbody><tr><td>도심</td><td>생활 인프라와 보행 환경</td><td>일상 동선의 변화</td></tr><tr><td>주거 지역</td><td>새로운 공원과 공공 공간</td><td>오래 머물 수 있는 동네</td></tr></tbody></table>"
    return ("<p>이 페이지는 새 테마의 가독성과 반응형 표시를 확인하기 위한 샘플 콘텐츠입니다. 실제 게시물이 아닙니다.</p>"
            "<p>우리는 매일 같은 길을 걷지만, 그 풍경은 조금씩 달라집니다. 도시와 일상 사이의 작은 변화를 천천히 살펴봅니다.</p>"
            f"<figure><img src='{html.escape(post['featuredImage'], quote=True)}' width='960' height='640' alt='샘플 도시 일러스트'/><figcaption>미리보기용 샘플 이미지</figcaption></figure>"
            "<h2>가까운 풍경에서 시작하는 기록</h2><p>중요한 것은 멀리 있는 큰 이야기를 따라가는 일만은 아닙니다. <strong>우리의 생활에 닿는 변화</strong>를 발견하고 꾸준히 기록하는 일에서 새로운 관점을 얻습니다.</p>"
            "<blockquote>좋은 정보는 나의 일상과 연결될 때 더 오래 남습니다.</blockquote>"
            "<h3>세 가지 관찰의 기준</h3><ul><li>걸어서 만날 수 있는 공간</li><li>시간을 들일 만한 변화</li><li>오랫동안 이어지는 가치</li></ul>"
            + table + "<pre><code>const example = '" + "wide-readable-code-" * 18 + "';</code></pre>"
            "<div class='faq-block'><h2>자주 묻는 이야기</h2><details class='faq-item'><summary>어디서부터 살펴보면 좋을까요?</summary><p>가장 익숙한 동네부터 천천히 걸어보세요. 작은 변화가 새로운 질문을 만듭니다.</p></details></div>"
            "<div class='product-list-container'><article class='product-card'><div class='product-details'><h3 class='product-name'>일상을 기록하는 노트</h3><p>기존 게시물의 상품 카드 표시를 확인하는 샘플입니다.</p><a class='product-purchase-button' href='/search'>관련 이야기 보기</a></div></article></div>")


def context_for(case):
    posts = sample_posts()
    for post in posts:
        post["body"] = article_body(post)
    selected = posts if case in {"home", "index", "search"} else posts[:1] if case in {"post", "page"} else []
    if case == "page":
        selected = copy.deepcopy(selected)
        selected[0].update(title="KR Inside 소개", labels=[], allowComments=False)
    title = "부동산 검색 결과" if case == "search" else "KR Inside · 샘플 미리보기"
    if case in {"post", "page"}:
        title = selected[0]["title"] + " · 샘플 미리보기"
    view = {"title": title, "isHomepage": case == "home", "isPost": case == "post", "isPage": case == "page", "isSingleItem": case in {"post", "page"}, "isMultipleItems": case in {"home", "index", "search", "empty"}, "isSearch": case in {"search", "empty"}, "isError": case == "error", "isPreview": True}
    return {"view": view, "blog": {"homepageUrl": "/", "title": "KR Inside", "languageDirection": "ltr", "locale": "ko", "analyticsAccountNumber": "", "searchUrl": "/search"}, "posts": selected, "popularPosts": posts[1:6], "olderPageUrl": "/search?updated-max=2026-10-16&max-results=6" if case in {"home", "index", "search"} else "", "newerPageUrl": "/" if case == "index" else "", "case": case}


class Renderer:
    def __init__(self, assets_prefix="/assets", inline_assets=False):
        self.assets_prefix = assets_prefix.rstrip("/")
        self.inline_assets = inline_assets
        self.css_written = False
        self.js_written = False

    def children(self, node, context, raw_text=False):
        if raw_text:
            context = dict(context, _raw_text=True)
        output = self.text(node.text or "", context)
        for child in node:
            output += self.node(child, context)
            output += self.text(child.tail or "", context)
        return output

    @staticmethod
    def text(content, context):
        return str(content) if context.get("_raw_text") else html.escape(str(content))

    def stylesheet(self):
        if self.css_written:
            return ""
        self.css_written = True
        return '<link rel="stylesheet" href="' + html.escape(self.assets_prefix + "/theme.css", quote=True) + '">'

    def runtime(self):
        if self.js_written:
            return ""
        self.js_written = True
        return '<script defer src="' + html.escape(self.assets_prefix + "/theme.js", quote=True) + '"></script>'

    def node(self, node, context):
        if not isinstance(node.tag, str):
            return ""
        q = etree.QName(node)
        namespace, tag = q.namespace, q.localname
        if namespace == D:
            data = value(resolve(tag, context))
            return str(data) if tag == "post.body" else self.text(data, context)
        if namespace == B:
            if tag in {"widget-settings", "template-skin", "comment", "class", "else"}:
                return ""
            if tag == "skin":
                if self.inline_assets:
                    self.css_written = True
                    return "<style>" + (node.text or "") + "</style>"
                return self.stylesheet()
            if tag == "if":
                wanted = bool(value(expression(node.get("cond", ""), context)))
                active = wanted
                output = self.text(node.text or "", context) if active else ""
                for child in node:
                    if child.tag == "{" + B + "}else":
                        active = not wanted
                    elif active:
                        output += self.node(child, context)
                    if active:
                        output += self.text(child.tail or "", context)
                return output
            if tag == "loop":
                output = ""
                for i, item in enumerate(expression(node.get("values", ""), context) or []):
                    nested = dict(context)
                    nested[node.get("var", "item")] = item
                    if node.get("index"):
                        nested[node.get("index")] = i
                    output += self.children(node, nested)
                return output
            if tag == "eval":
                return self.text(value(expression(node.get("expr", ""), context)), context)
            if tag == "include":
                if node.get("cond") and not bool(value(expression(node.get("cond"), context))):
                    return ""
                name = node.get("name")
                if name == "all-head-content":
                    return '<meta charset="utf-8"><meta name="kr-preview" content="Synthetic sample content; limited XML fixture renderer, not Blogger output">'
                if name == "google-analytics":
                    return ""
                if name == "comments":
                    return '<section id="comments" class="comments"><h2>댓글</h2><p>미리보기에서는 Blogger 댓글 폼을 표시하지 않습니다.</p></section>'
                target = context.get("_includes", {}).get(name)
                if target is None:
                    raise ValueError("Unknown template include: " + str(name))
                nested = dict(context)
                if target.get("var") and node.get("data"):
                    nested[target.get("var")] = expression(node.get("data"), context)
                return self.children(target, nested)
            if tag == "widget":
                if node.get("visible") == "false":
                    return ""
                wid, kind = node.get("id"), node.get("type")
                if kind in {"HTML", "AdSense"}:
                    return '<div class="widget ' + html.escape(kind) + '" id="' + html.escape(wid) + '" data-preview-ad="omitted"></div>'
                nested = dict(context)
                nested["_includes"] = {x.get("id"): x for x in node.findall("{" + B + "}includable")}
                nested["this"] = {"title": node.get("title", "")}
                if kind == "PopularPosts":
                    nested["posts"] = context["popularPosts"]
                target = nested["_includes"].get("main")
                if target is None:
                    raise ValueError("No main includable for " + str(wid))
                return '<div class="widget ' + html.escape(kind) + '" id="' + html.escape(wid) + '">' + self.children(target, nested) + "</div>"
            if tag == "section":
                attrs = {"id": node.get("id", ""), "class": "section " + node.get("class", "")}
                return "<div" + self.attrs(attrs) + ">" + self.children(node, context) + "</div>"
            if tag == "includable":
                return ""
            raise ValueError("Unsupported Blogger tag: " + tag)
        if tag == "link" and node.get("rel") == "stylesheet":
            if not self.inline_assets:
                return self.stylesheet()
            self.css_written = True
        if tag == "style":
            if not self.inline_assets:
                return self.stylesheet()
            self.css_written = True
        if tag == "script" and node.get("id") == "kr-theme-runtime":
            if not self.inline_assets:
                return self.runtime()
            self.js_written = True
        attrs = {}
        for key, val in node.attrib.items():
            aq = etree.QName(key)
            if aq.namespace == B:
                continue
            attrs[aq.localname] = str(value(expression(val, context))) if aq.namespace == E else val
        classes = attrs.get("class", "").split()
        for child in node.findall("{" + B + "}class"):
            if not child.get("cond") or bool(value(expression(child.get("cond"), context))):
                name = child.get("name") or str(value(expression(child.get("{" + E + "}name", ""), context)))
                classes.extend(name.split())
        if classes:
            attrs["class"] = " ".join(classes)
        opening = "<" + tag + self.attrs(attrs) + ">"
        if tag in VOID:
            return opening
        content = self.children(node, context, raw_text=tag in {"script", "style"})
        if tag == "head" and not self.css_written:
            content += self.stylesheet()
        if tag == "body" and not self.js_written:
            content += self.runtime()
        return opening + content + "</" + tag + ">"

    @staticmethod
    def attrs(attributes):
        return "".join(' ' + key + '="' + html.escape(val, quote=True) + '"' for key, val in attributes.items())


def build(xml_path, output_dir, assets_prefix="/assets", inline_assets=False):
    source = Path(xml_path).read_bytes()
    if b"@@" in source:
        raise ValueError("Build expanded XML before previewing; template placeholders remain")
    tree = etree.fromstring(source, etree.XMLParser(resolve_entities=False, no_network=True))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        renderer = Renderer(assets_prefix, inline_assets)
        rendered = "<!doctype html>\n" + renderer.node(tree, context_for(case))
        (output_dir / (case + ".html")).write_text(rendered, encoding="utf-8")
    entries = []
    for post in sample_posts()[:4]:
        entries.append({"title": {"$t": post["title"]}, "link": [{"rel": "alternate", "href": post["url"]}], "published": {"$t": post["date"]["iso8601"]}, "summary": {"$t": post["snippets"]["short"]}, "media$thumbnail": {"url": post["featuredImage"]}, "category": [{"term": post["labels"][0]["name"]}]})
    (output_dir / "feed.json").write_text(json.dumps({"feed": {"entry": entries}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"source_xml": str(Path(xml_path).resolve()), "source_sha256": hashlib.sha256(source).hexdigest(), "scope": "Synthetic data rendered through the actual XML template; not the Blogger compiler", "cases": list(CASES), "native_stubs": ["all-head-content", "comments", "google-analytics", "HTML/AdSense widgets"], "assets_mode": "preserved_from_xml" if inline_assets else "local_asset_references", "stylesheet": "preserved from XML" if inline_assets else assets_prefix + "/theme.css", "runtime": "preserved from XML" if inline_assets else assets_prefix + "/theme.js", "feed_fixture": "feed.json", "images": "Synthetic SVG data URLs"}
    (output_dir / "preview-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--assets-prefix", default="/assets")
    parser.add_argument("--inline-assets", action="store_true", help="Preserve CSS and runtime bytes from the XML instead of referencing local asset files")
    args = parser.parse_args()
    print(json.dumps(build(args.xml, args.out, args.assets_prefix, args.inline_assets), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
