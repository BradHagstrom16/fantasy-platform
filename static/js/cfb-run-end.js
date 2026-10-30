/* Corrupt Commish Club — the Observer's Seat (games/cfb/DESIGN.md 6.14, ADR-078).
 *
 * The turn itself is CSS: the card a member's run ended on carries
 * data-moment="elimination" once, and its parts play from that. This script
 * does two things. It holds the parts while the card is offscreen and lets
 * them run when it comes into view, and it records the play with one POST
 * once a part has started in view, so the server never serves the moment
 * again (the server names the week; the page sends nothing). Without the
 * script the parts still play on their own; the record waits for a visit
 * that has it.
 */
(function () {
  'use strict';
  var card = document.querySelector('[data-moment="elimination"]');
  if (!card) { return; }

  var recorded = false;
  function record() {
    if (recorded) { return; }
    recorded = true;
    var meta = document.querySelector('meta[name="csrf-token"]');
    fetch(card.getAttribute('data-moment-seen'), {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'X-CSRFToken': meta ? meta.content : '' }
    }).catch(function () {});
  }

  // A start counts once the card has been seen. Until the observer has
  // looked (or where there is none), a start is held, never recorded.
  var watching = !!(card.getAnimations && 'IntersectionObserver' in window);
  var seen = false;
  var started = false;
  function start() {
    started = true;
    if (seen || !watching) { record(); }
  }
  card.addEventListener('animationstart', function (event) {
    if (event.animationName.indexOf('cfb-run-') === 0) { start(); }
  });

  if (!card.getAnimations) { return; }
  function parts() {
    return card.getAnimations({ subtree: true }).filter(function (animation) {
      return (animation.animationName || '').indexOf('cfb-run-') === 0;
    });
  }
  // A deferred script can arrive after a part has begun (the reduced-motion
  // fade starts on the first frame, before anyone is listening): count it.
  if (parts().some(function (animation) {
    return animation.playState === 'finished' ||
      (animation.currentTime || 0) > (animation.effect.getTiming().delay || 0);
  })) { start(); }

  if (!watching) { return; }
  // Only an offscreen card is held, so a card already in view stays with
  // the CSS (which also waits out The Door). A hold rewinds the parts, so a
  // turn that began before the observer looked plays whole when it is seen.
  var held = false;
  var observer = new IntersectionObserver(function (entries) {
    var inView = entries[0].isIntersecting;
    if (!inView && !held) {
      held = true;
      parts().forEach(function (animation) {
        animation.pause();
        animation.currentTime = 0;
      });
    } else if (inView) {
      seen = true;
      if (held) {
        parts().forEach(function (animation) { animation.play(); });
        record();
      } else if (started) {
        record();
      }
      observer.disconnect();
    }
  }, { threshold: 0.6 });
  observer.observe(card);
})();
