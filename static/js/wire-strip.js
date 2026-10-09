/* Corrupt Commish Club — the live wire in the lounge strip (ADR-074, PR B).
 *
 * Adds `is-live` to the Wire strip once, the first time it enters view, and
 * nothing more: the pulse along the wire and the phone's one shake are CSS
 * keyframes that run once from that class. Nothing loops, nothing runs
 * offscreen, and a browser without IntersectionObserver (or with reduced
 * motion, which the CSS handles) keeps the still wire with the phone lit.
 */
(function () {
  'use strict';
  var strip = document.querySelector('.wire-strip');
  if (!strip || !('IntersectionObserver' in window)) { return; }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) { return; }
      strip.classList.add('is-live');
      observer.disconnect();
    });
  }, { threshold: 0.4 });
  observer.observe(strip);
})();
