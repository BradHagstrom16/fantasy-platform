/* The Door (DESIGN.md §4.5, ADR-077): the walk from a lounge headliner panel
   into its room is one cross-document view transition, and Back walks it in
   reverse. style.css opts every same-origin navigation in (only with script
   and without reduced motion); this file stands down every one that is not
   the lounge and a room of the panel's own game, so the rest stay plain
   loads. Loaded render-blocking in <head>: pagereveal must be registered
   before the first render.

   The pairs, named here and only for the transition:
     door        the panel's head  <->  the room's masthead (.page-hero, golf .golf-context)
     door-words  the panel's name  <->  the masthead's H1 (golf: the league's name)
   The room opens out of the panel's rectangle (--door-t/r/b/l), never a blend. */
(function () {
  'use strict';

  var STASH = 'ccc-door';

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

  // The room's masthead and the words in it: the platform .page-hero and its
  // H1 (every CFB and Docket player page), or the Pay Sheet's first line,
  // which opens with the league's name.
  function masthead() {
    var hero = document.querySelector('.page-hero');
    if (hero) return { block: hero, words: hero.querySelector('h1') };
    var line = document.querySelector('.golf-context');
    if (line) return { block: line, words: line.querySelector('.golf-context-items > :first-child') };
    return null;
  }

  function inView(rect) {
    return rect.bottom > 0 && rect.top < window.innerHeight && rect.width > 0;
  }

  // Every element this file named. A page restored from the back/forward
  // cache keeps its inline styles, and two elements under one name abort the
  // transition, so each handler resets before it names.
  var named = [];

  function reset() {
    named.forEach(function (el) { el.style.viewTransitionName = ''; });
    named = [];
  }

  function name(el, value) {
    if (!el) return;
    el.style.viewTransitionName = value;
    named.push(el);
  }

  function nameLounge(link) {
    name(link, 'door');
    name(link.querySelector('.hl-panel-name'), 'door-words');
  }

  function nameRoom(m) {
    name(m.block, 'door');
    name(m.words, 'door-words');
  }

  // The window the room opens from (or closes into): the panel's rectangle as
  // clip-path insets, clamped to the viewport.
  function setWindow(rect, vw, vh) {
    var s = document.documentElement.style;
    s.setProperty('--door-t', Math.max(0, rect.top) + 'px');
    s.setProperty('--door-r', Math.max(0, vw - rect.right) + 'px');
    s.setProperty('--door-b', Math.max(0, vh - rect.bottom) + 'px');
    s.setProperty('--door-l', Math.max(0, rect.left) + 'px');
    // Back shuts the room up into the panel's top edge (style.css door-close).
    s.setProperty('--door-shut', Math.max(0, vh - rect.top) + 'px');
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

  // Clear the names once the transition is over, so nothing else on the
  // page (a later same-document morph) inherits them.
  function clearAfter(transition) {
    transition.finished.then(reset, reset);
  }

  window.addEventListener('pageswap', function (e) {
    var t = e.viewTransition;
    reset();
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
      nameLounge(link);
      t.types.add('door-in');
      return;
    }

    // Room -> lounge: a page with the room's masthead, on its way home.
    var m = to === '/' && roomSlug() ? masthead() : null;
    if (!m) { t.skipTransition(); return; }
    nameRoom(m);
    t.types.add('door-out');
  });

  window.addEventListener('pagereveal', function (e) {
    var t = e.viewTransition;
    reset();
    if (!t) return;
    var from = window.navigation && navigation.activation && navigation.activation.from;
    var fromPath = from ? pathOf(from.url) : null;
    if (fromPath === null) { t.skipTransition(); return; }

    // Room side of the door in.
    if (fromPath === '/') {
      var s = unstash();
      var m = roomSlug() ? masthead() : null;
      if (!s || !m) { t.skipTransition(); return; }
      setWindow(s, s.vw, s.vh);
      nameRoom(m);
      t.types.add('door-in');
      clearAfter(t);
      return;
    }

    // Lounge side of the door out: the panel of the room we came from.
    var link = location.pathname === '/' ? panelLink(fromPath.split('/')[1]) : null;
    var rect = link ? panelOf(link).getBoundingClientRect() : null;
    if (!rect || !inView(rect)) { t.skipTransition(); return; }
    setWindow(rect, window.innerWidth, window.innerHeight);
    nameLounge(link);
    t.types.add('door-out');
    clearAfter(t);
  });
})();
