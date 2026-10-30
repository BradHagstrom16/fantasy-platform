/* Corrupt Commish Club — the Observer's Seat (games/cfb/DESIGN.md 6.14, ADR-078).
 *
 * The turn itself is CSS: the card a member's run ended on carries
 * data-moment="elimination" once, and its parts play from that. This script
 * does two things. It holds the parts while the card is out of view and lets
 * them run when it is seen, and it records the play with one POST once a
 * part has begun while the card is seen, so the server never serves the
 * moment again (the card's URL names the week it showed; the server records
 * it only while that week is due). Without the script the parts still play
 * on their own; the record waits for a visit that has it.
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

  // Without the Web Animations API or an observer the script cannot tell
  // where the card is, so the first part to start is the record.
  if (!card.getAnimations || !('IntersectionObserver' in window)) {
    card.addEventListener('animationstart', function (event) {
      if (event.animationName.indexOf('cfb-run-') === 0) { record(); }
    });
    return;
  }

  function parts() {
    return card.getAnimations({ subtree: true }).filter(function (animation) {
      return (animation.animationName || '').indexOf('cfb-run-') === 0;
    });
  }
  // A part has begun once it is past its delay (the reduced-motion fade has
  // none). Read from the parts themselves, so a part that began before this
  // deferred script arrived counts too.
  function begun() {
    return parts().some(function (animation) {
      return animation.playState === 'finished' ||
        (animation.currentTime || 0) > (animation.effect.getTiming().delay || 0);
    });
  }

  var seen = false;
  var held = false;
  var looking = false;
  // The observer calls only when the card's visible share crosses a step,
  // and a tall card's share stops moving once it fills the viewport, so a
  // step has to land between "most of the viewport is card" and that
  // plateau. Every 5% does for a card up to eight viewports tall.
  var steps = [];
  for (var i = 0; i <= 20; i++) { steps.push(i / 20); }
  // While the card is seen and its parts run, look each frame for the first
  // to begin: that is the record. The Door's pause simply keeps it looking.
  function look() {
    if (!seen || held) { looking = false; return; }
    if (begun()) { record(); observer.disconnect(); return; }
    requestAnimationFrame(look);
  }
  // Seen means most of the card is in view, or, for a card taller than the
  // viewport can hold that much of, most of the viewport is card. Out of
  // view before a part began there (or after a turn ran unseen before this
  // script looked), the parts are held and rewound, so the turn plays whole
  // the next time the card is seen. The hold is the stylesheet's
  // (data-moment-held pauses the parts) and the rewind a seek: play() and
  // pause() would take the parts from the stylesheet for good, and The
  // Door's pause with them.
  var observer = new IntersectionObserver(function (entries) {
    var entry = entries[0];
    seen = entry.intersectionRatio >= 0.6 ||
      entry.intersectionRect.height >= 0.6 * entry.rootBounds.height;
    if (!seen && !held) {
      held = true;
      card.setAttribute('data-moment-held', '');
      parts().forEach(function (animation) { animation.currentTime = 0; });
    } else if (seen) {
      if (held) {
        held = false;
        card.removeAttribute('data-moment-held');
      }
      if (!looking) {
        looking = true;
        requestAnimationFrame(look);
      }
    }
  }, { threshold: steps });
  observer.observe(card);
})();
