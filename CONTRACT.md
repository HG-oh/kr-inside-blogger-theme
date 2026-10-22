# New theme implementation contract

Original implementation, no Typify/jQuery code or old CSS dependency. All public assets live in this separate repository. UTF-8, Korean first. Native Blogger Blog and PopularPosts widgets render real post links/text/images before JavaScript. Do not require JS to reveal any primary content. The root builds templates/theme.xml.in, tools/build.py and preview fixtures.

## Visual direction and DOM

Editorial magazine, off-white paper, almost-black typography, restrained forest green accent, crisp dividers, generous spacing, restrained rounded corners. No gratuitous gradients, fake metrics or floating blobs. System Korean fonts; optional serif display accents use installed system fonts. Premium but readable, responsive 360px to 1440px, full dark mode, reduced motion, visible keyboard focus. Base content max-width 1240px.

html[data-theme=light|dark|auto], body[data-view=home|index|post|page|error]. `[hidden]` must always hide. Class `.js` is added by theme.js only. Body .menu-open when enhanced navigation open; `#site-menu` starts native `<details class=site-menu>` so no-JS navigation works. Summary.menu-toggle accessible native toggle, then div.menu-panel, button.menu-close[type=button], nav.menu-groups with 6 details.menu-group > summary + ul > li>a. Header `.site-header > .site-container.header-inner > a.brand` (span.brand-mark “kr.” + span.brand-name “KR INSIDE”) + nav.edition-nav containing four site links + div.header-actions [button.theme-toggle[data-theme-toggle], a.search-shortcut[href=#site-search], #site-menu]. Domain menus come from sites/*.json: item29, www23, news23, trip31 original unique URLs. Preserve each exact URL and its own selected labels/verification/tracking settings.

`.site-container > .intro` contains `.eyebrow`, h1[data-edition-title], p[data-edition-description], `.intro-links` links to #latest-posts and #popular-posts. `.edition-nav a[data-edition=www|news|trip|item]` gets aria-current=page fromJS. No interactive controls should depend on hidden tooltips.

`.site-container > .content-layout` contains `main#main-content` and `aside.discovery-rail`. Main `.section-heading#latest-posts` with .eyebrow, h2, .section-note; `.post-grid` contains article.story-card: a.story-image>img[width=960,height=640,loading=lazy] or span.image-placeholder, then div.story-content with a.story-category, h2.story-title>a, p.story-excerpt, div.story-meta > time + optional span. First story has `.story-card--lead` and an eager image. All stories occupy one row each on desktop and mobile. The grid fills to 24 actual story cards using native pagination; only story cards count toward that limit. Images must have solid aspect-ratio and object-fit. Empty state .empty-state.

`.pagination` contains anchors.rel-newer/rel-older and .pagination-home with real href. Single page uses `.article-header` (.article-category,h1.article-title,.article-meta), `.post-body.entry-content` (existing user HTML), `.article-footer` (.post-labels, button[data-copy-link], a[href=#comments]), `.comments` native Blogger markup. `.reading-layout` can specialize content-layout for posts. Body figures/photos/tables/code, legacy FAQ, product and TOC classes require robust contained styling. Reading body max70ch.

Sidebar `.rail-section#popular-posts` > .section-heading + ol.ranked-list > li.ranked-item > span.rank-number, a.ranked-image>img or placeholder, div.ranked-content>a.ranked-title+span.ranked-meta. Show 5 posts from native PopularPosts. Below: `.rail-section#recent-posts` > heading + `[data-recent-posts]` initially contains real anchor .feed-fallback to /search (don't show perpetual loading). JS replaces only on successful feed with ol.recent-list > li.recent-item > a.recent-image>img/span.image-placeholder + div>a.recent-title+time.recent-date. Root sets data-feed-url on this container and data-limit=4; fetch same-origin /feeds/posts/default?alt=json&max-results=4, no JSONP. On unavailable feed keep/show .feed-fallback link with clear text. Below `.rail-section.topic-section > .topic-links > a` (root domain navigation), `.rail-section.ad-section` with original ad widget optionally, visibly labelled 광고. No fake counters.

`.search-section#site-search` includes `.search-form` action=/search method=get, label.sr-only + input[name=q,type=search,required] + button. `.mobile-shortcuts` anchor navigation #latest-posts/#popular-posts/#site-search, mobile only; sticky or fixed if not covering content. Footer `.site-footer > .site-container.footer-inner` brand, description and .footer-links real site/social links, copyright (data-year).

## Behavior owned by JS agent

No dependencies. Accessible details-based menu: close button, outside-click, Escape with focus return, optionally focus containment on mobile opened overlay, body scroll lock only when opened; no-JS details remains functional. Theme button cycles auto/light/dark with localStorage guarded; labels meaningful; default auto via CSS prefers-color-scheme. Set text and edition active nav by hostname for four supportedhosts. Feed fetching must timeout, safely use DOM/textContent, handle disabled feeds/malformed/missingthumbnail/emptyfeed/networkfailure. URLs only http(s); thumbnails nativeimg; malformed images fallback never endless spinner. DOM handlers idempotent and safe ifwidgetmissing. Optional copy-current-link button with success/failure aria-live state, year. Preserve post content, never rewrite external links. No inline onerror allowed.

## Constraints

Builder produces small installable portable XML with new CSS/JS inline if publication blocked and external XML only after real asset URLs are verified. External build must never be presented as ready while unpublished. Comments use native Blogger includables, no third-party theme runtime. Repository publication is root task. CSS agent edits only assets/theme.css; JS agent assets/theme.js; validation agent tests/validate.py and related test-only fixtures. Coordinate contract adjustments through messages.

## In-list advertisements

The post grid carries data-ad-client/data-ad-slot from the existing ad-content.html, not invented IDs. Add `.feed-ad[data-after-post]` between stories after 6, 12, 18 only when another story follows. Each has label 광고 and a reserved `.ad-frame`. Create its ins.adsbygoogle only near viewport; reuse SDK and request each unit once. Ads never count as posts or replace a post.

## Domain profiles

One CSS/JS pair is shared unchanged by every edition. Site-specific settings live only in sites/*.json and generated XML: menus, intro, topics, verification and source tracking IDs. Never apply the item menu or Naver verification ID to another domain. Public asset URLs must be verified before producing external XML.

## Language and region selectors

The optional header `nav.edition-filters[data-filter-kind=language|region]` contains `.filter-inner`, `.filter-label`, `.filter-options` and `.filter-option` anchors. Anchor data attributes contain the key, JSON array of exact existing parent/subcategory labels, and optional parent feed label. Native links select existing Blogger label pages; no redirects, stored language preference or invented Korean label. www/trip default to Korean (absence of known foreign labels); news defaults to all regions. Current state uses the native route or article labels. Mobile selection scrolls only the horizontal button strip.

Every story includes hidden `.post-label-data [data-post-label]` elements for all native labels. Blogger's `any` label expression excludes foreign stories on Korean listings before JS. Foreign label pages keep their native results. Runtime counts only matching stories, advances even through a valid empty filtered grid, and uses real next-page cursors; at most 48 native requests per language fill. Recent posts use the selected parent-language/region feed, or up to six paginated default-feed requests to find four Korean posts. Feed failures preserve matching results and a link to the selected view. PopularPosts keeps the native overall ranking. Item without the optional selector retains its original behavior.
