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

  function replaceBrokenImage(image) {
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
    const thumb = safeURL(entry.media$thumbnail?.url, base);
    if (thumb) {
      const image = element('img');
      image.src = thumb.href;
      image.alt = '';
      image.width = 160;
      image.height = 110;
      image.loading = 'lazy';
      image.decoding = 'async';
      imageLink.append(image);
    } else imageLink.append(placeholder());
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
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
