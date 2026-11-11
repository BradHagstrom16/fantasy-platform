/* The Door (DESIGN.md §4.5, ADR-077 as amended by ADR-079): the walk from a
   lounge headliner panel into its room is one cross-document view transition,
   and Back walks it in reverse. style.css opts every same-origin navigation
   in (only with script and without reduced motion); this file stands down
   every one that is not the lounge and a room of the panel's own game, so the
   rest stay plain loads. Loaded render-blocking in <head>: pagereveal must be
   registered before the first render.

   Two doors part from a seam down the middle of the panel and the room is
   behind them, already in its place: nothing in the room moves, so this file
   names no element. It hands the stylesheet the doorway (the panel's
   rectangle, --door-t/r/b/l), the seam (--door-sl/sr), the point the lounge
   falls back from (--door-cx/cy) and the navbar's lower edge (--door-nav),
   and it answers the tap: the panel
   takes .is-unlatched, which draws the seam before the room has loaded. */
(function () {
  'use strict';

  var STASH = 'ccc-door';
  var SCROLL = 'ccc-door-scroll';
  var LATCH = 'is-unlatched';
  // How long a tap's seam waits for its navigation before it gives up.
  var LATCH_MS = 4000;

  function pathOf(url) {
    try { return new URL(url).pathname; } catch (e) { return null; }
  }

  function roomSlug() {
    var m = /(?:^|\s)game-([a-z]+)(?:\s|$)/.exec(document.body ? document.body.className : '');
    return m ? m[1] : null;
  }

  function panelLink(slug) {
    return slug ? document.querySelector('.home-shell .hl-panel-link[data-door-slug="' + slug + '"]') : null;
  }

  // The room's masthead: the platform .page-hero (every CFB and Docket player
  // page) or the Pay Sheet's first line. The door only opens onto a page that
  // has one, so a member always lands on the room's name.
  function masthead() {
    return document.querySelector('.page-hero') || document.querySelector('.golf-context');
  }

  // Seen means inside the window and below the sticky navbar: a panel
  // scrolled up under the bar is out of sight, so the walk is a plain load.
  function inView(rect) {
    var nav = document.querySelector('.navbar');
    var top = nav ? Math.max(0, nav.getBoundingClientRect().bottom) : 0;
    return Math.min(rect.bottom, window.innerHeight) > Math.max(rect.top, top) &&
           Math.min(rect.right, window.innerWidth) > Math.max(rect.left, 0);
  }

  // The doorway: the panel's rectangle as clip-path insets, clamped to the
  // viewport, the seam down its middle, and its centre.
  function setDoorway(rect, vw, vh) {
    var s = document.documentElement.style;
    var left = Math.max(0, rect.left);
    var right = Math.min(vw, rect.right);
    var top = Math.max(0, rect.top);
    var bottom = Math.min(vh, rect.bottom);
    var cx = (left + right) / 2;
    s.setProperty('--door-t', top + 'px');
    s.setProperty('--door-r', (vw - right) + 'px');
    s.setProperty('--door-b', (vh - bottom) + 'px');
    s.setProperty('--door-l', left + 'px');
    s.setProperty('--door-sl', cx + 'px');
    s.setProperty('--door-sr', (vw - cx) + 'px');
    s.setProperty('--door-cx', cx + 'px');
    s.setProperty('--door-cy', ((top + bottom) / 2) + 'px');
    // Where the sticky navbar ends: the lounge's picture is cut off there.
    var nav = document.querySelector('.navbar');
    s.setProperty('--door-nav', (nav ? Math.max(0, nav.getBoundingClientRect().bottom) : 0) + 'px');
  }

  function panelOf(link) {
    return link.closest('.hl-panel') || link;
  }

  function stash(value) {
    try {
      if (value) sessionStorage.setItem(STASH, JSON.stringify(value));
      else sessionStorage.removeItem(STASH);
    } catch (e) { /* storage blocked: the room side finds nothing and stands down */ }
  }

  function unstash() {
    var value = null;
    try { value = JSON.parse(sessionStorage.getItem(STASH)); } catch (e) { value = null; }
    stash(null);
    return value;
  }

  // Where the lounge was scrolled to when the member walked in. A lounge
  // reloaded by Back (a signed-in page is no-store, so it is never kept in
  // the back/forward cache) reveals at the top, before the browser puts the
  // scroll back, and a panel further down the page (the second one on a
  // phone) would be out of sight: no doorway, no door. So Back puts the
  // scroll back itself, first, to where the browser is about to put it.
  function stashScroll(y) {
    try { sessionStorage.setItem(SCROLL, String(Math.round(y))); } catch (e) { /* as stash() */ }
  }

  function restoreScroll() {
    var y = 0;
    try { y = parseInt(sessionStorage.getItem(SCROLL), 10) || 0; } catch (e) { y = 0; }
    if (y > 0 && window.scrollY === 0) window.scrollTo({ top: y, behavior: 'instant' });
  }

  // The door is the arriving page's entrance, so its own load-in (the cards'
  // rise, a stagger) is finished before the first frame: seen through the
  // doorway, the room is already in its place. A loop (a live dot) and a
  // terminal moment ([data-moment], which waits the door out) are left alone.
  function settle() {
    if (!document.getAnimations) return;
    document.getAnimations().forEach(function (a) {
      var fx = a.effect;
      var el = fx && fx.target;
      if (!el || (fx.pseudoElement && fx.pseudoElement.indexOf('::view-transition') === 0)) return;
      if (fx.getComputedTiming().iterations === Infinity || el.closest('[data-moment]')) return;
      a.finish();
    });
  }

  // The latch. A page restored from the back/forward cache keeps the class a
  // tap left on it, so every way back to the lounge clears it: the door out
  // when it lands, pageshow when no door ran.
  var latchTimer = 0;
  var closing = false;

  function unlatch() {
    clearTimeout(latchTimer);
    var held = document.querySelectorAll('.home-shell .' + LATCH);
    for (var i = 0; i < held.length; i++) held[i].classList.remove(LATCH);
  }

  function latch(panel) {
    unlatch();
    panel.classList.add(LATCH);
  }

  // The tap's answer: a plain click on any link into a seated panel's game
  // draws that panel's seam at once, while the room is still loading.
  document.addEventListener('click', function (e) {
    if (location.pathname !== '/' || e.defaultPrevented || e.button !== 0 ||
        e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest ? e.target.closest('a[href]') : null;
    if (!a || a.target === '_blank' || a.origin !== location.origin) return;
    var link = panelLink(a.pathname.split('/')[1]);
    if (!link || !inView(panelOf(link).getBoundingClientRect())) return;
    latch(panelOf(link));
    latchTimer = setTimeout(unlatch, LATCH_MS);
  });

  window.addEventListener('pageshow', function () {
    if (!closing) unlatch();
  });

  window.addEventListener('pageswap', function (e) {
    var t = e.viewTransition;
    if (!t) return;
    var to = e.activation && e.activation.entry ? pathOf(e.activation.entry.url) : null;
    if (to === null) { t.skipTransition(); return; }

    // Lounge -> room: the destination is under a seated panel's game.
    if (location.pathname === '/') {
      var link = panelLink(to.split('/')[1]);
      var rect = link ? panelOf(link).getBoundingClientRect() : null;
      if (!rect || !inView(rect)) { t.skipTransition(); return; }
      stash({ top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left,
              vw: window.innerWidth, vh: window.innerHeight });
      stashScroll(window.scrollY);
      t.types.add('door-in');
      return;
    }

    // Room -> lounge: a page with the room's masthead, on its way home.
    if (to !== '/' || !roomSlug() || !masthead()) { t.skipTransition(); return; }
    t.types.add('door-out');
  });

  window.addEventListener('pagereveal', function (e) {
    var t = e.viewTransition;
    if (!t) return;
    var from = window.navigation && navigation.activation && navigation.activation.from;
    var fromPath = from ? pathOf(from.url) : null;
    if (fromPath === null) { t.skipTransition(); return; }

    // Room side of the door in.
    if (fromPath === '/') {
      var s = unstash();
      if (!s || !roomSlug() || !masthead()) { t.skipTransition(); return; }
      setDoorway(s, s.vw, s.vh);
      settle();
      t.types.add('door-in');
      return;
    }

    // Lounge side of the door out: the panel of the room we came from. The
    // doors shut onto its seam, which lets go once they have landed.
    var link = location.pathname === '/' ? panelLink(fromPath.split('/')[1]) : null;
    if (link && navigation.activation.navigationType === 'traverse') restoreScroll();
    var rect = link ? panelOf(link).getBoundingClientRect() : null;
    if (!rect || !inView(rect)) { t.skipTransition(); return; }
    setDoorway(rect, window.innerWidth, window.innerHeight);
    closing = true;
    settle();
    latch(panelOf(link));
    t.types.add('door-out');
    var landed = function () { closing = false; unlatch(); };
    t.finished.then(landed, landed);
  });
})();
