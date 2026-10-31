/* Corrupt Commish Club — the slips on a headliner's slot board (Brad, 2026-10-30).
 *
 * A held tile on the lounge board reads back its pick in a slip under the
 * board. A mouse previews the slip on hover; a click or tap pins it, the
 * same tile again closes it, another tile moves it. Esc and a press outside
 * the board close it. The held tiles are one tab stop (a toolbar's roving
 * tabindex): the arrows, Home and End move along them, and an open slip
 * follows. Without this script the board is the plain board, and the
 * group's label still says the whole sentence.
 */
(function () {
  'use strict';

  function wire(wrap) {
    var tiles = Array.prototype.slice.call(wrap.querySelectorAll('button.hl-tile'));
    if (!tiles.length) { return; }
    var shown = null;     // the tile whose slip is showing
    var pinned = false;   // shown by a click, tap or key, not a hover

    function slipFor(tile) {
      return document.getElementById(tile.getAttribute('data-slip'));
    }

    // The server sends the tiles inert; only a wired board is a control.
    wrap.querySelector('.hl-board').setAttribute('role', 'toolbar');
    tiles.forEach(function (tile) {
      tile.inert = false;
      tile.setAttribute('aria-controls', tile.getAttribute('data-slip'));
      tile.setAttribute('aria-expanded', 'false');
      // A tap on the open slip clears it, so it never sits over the action
      // under it. On click, not pointerdown: the tap ends on the slip and
      // cannot fall through to the link beneath.
      slipFor(tile).addEventListener('click', hide);
    });
    wrap.classList.add('is-wired');

    function place(tile) {
      slipFor(tile).style.setProperty('--notch', (tile.offsetLeft + tile.offsetWidth / 2) + 'px');
    }

    function hide() {
      if (!shown) { return; }
      var slip = slipFor(shown);
      slip.hidden = true;
      slip.classList.remove('is-swap');
      shown.setAttribute('aria-expanded', 'false');
      shown = null;
      pinned = false;
    }

    function show(tile, pin) {
      if (shown === tile) { pinned = pinned || pin; return; }
      // Moving from one open slip to the next swaps it in place; only a
      // slip opening from nothing plays the entrance.
      var swap = shown !== null;
      hide();
      var slip = slipFor(tile);
      slip.classList.toggle('is-swap', swap);
      place(tile);
      slip.hidden = false;
      tile.setAttribute('aria-expanded', 'true');
      shown = tile;
      pinned = pin;
    }

    function rove(tile) {
      tiles.forEach(function (t) { t.tabIndex = t === tile ? 0 : -1; });
    }

    rove(tiles[0]);

    tiles.forEach(function (tile, index) {
      tile.addEventListener('pointerenter', function (event) {
        if (event.pointerType === 'mouse' && !pinned) { show(tile, false); }
      });
      tile.addEventListener('click', function () {
        if (shown === tile && pinned) { hide(); } else { show(tile, true); }
      });
      tile.addEventListener('focus', function () { rove(tile); });
      tile.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight') { next = tiles[(index + 1) % tiles.length]; }
        else if (event.key === 'ArrowLeft') { next = tiles[(index - 1 + tiles.length) % tiles.length]; }
        else if (event.key === 'Home') { next = tiles[0]; }
        else if (event.key === 'End') { next = tiles[tiles.length - 1]; }
        if (!next) { return; }
        event.preventDefault();
        next.focus();
        if (shown) { show(next, true); }
      });
    });

    wrap.addEventListener('pointerleave', function (event) {
      if (event.pointerType === 'mouse' && !pinned) { hide(); }
    });
    document.addEventListener('pointerdown', function (event) {
      if (shown && !wrap.contains(event.target)) { hide(); }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && shown) { hide(); }
    });
    window.addEventListener('resize', function () {
      if (shown) { place(shown); }
    });
    // Leave the lounge with the board at rest, so Back restores it closed.
    window.addEventListener('pagehide', hide);
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-hl-board]'), wire);
})();
