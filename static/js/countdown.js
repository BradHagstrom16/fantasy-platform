// Countdown ticker — drives the .decree countdown card on the pre-state home.
// Reads data-deadline-utc on the .decree element; ticks every second; reloads
// the page when the deadline is reached so the next request sees state='live'.
(function () {
  var el = document.querySelector('.decree[data-deadline-utc]');
  if (!el) return;

  var deadline = new Date(el.getAttribute('data-deadline-utc')).getTime();
  if (isNaN(deadline)) return;

  var dEl = el.querySelector('[data-cd-days]');
  var hEl = el.querySelector('[data-cd-hours]');
  var mEl = el.querySelector('[data-cd-mins]');
  var sEl = el.querySelector('[data-cd-secs]');
  if (!dEl || !hEl || !mEl || !sEl) return;

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function tick() {
    var now = Date.now();
    var diff = deadline - now;
    if (diff <= 0) {
      dEl.textContent = '00';
      hEl.textContent = '00';
      mEl.textContent = '00';
      sEl.textContent = '00';
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
  setInterval(tick, 1000);
})();
