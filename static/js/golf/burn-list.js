/* The Record Room: the Burn List's search.
 *
 * Enhancement only: without this script every burned golfer is listed. With
 * it the list opens on its first rows, "Show all" opens the rest, and typing
 * a name searches every row. The fold below is the same one
 * games/golf/services/field.py::search_key writes into each row's
 * data-search ("jj" finds "J.J.", "hojgaard" finds "Højgaard"); the two
 * change together.
 */
(function () {
  'use strict';

  var FIRST = 12; // rows shown before "Show all"

  function fold(text) {
    return text.toLowerCase()
      .replace(/ø/g, 'o').replace(/æ/g, 'ae').replace(/œ/g, 'oe')
      .replace(/ł/g, 'l').replace(/đ/g, 'd').replace(/ß/g, 'ss')
      .normalize('NFKD').replace(/[^a-z0-9]/g, '');
  }

  function init() {
    var list = document.querySelector('[data-burn-list]');
    var input = document.getElementById('golf-burn-search');
    if (!list || !input) return;

    var rows = Array.prototype.slice.call(list.querySelectorAll('[data-row]'));
    var wrap = document.querySelector('[data-burn-search-wrap]');
    var count = document.querySelector('[data-burn-count]');
    var none = document.querySelector('[data-burn-none]');
    var query = document.querySelector('[data-burn-query]');
    var more = document.querySelector('[data-burn-more]');
    var clear = document.querySelector('[data-burn-clear]');
    var all = rows.length <= FIRST;

    function plural(n) { return n + (n === 1 ? ' golfer' : ' golfers'); }

    function draw() {
      var words = input.value.split(/\s+/).map(fold).filter(Boolean);
      var shown = 0;
      rows.forEach(function (row, i) {
        var key = row.getAttribute('data-search');
        var match = words.every(function (word) { return key.indexOf(word) !== -1; });
        var visible = words.length ? match : (all || i < FIRST);
        row.hidden = !visible;
        if (words.length ? match : true) shown += 1;
      });
      if (words.length) {
        count.textContent = shown + ' of ' + rows.length + ' match';
      } else {
        count.textContent = plural(rows.length) + ' spent';
      }
      list.hidden = words.length > 0 && shown === 0;
      if (none) {
        none.hidden = !(words.length > 0 && shown === 0);
        if (query) query.textContent = input.value.trim();
      }
      if (more) more.hidden = all || words.length > 0;
    }

    input.addEventListener('input', draw);
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && input.value) { input.value = ''; draw(); }
    });
    if (more) {
      more.textContent = 'Show all ' + rows.length;
      more.addEventListener('click', function () {
        all = true;
        draw();
        // The button is gone: hand focus to the first row it opened.
        if (rows[FIRST]) {
          rows[FIRST].setAttribute('tabindex', '-1');
          rows[FIRST].focus();
        }
      });
    }
    if (clear) {
      clear.addEventListener('click', function () {
        input.value = '';
        draw();
        input.focus();
      });
    }

    if (wrap) wrap.hidden = false;
    draw();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
