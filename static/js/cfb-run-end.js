/* Corrupt Commish Club — the Observer's Seat (games/cfb/DESIGN.md 6.14, ADR-078).
 *
 * The turn itself is CSS: the card a member's run ended on carries
 * data-moment="elimination" once, and its parts play from that. This script
 * does two things. It holds the parts while the card is offscreen and lets
 * them run when it comes into view, and it records the play with one POST
 * the moment it starts, so the server never serves the moment again (the
 * server names the week; the page sends nothing). Without the script the
 * parts still play on their own; the record waits for a visit that has it.
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
  card.addEventListener('animationstart', function (event) {
    if (event.animationName.indexOf('cfb-run-') === 0) { record(); }
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
  })) { record(); }

  if (!('IntersectionObserver' in window)) { return; }
  // Only an offscreen start is held, so a card already in view stays with
  // the CSS (which also waits out The Door).
  var held = false;
  var observer = new IntersectionObserver(function (entries) {
    var inView = entries[0].isIntersecting;
    if (!inView && !held) {
      held = true;
      parts().forEach(function (animation) { animation.pause(); });
    } else if (inView) {
      if (held) { parts().forEach(function (animation) { animation.play(); }); }
      observer.disconnect();
    }
  }, { threshold: 0.6 });
  observer.observe(card);
})();
