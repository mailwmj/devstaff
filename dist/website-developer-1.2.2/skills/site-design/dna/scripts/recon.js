// 参考网址侦察：在一个真实的浏览器里跑，把 CSS 侧的真相取出来。
//
// 用法（宿主浏览器工具不同，传参方式不同，但这一份就是一段普通 JS）：
//   playwright-cli eval "$(cat dna/scripts/recon.js)" > /tmp/recon.raw
//   python3 dna/scripts/dna.py recon /tmp/recon.raw --out .site/design/reference/recon.json --summary
//
// 为什么不去截图上量：截图里没有字体名、没有字号绝对值、没有动效时长，文字聚类
// 还是笔画芯与抗锯齿边缘的混合值。CSS 里这些都是精确值。截图的活是当验收基准。
//
// 所有列表都有上限并带计数：一份没有上限的侦察结果会把上下文灌满，
// 而“哪个值出现得最多”才是要判的东西。

() => {
  const MAX = 40;
  const MAX_PER_LIST = 12;
  const cut = (text, limit = 60) =>
    (text || '').replace(/\s+/g, ' ').trim().slice(0, limit);

  const tag = (el) => {
    if (!el) return '';
    const id = el.id ? '#' + el.id : '';
    const cls = typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.')
      : '';
    return el.tagName.toLowerCase() + id + cls;
  };

  const cs = (el) => {
    try {
      return el ? getComputedStyle(el) : null;
    } catch (error) {
      return null;
    }
  };

  // 按出现次数聚合，返回 [{value, count}]，多的在前。
  // 这是从一屏页面上读出“刻度”的唯一办法：单个元素给不出规律，频次能。
  const tally = (values, limit = MAX_PER_LIST) => {
    const counts = new Map();
    for (const value of values) {
      if (value === undefined || value === null) continue;
      const key = String(value).trim();
      if (!key || key === 'none' || key === 'normal' || key === 'auto'
          || key === '0px' || key === '0s' || key === 'rgba(0, 0, 0, 0)') continue;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, limit)
      .map(([value, count]) => ({ value, count }));
  };

  const all = [...document.querySelectorAll('*')];
  const visible = all.filter((el) => {
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  });

  // ---- 页面与视口 ----
  const page = {
    url: location.href,
    host: location.host,
    title: document.title,
    lang: document.documentElement.lang || null,
    dir: document.documentElement.dir || null,
    // 没加载完的页面和“这个站就这么简单”看起来一模一样。
    // 把这两个数记下来，让“没长完”能被看见。
    readyState: document.readyState,
    elementCount: all.length,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio,
    },
    colorScheme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    scrollHeight: document.documentElement.scrollHeight,
  };

  // ---- CSS 变量：名字猜不出来，只能全收 ----
  const rootStyle = cs(document.documentElement);
  const cssVariables = {};
  if (rootStyle) {
    for (const name of rootStyle) {
      if (!name.startsWith('--')) continue;
      const value = rootStyle.getPropertyValue(name).trim();
      if (value) cssVariables[name] = value;
    }
  }

  // ---- 关键元素的 computed style ----
  const ROLE_SELECTORS = [
    ['html', 'html'],
    ['body', 'body'],
    ['h1', 'h1'],
    ['h2', 'h2'],
    ['h3', 'h3'],
    ['p', 'p'],
    ['a', 'a[href]'],
    ['button', 'button, [role=button], input[type=submit]'],
    ['input', 'input:not([type=hidden]):not([type=submit]), textarea, select'],
    ['code', 'code, pre, kbd'],
    ['nav', 'nav, header'],
    ['footer', 'footer'],
    ['list', 'ul, ol'],
    ['table', 'table'],
    ['card', '[class*=card], [class*=Card]'],
    ['badge', '[class*=badge], [class*=tag], [class*=pill]'],
  ];
  const roles = [];
  for (const [label, selector] of ROLE_SELECTORS) {
    let el = null;
    try {
      el = document.querySelector(selector);
    } catch (error) {
      el = null;
    }
    const style = cs(el);
    if (!el || !style) continue;
    roles.push({
      role: label,
      selector: tag(el),
      sample: cut(el.textContent),
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      lineHeight: style.lineHeight,
      letterSpacing: style.letterSpacing,
      color: style.color,
      backgroundColor: style.backgroundColor,
      borderRadius: style.borderRadius,
      border: style.borderTopWidth + ' ' + style.borderTopStyle + ' ' + style.borderTopColor,
      boxShadow: cut(style.boxShadow, 90),
      padding: style.padding,
      transitionDuration: style.transitionDuration,
      transitionTimingFunction: style.transitionTimingFunction,
      animationDuration: style.animationDuration,
      cursor: style.cursor,
    });
  }

  // ---- 刻度：从整页频次里读 ----
  const stylesOfVisible = visible.map(cs).filter(Boolean);
  const textSizes = {};
  for (const el of visible) {
    const own = [...el.childNodes].some(
      (node) => node.nodeType === 3 && node.textContent.trim());
    if (!own) continue;
    const style = cs(el);
    if (!style) continue;
    const key = style.fontSize;
    textSizes[key] = textSizes[key] || { fontSize: key, count: 0, families: new Set() };
    textSizes[key].count += 1;
    textSizes[key].families.add(style.fontFamily.split(',')[0].replace(/["']/g, ''));
  }
  const typeScale = Object.values(textSizes)
    .sort((a, b) => parseFloat(b.fontSize) - parseFloat(a.fontSize))
    .slice(0, MAX_PER_LIST)
    .map((entry) => ({
      fontSize: entry.fontSize,
      count: entry.count,
      families: [...entry.families].slice(0, 3),
    }));

  const scale = {
    typeScale,
    fontFamilies: tally(stylesOfVisible.map((style) => style.fontFamily)),
    lineHeights: tally(stylesOfVisible.map((style) => style.lineHeight)),
    letterSpacings: tally(stylesOfVisible.map((style) => style.letterSpacing)),
    borderRadii: tally(stylesOfVisible.map((style) => style.borderRadius)),
    boxShadows: tally(stylesOfVisible.map((style) => style.boxShadow), 8),
    gaps: tally(stylesOfVisible.map((style) => style.gap)),
    maxWidths: tally(stylesOfVisible.map((style) => style.maxWidth)),
    paddings: tally(stylesOfVisible.map((style) => style.padding)),
    transitionDurations: tally(stylesOfVisible.map((style) => style.transitionDuration)),
    animationDurations: tally(stylesOfVisible.map((style) => style.animationDuration)),
    easings: tally(stylesOfVisible.map((style) => style.transitionTimingFunction)),
  };

  // ---- 动效与无障碍降级 ----
  let accessibleSheets = 0;
  let inaccessibleSheets = 0;
  let reducedMotionRules = 0;
  let keyframeRuleCount = 0;
  for (const sheet of document.styleSheets) {
    let rules = null;
    try {
      rules = sheet.cssRules;
    } catch (error) {
      inaccessibleSheets += 1; // 跨域样式表读不到，如实记，不假装看过
      continue;
    }
    accessibleSheets += 1;
    const walk = (list) => {
      for (const rule of list) {
        if (rule.conditionText && /prefers-reduced-motion/.test(rule.conditionText)) {
          reducedMotionRules += 1;
        }
        if (rule.cssText && /@keyframes/.test(rule.cssText)) keyframeRuleCount += 1;
        if (rule.cssRules) walk(rule.cssRules);
      }
    };
    walk(rules);
  }
  const motion = {
    accessibleStylesheets: accessibleSheets,
    inaccessibleStylesheets: inaccessibleSheets,
    reducedMotionRules,
    keyframeRules: keyframeRuleCount,
    smoothScroll: rootStyle ? rootStyle.scrollBehavior : null,
    stickyCount: stylesOfVisible.filter((style) => style.position === 'sticky').length,
    willChangeCount: stylesOfVisible.filter((style) => style.willChange !== 'auto').length,
  };

  // ---- 第三维：视觉特效 ----
  const canvases = [...document.querySelectorAll('canvas')].map((canvas) => {
    const contexts = [];
    for (const kind of ['2d', 'webgl', 'webgl2', 'bitmaprenderer']) {
      try {
        // 一个 canvas 只能有一种上下文，已有的会被拒，这里只探“本来是什么”
        if (canvas.getContext(kind)) contexts.push(kind);
      } catch (error) { /* 探测失败就是没有 */ }
    }
    return {
      selector: tag(canvas),
      width: canvas.width,
      height: canvas.height,
      contexts,
      cssWidth: cs(canvas).width,
      cssHeight: cs(canvas).height,
    };
  });
  const cdnHosts = new Set();
  const scripts = [...document.querySelectorAll('script[src]')].map((node) => node.src);
  for (const src of scripts) {
    try { cdnHosts.add(new URL(src).host); } catch (error) { /* 忽略 */ }
  }
  // 只拿路径比，不拿整条 URL：站自己叫 get.webgl.org 的时候，
  // 整条 URL 匹配会把它的每一个脚本都报成 WebGL 库。
  const libraryHits = [];
  for (const src of scripts) {
    let pathname = src;
    try { pathname = new URL(src).pathname; } catch (error) { /* 相对路径就用原串 */ }
    if (/three|pixi|gsap|lottie|anime|matter|d3|shader|webgl|gl-|motion|tdl|regl|zdog|troika|curtains|ogl|babylon|aframe/i.test(pathname)) {
      libraryHits.push(src);
    }
  }
  const libraries = libraryHits.slice(0, 20);
  const globals = ['THREE', 'PIXI', 'gsap', 'ScrollTrigger', 'lottie', 'anime', 'matter', 'd3',
                   'Motion', 'Lenis', 'Rive', 'Swiper', 'Vanta', 'BABYLON', 'AFRAME', 'Zdog',
                   'curtains', 'regl', 'ogl', 'Chart', 'echarts', 'mapboxgl', 'L']
    .filter((name) => name in window);
  const effectStyles = {
    backdropFilter: stylesOfVisible.filter(
      (style) => /blur/.test(style.backdropFilter || style.webkitBackdropFilter || '')).length,
    gradients: stylesOfVisible.filter(
      (style) => /gradient/.test(style.backgroundImage || '')).length,
    mixBlendMode: stylesOfVisible.filter((style) => style.mixBlendMode !== 'normal').length,
    filters: stylesOfVisible.filter((style) => style.filter !== 'none').length,
  };
  const media = {
    videos: document.querySelectorAll('video').length,
    svgs: document.querySelectorAll('svg').length,
    inlineSvgAnimations: [...document.querySelectorAll('svg')].filter(
      (svg) => svg.querySelector('animate, animateTransform, animateMotion, set')).length,
    images: document.querySelectorAll('img, picture source').length,
  };
  const effects = {
    canvases,
    libraries,
    scriptHosts: [...cdnHosts].slice(0, 8),
    globals,
    styles: effectStyles,
    media,
  };

  // ---- 素材：每个槽位的实际尺寸与来源 ----
  const assets = [...document.querySelectorAll('img')].slice(0, MAX).map((img) => {
    const box = img.getBoundingClientRect();
    let host = null;
    try { host = new URL(img.currentSrc || img.src, location.href).host; } catch (error) { /* 忽略 */ }
    return {
      src: cut(img.currentSrc || img.src, 110),
      host,
      alt: cut(img.alt, 60) || null,
      natural: img.naturalWidth + 'x' + img.naturalHeight,
      rendered: Math.round(box.width) + 'x' + Math.round(box.height),
      loading: img.loading || null,
    };
  });

  // ---- 这一趟看不到什么：说清楚，不让人把缺失当成没有 ----
  const notObserved = [
    'DOM 结构、行为与交互结果（需要实际操作或继续读 DOM）',
    '其它视口与断点下的重组（需要换视口重跑这一份）',
    '跨域样式表里的规则',
    '登录后的页面、服务端行为、隐藏状态',
    '动效的实际手感与滚动编排（需要实际操作或录像）',
  ];

  return {
    version: 1,
    tool: 'recon.js',
    page,
    cssVariables,
    roles,
    scale,
    motion,
    effects,
    assets,
    stylesheets: { accessible: accessibleSheets, inaccessible: inaccessibleSheets },
    notObserved: inaccessibleSheets > 0
      ? notObserved.concat([inaccessibleSheets + ' 份跨域样式表读不到，其中的规则不在本结果里'])
      : notObserved,
  };
}
