// Countdown ticker — drives any element carrying [data-deadline-utc].
// Originally bound to the platform home's .decree card; generalized so the
// WC hub lead card (.wc-stat-card.is-lead with data-deadline-utc) shares
// the same ticker. Both pages render exactly one countdown element per
// page, so querySelector (first match) is fine. Ticks every second;
// reloads the page when the deadline is reached so the next request sees
// state='live'.
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

  var dEl = el.querySelector('[data-cd-days]');
  var hEl = el.querySelector('[data-cd-hours]');
  var mEl = el.querySelector('[data-cd-mins]');
  var sEl = el.querySelector('[data-cd-secs]');
  if (!dEl || !hEl || !mEl || !sEl) {
    console.warn('[countdown] missing one or more [data-cd-*] children inside [data-deadline-utc]');
    return;
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  var timerId = null;
  var reloading = false;

  function tick() {
    var now = Date.now();
    var diff = deadline - now;
    if (diff <= 0) {
      if (reloading) return;
      reloading = true;
      dEl.textContent = '00';
      hEl.textContent = '00';
      mEl.textContent = '00';
      sEl.textContent = '00';
      if (timerId) clearInterval(timerId);
      // Wait one tick so the user sees zero, then reload for state transition
      setTimeout(function () { window.location.reload(); }, 1500);
      return;
    }
    var days = Math.floor(diff / (1000 * 60 * 60 * 24));
    var hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
    var mins = Math.floor((diff / (1000 * 60)) % 60);
    var secs = Math.floor((diff / 1000) % 60);
    dEl.textContent = pad(days);
    hEl.textContent = pad(hours);
    mEl.textContent = pad(mins);
    sEl.textContent = pad(secs);
  }

  tick();
  timerId = setInterval(tick, 1000);
})();
