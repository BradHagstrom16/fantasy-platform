// Countdown ticker — drives any element carrying [data-deadline-utc].
// Originally bound to the platform home's .decree card; generalized so the
// WC hub lead card (.wc-stat-card.is-lead with data-deadline-utc) shares
// the same ticker. Both pages render exactly one countdown element per
// page, so querySelector (first match) is fine. Ticks every second;
// reloads the page when the deadline is reached so the next request sees
// state='live'.
//
// S6.1.5 PI-1 — server-time anchor. When [data-server-now-utc] is present,
// compute the drift between the client clock at page-load and the server's
// authoritative "now" and use (Date.now() - drift) for deadline math. This
// prevents a misset local clock from overriding the Decree of the Commish:
// without the anchor, the server-rendered Days numeral lasted ~1s before
// being trampled by Date.now()-based JS math. The anchor preserves the
// authoritative server value across the live tick.
(function () {
  var el = document.querySelector('[data-deadline-utc]');
  if (!el) {
    // No countdown on this page. Quiet exit — the WC hub loads this script
    // unconditionally in pre-state via home_shell.html, and a future state
    // partial may legitimately omit the element.
    return;
  }

  var deadlineStr = el.getAttribute('data-deadline-utc');
  // Defense-in-depth: the attribute is named `-utc`, so the string MUST
  // carry an explicit UTC marker. Without one, Chrome/Safari parse a
  // space-separated ISO datetime as LOCAL time and silently drift the
  // countdown. Today the Jinja side always emits trailing `Z`; this guard
  // catches any future template regression.
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(deadlineStr)) {
    console.warn('[countdown] data-deadline-utc lacks timezone marker (Z or ±HH:MM):', deadlineStr);
    return;
  }
  var deadline = new Date(deadlineStr).getTime();
  if (isNaN(deadline)) {
    console.warn('[countdown] data-deadline-utc is not parseable as a date:', deadlineStr);
    return;
  }

  // Drift = (client wall clock at load) - (server "now" at render). All
  // subsequent ticks use Date.now() - drift as the authoritative "now". The
  // drift is computed once at page load and held constant; we don't try to
  // resync (the page reloads on deadline anyway, and small client-clock
  // tick-rate variance over <1 hour is below the resolution we display).
  var drift = 0;
  var serverNowStr = el.getAttribute('data-server-now-utc');
  if (serverNowStr) {
    if (!/(Z|[+-]\d{2}:?\d{2})$/.test(serverNowStr)) {
      console.warn('[countdown] data-server-now-utc lacks timezone marker:', serverNowStr);
    } else {
      var serverNow = new Date(serverNowStr).getTime();
      if (!isNaN(serverNow)) {
        drift = Date.now() - serverNow;
      }
    }
  }

  var dEl = el.querySelector('[data-cd-days]');
  var hEl = el.querySelector('[data-cd-hours]');
  var mEl = el.querySelector('[data-cd-mins]');
  var sEl = el.querySelector('[data-cd-secs]');
  if (!dEl || !hEl || !mEl || !sEl) {
    console.warn('[countdown] missing one or more [data-cd-*] children inside [data-deadline-utc]');
    return;
  }
  // The .decree-hero aria-label needs to track the live Days value so a
  // screen-reader user reading the countdown after the first tick still
  // hears the right number. Find the labelled wrapper (may be absent on
  // surfaces that haven't adopted the S6.1.5 PI-1 aria pattern yet).
  var heroEl = dEl.closest('[aria-label]');

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  // Live "alive" pulse: when a digit changes, give it a quick low-amplitude
  // settle so the countdown reads as ticking, not static. Transform/opacity
  // only (composited); skipped entirely under reduced-motion and on engines
  // without the Web Animations API. Fires only on an actual value change, so
  // an unchanged digit (e.g. days holding steady) never animates.
  var REDUCED = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  function setDigit(node, value) {
    if (node.textContent === value) return;
    node.textContent = value;
    if (REDUCED || !node.animate) return;
    node.animate(
      [{ opacity: 0.5, transform: 'translateY(-2px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: 280, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
    );
  }

  var timerId = null;
  var reloading = false;

  function tick() {
    var now = Date.now() - drift;
    var diff = deadline - now;
    if (diff <= 0) {
      if (reloading) return;
      reloading = true;
      dEl.textContent = '00';
      hEl.textContent = '00';
      mEl.textContent = '00';
      sEl.textContent = '00';
      if (heroEl) heroEl.setAttribute('aria-label', '0 days until kickoff');
      if (timerId) clearInterval(timerId);
      // Wait one tick so the user sees zero, then reload for state transition
      setTimeout(function () { window.location.reload(); }, 1500);
      return;
    }
    var days = Math.floor(diff / (1000 * 60 * 60 * 24));
    var hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
    var mins = Math.floor((diff / (1000 * 60)) % 60);
    var secs = Math.floor((diff / 1000) % 60);
    setDigit(dEl, pad(days));
    setDigit(hEl, pad(hours));
    setDigit(mEl, pad(mins));
    setDigit(sEl, pad(secs));
    if (heroEl) {
      heroEl.setAttribute(
        'aria-label',
        days + (days === 1 ? ' day' : ' days') + ' until kickoff'
      );
    }
  }

  tick();
  timerId = setInterval(tick, 1000);
})();
