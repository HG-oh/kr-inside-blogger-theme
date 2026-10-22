/* KR Inside Journal · progressive enhancements, no dependencies. */
(() => {
  'use strict';
  const root = document.documentElement;
  const storageKey = 'kr-inside-theme';
  const modes = ['auto', 'light', 'dark'];
  const modeNames = {auto: '자동', light: '라이트', dark: '다크'};
  const currentMode = () => modes.includes(root.dataset.theme) ? root.dataset.theme : 'auto';
  try {
    const saved = localStorage.getItem(storageKey);
    root.dataset.theme = modes.includes(saved) ? saved : currentMode();
  } catch (_) {
    root.dataset.theme = currentMode();
  }

  function safeURL(value, base = location.href) {
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
      const url = new URL(value, base);
      return /^https?:$/.test(url.protocol) ? url : null;
    } catch (_) {
      return null;
    }
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function placeholder() {
    const node = element('span', 'image-placeholder', 'KR INSIDE');
    node.setAttribute('aria-hidden', 'true');
    return node;
  }

  const recentImageRetries = new WeakMap();

  function replaceBrokenImage(image) {
    const retry = recentImageRetries.get(image);
    if (retry) { retry(); return; }
    if (image instanceof HTMLImageElement &&
        image.closest('.story-image, .ranked-image, .recent-image')) {
      image.replaceWith(placeholder());
    }
  }

  function setupTheme() {
    const buttons = document.querySelectorAll('[data-theme-toggle]');
    function labelButtons() {
      const mode = currentMode();
      const next = modes[(modes.indexOf(mode) + 1) % modes.length];
      buttons.forEach(button => {
        const label = `화면 모드: ${modeNames[mode]}. ${modeNames[next]} 모드로 변경`;
        button.setAttribute('aria-label', label);
        button.title = label;
        button.dataset.themeMode = mode;
        const visibleLabel = button.querySelector('.theme-label');
        if (visibleLabel) visibleLabel.textContent = modeNames[mode];
      });
    }
    buttons.forEach(button => {
      button.addEventListener('click', () => {
        root.dataset.theme = modes[(modes.indexOf(currentMode()) + 1) % modes.length];
        try { localStorage.setItem(storageKey, root.dataset.theme); } catch (_) { /* Optional storage. */ }
        labelButtons();
      });
      button.hidden = false;
    });
    labelButtons();
    window.addEventListener('storage', event => {
      if (event.key !== storageKey) return;
      root.dataset.theme = modes.includes(event.newValue) ? event.newValue : 'auto';
      labelButtons();
    });
  }

  function setupMenu() {
    const menu = document.getElementById('site-menu');
    if (!menu) return;
    const toggle = menu.querySelector('.menu-toggle');
    const mobile = window.matchMedia('(max-width: 760px)');
    const update = () => {
      document.body.classList.toggle('menu-open', menu.open);
      if (toggle) toggle.setAttribute('aria-expanded', String(menu.open));
    };
    function close(restoreFocus = true) {
      menu.open = false;
      update();
      if (restoreFocus && toggle) toggle.focus({preventScroll: true});
    }
    menu.addEventListener('toggle', update);
    menu.querySelectorAll('.menu-close').forEach(button => {
      button.addEventListener('click', () => close());
      button.hidden = false;
    });
    document.addEventListener('click', event => {
      if (menu.open && !menu.contains(event.target)) close(false);
    });
    menu.addEventListener('click', event => {
      const link = event.target.closest('a[href]');
      if (link) close(false);
    });
    document.addEventListener('keydown', event => {
      if (!menu.open) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
      } else if (event.key === 'Tab' && mobile.matches) {
        const focusable = [...menu.querySelectorAll('summary, a[href], button, input, [tabindex="0"]')]
          .filter(node => !node.disabled && node.getClientRects().length &&
            getComputedStyle(node).visibility !== 'hidden');
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (!first) return;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });
    update();
  }

  function setupEdition() {
    const host = location.hostname.toLowerCase();
    const editions = {
      'www.kr-inside.com': ['www', '경제를 읽고, 내일을 준비하다.', '부동산과 재테크, 직접 경험하고 기록한 경제적 자유의 이야기.'],
      'kr-inside.com': ['www', '경제를 읽고, 내일을 준비하다.', '부동산과 재테크, 직접 경험하고 기록한 경제적 자유의 이야기.'],
      'news.kr-inside.com': ['news', '지금 알아야 할, 부동산의 흐름.', '서울부터 부산까지, 지역별 부동산 소식과 도시의 변화를 한눈에.'],
      'trip.kr-inside.com': ['trip', '여행의 시작은, 좋은 발견에서.', '가까운 골목부터 낯선 도시까지. 다시 꺼내 보고 싶은 여행의 기록.'],
      'item.kr-inside.com': ['item', '일상에 필요한, 좋은 선택.', '눈여겨볼 상품과 생활의 아이디어. 나에게 맞는 선택을 찾아보세요.']
    };
    const edition = editions[host];
    if (!edition) return;
    root.dataset.edition = edition[0];
    document.querySelectorAll('.edition-nav a[data-edition]').forEach(link => {
      if (link.dataset.edition === edition[0]) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-edition-title]').forEach(node => { node.textContent = edition[1]; });
    document.querySelectorAll('[data-edition-description]').forEach(node => { node.textContent = edition[2]; });
  }

  // A template's contents are inert: never attach parsed feed/article nodes.
  // Only validated image URL strings are copied into our own image elements.
  function imageURL(value, base) {
    if (typeof value !== 'string' || /[<>\u0000-\u001f]/.test(value)) return null;
    const url = safeURL(value, base);
    if (!url || /(?:^|\/)(?:blank|spacer|pixel|transparent|tracking[-_]?pixel)(?:[._-]|$)/i.test(url.pathname)) return null;
    return url.href;
  }

  function imagesFromHTML(markup, base) {
    if (typeof markup !== 'string' || !markup.trim()) return [];
    const template = document.createElement('template');
    template.innerHTML = markup.slice(0, 1500000);
    const content = template.content;
    const candidates = [];
    const add = value => {
      const url = imageURL(value, base);
      if (url && !candidates.includes(url)) candidates.push(url);
    };
    content.querySelectorAll('img').forEach(image => {
      const width = Number.parseInt(image.getAttribute('width'), 10);
      const height = Number.parseInt(image.getAttribute('height'), 10);
      if ((width > 0 && width <= 2) || (height > 0 && height <= 2)) return;
      ['data-src', 'data-original', 'data-lazy-src'].forEach(name => add(image.getAttribute(name)));
      const srcset = image.getAttribute('data-srcset') || image.getAttribute('srcset') || '';
      srcset.split(',').map(part => part.trim().split(/\s+/)[0]).forEach(add);
      add(image.getAttribute('src'));
    });
    return candidates.slice(0, 5);
  }

  function recentImage(link, entry, postURL) {
    const queue = [imageURL(entry.media$thumbnail?.url, postURL.href),
      ...imagesFromHTML(entry.content?.$t, postURL.href),
      ...imagesFromHTML(entry.summary?.$t, postURL.href)].filter(Boolean);
    const tried = new Set();
    const image = element('img');
    image.alt = '';
    image.width = 160;
    image.height = 110;
    image.loading = 'lazy';
    image.decoding = 'async';
    function next() {
      let candidate;
      while (queue.length && !candidate) {
        const url = queue.shift();
        if (!tried.has(url)) candidate = url;
      }
      if (!candidate) {
        recentImageRetries.delete(image);
        link.replaceChildren(placeholder());
        return;
      }
      tried.add(candidate);
      if (image.parentNode !== link) link.replaceChildren(image);
      image.src = candidate;
    }
    recentImageRetries.set(image, next);
    image.addEventListener('load', () => {
      if (image.naturalWidth <= 2 || image.naturalHeight <= 2) next();
    });
    link.append(placeholder());
    next();
  }

  function recentItem(entry, base) {
    if (!entry || typeof entry !== 'object' || !Array.isArray(entry.link)) return null;
    const alternate = entry.link.find(link => link && link.rel === 'alternate' && safeURL(link.href, base));
    const url = alternate && safeURL(alternate.href, base);
    if (!url) return null;
    const title = typeof entry.title?.$t === 'string' && entry.title.$t.trim() ? entry.title.$t : '제목 없는 글';
    const item = element('li', 'recent-item');
    const imageLink = element('a', 'recent-image');
    imageLink.href = url.href;
    imageLink.setAttribute('aria-label', title);
    recentImage(imageLink, entry, url);
    const content = element('div', 'recent-content');
    const link = element('a', 'recent-title', title);
    link.href = url.href;
    content.append(link);
    const rawDate = entry.published?.$t;
    const date = typeof rawDate === 'string' ? new Date(rawDate) : null;
    if (date && Number.isFinite(date.getTime())) {
      const time = element('time', 'recent-date', new Intl.DateTimeFormat('ko-KR', {
        year: 'numeric', month: '2-digit', day: '2-digit'
      }).format(date));
      time.dateTime = date.toISOString();
      content.append(time);
    }
    item.append(imageLink, content);
    return item;
  }

  async function loadRecent(container) {
    const source = safeURL(container.dataset.feedUrl || '/feeds/posts/default?alt=json&max-results=4');
    container.dataset.state = 'loading';
    container.setAttribute('aria-busy', 'true');
    let timer;
    try {
      if (!source || source.origin !== location.origin) throw new Error('Invalid feed origin');
      const controller = new AbortController();
      timer = setTimeout(() => controller.abort(), 8000);
      const response = await fetch(source.href, {
        signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'application/json'}
      });
      if (!response.ok) throw new Error('Feed unavailable');
      const data = await response.json();
      if (!data?.feed || typeof data.feed !== 'object' || Array.isArray(data.feed) ||
          (data.feed.entry !== undefined && !Array.isArray(data.feed.entry))) throw new Error('Invalid feed');
      const list = element('ol', 'recent-list');
      const limit = Math.min(8, Math.max(1, Number(container.dataset.limit) || 4));
      for (const entry of data.feed.entry || []) {
        const item = recentItem(entry, source.href);
        if (item) list.append(item);
        if (list.children.length >= limit) break;
      }
      if (list.children.length) {
        container.replaceChildren(list);
        container.dataset.state = 'ready';
      } else {
        container.dataset.state = 'empty';
        const fallback = container.querySelector('.feed-fallback');
        if (fallback) fallback.textContent = '아직 게시물이 없습니다. 전체 글 보기';
      }
    } catch (_) {
      container.dataset.state = 'error';
      const fallback = container.querySelector('.feed-fallback');
      if (fallback) fallback.textContent = '최근 글 전체 보기';
    } finally {
      clearTimeout(timer);
      container.removeAttribute('aria-busy');
    }
  }

  function setupListing() {
    const grid = document.querySelector('.post-grid[data-page-size]');
    const navigation = document.querySelector('#main-content .pagination');
    if (!grid || !navigation) return;
    const limit = Math.min(30, Math.max(20, Number(grid.dataset.pageSize) || 24));
    let next = navigation.querySelector('.rel-older');
    const localURL = (value, base = location.href) => {
      const url = safeURL(value, base);
      return url?.origin === location.origin ? url : null;
    };
    let cursor = next ? localURL(next.getAttribute('href')) : null;
    const key = card => localURL(card.querySelector('.story-title a')?.getAttribute('href'))?.href;
    const seen = new Set([...grid.children].map(key).filter(Boolean));
    const visited = new Set();
    const status = element('div', 'listing-status');
    const message = element('span');
    message.setAttribute('role', 'status');
    const retry = element('button', 'listing-retry', '다시 불러오기');
    retry.type = 'button';
    retry.hidden = true;
    status.append(message, retry);
    navigation.before(status);

    function updateNext() {
      if (!cursor) { if (next) next.hidden = true; return; }
      if (!next) {
        next = element('a', 'rel-older', '다음 페이지 →');
        next.rel = 'next';
        navigation.append(next);
      }
      const url = new URL(cursor.href);
      url.searchParams.set('max-results', String(limit));
      next.href = url.href;
      next.hidden = false;
    }

    async function fill() {
      if (grid.dataset.listState === 'loading') return;
      grid.dataset.listState = 'loading';
      retry.hidden = true;
      if (next) next.hidden = true;
      message.textContent = cursor && grid.children.length < limit ? '이야기를 더 불러오는 중…' : '';
      try {
        for (let attempt = 0; cursor && grid.children.length < limit; attempt++) {
          if (attempt >= limit) throw new Error('Too many listing pages');
          const source = new URL(cursor.href);
          const remaining = limit - grid.children.length;
          source.searchParams.set('max-results', String(remaining));
          if (visited.has(source.href)) throw new Error('Repeated listing page');
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 8000);
          let markup, response;
          try {
            response = await fetch(source.href, {
              credentials: 'same-origin', signal: controller.signal, headers: {Accept: 'text/html'}
            });
            if (!response.ok || !localURL(response.url || source.href)) throw new Error('Listing unavailable');
            markup = await response.text();
          } finally { clearTimeout(timer); }
          // The full page stays inert; only the native story cards are appended.
          const template = document.createElement('template');
          template.innerHTML = markup;
          const cards = [...template.content.querySelectorAll('.post-grid > .story-card')];
          const older = template.content.querySelector('#main-content .pagination .rel-older');
          const following = older ? localURL(older.getAttribute('href'), source.href) : null;
          if (!cards.length || (older && !following)) throw new Error('Invalid listing page');
          const fresh = [], batchKeys = new Set(seen);
          for (const card of cards) {
            const id = key(card);
            if (!id) throw new Error('Invalid story URL');
            if (!batchKeys.has(id)) { fresh.push(card); batchKeys.add(id); }
          }
          // Never discard overflow and advance a cursor: that would skip stories.
          if (!fresh.length || fresh.length > remaining) throw new Error('Unexpected listing size');
          const fragment = document.createDocumentFragment();
          fresh.forEach(card => {
            card.querySelectorAll('script, style, link, iframe, object, embed, base').forEach(node => node.remove());
            [card, ...card.querySelectorAll('*')].forEach(node => {
              for (const attr of [...node.attributes]) {
                if (/^on/i.test(attr.name)) node.removeAttribute(attr.name);
              }
            });
            card.querySelectorAll('img').forEach(image => {
              image.loading = 'lazy';
              image.decoding = 'async';
              image.removeAttribute('fetchpriority');
            });
            card.classList.remove('story-card--lead');
            fragment.append(card);
          });
          grid.append(fragment);
          batchKeys.forEach(id => seen.add(id));
          visited.add(source.href);
          cursor = following;
        }
        grid.dataset.listState = 'ready';
        message.textContent = '';
      } catch (_) {
        grid.dataset.listState = 'error';
        message.textContent = '나머지 글을 불러오지 못했습니다. 다시 시도하거나 다음 페이지로 이동해 주세요.';
        retry.hidden = false;
      } finally { updateNext(); }
    }
    retry.addEventListener('click', fill);
    fill();
  }

  function setupCopy() {
    document.querySelectorAll('[data-copy-link]').forEach(button => {
      button.addEventListener('click', async () => {
        let status = button.parentElement.querySelector('[data-copy-status], .copy-status');
        if (!status) {
          status = element('span', 'copy-status');
          status.setAttribute('role', 'status');
          button.after(status);
        }
        status.classList.add('copy-status');
        const canonical = document.querySelector('link[rel="canonical"]')?.href;
        const url = safeURL(canonical) || safeURL(location.href);
        if (!url) return;
        try {
          if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
          await navigator.clipboard.writeText(url.href);
          status.textContent = '글 주소를 복사했습니다.';
        } catch (_) {
          status.textContent = '주소창에서 글 주소를 복사해 주세요.';
        }
      });
      button.hidden = false;
    });
  }

  function init() {
    if (root.dataset.krThemeReady === 'true') return;
    root.dataset.krThemeReady = 'true';
    root.classList.add('js');
    setupTheme();
    setupMenu();
    setupEdition();
    setupCopy();
    document.querySelectorAll('[data-year]').forEach(node => { node.textContent = new Date().getFullYear(); });
    document.addEventListener('error', event => replaceBrokenImage(event.target), true);
    document.querySelectorAll('.story-image img, .ranked-image img, .recent-image img').forEach(image => {
      if (image.complete && image.naturalWidth === 0) replaceBrokenImage(image);
    });
    document.querySelectorAll('[data-recent-posts]').forEach(loadRecent);
    setupListing();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
