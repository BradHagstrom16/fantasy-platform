/* The Record Room: "Play the season" for the season race.
 *
 * Enhancement only. The server draws the finished race (every line, the final
 * standings); this script shows the controls and lets a member play or scrub
 * the season week by week. A playhead crosses the plot, the lines are revealed
 * up to it, a dot rides your line and the leader's, and the standings below
 * re-order in competition rank, so the lead changing hands is something you
 * watch happen. Nothing moves until the member asks.
 *
 * No payload, no script, or a one-event season: nothing runs and the still
 * chart stands on its own.
 */
(function () {
  'use strict';

  // How long the playhead glides between events, and how long it rests on each.
  var GLIDE_MS = 520;
  var DWELL_MS = 220;
  var STRIDE_MS = GLIDE_MS + DWELL_MS;

  function init() {
    var figure = document.querySelector('[data-race]');
    var dataEl = document.querySelector('[data-race-data]');
    if (!figure || !dataEl) return;

    var data;
    try {
      data = JSON.parse(dataEl.textContent);
    } catch (e) {
      return; // a malformed payload leaves the still chart untouched
    }
    if (!data || !data.count || data.count < 2) return;

    var width = data.width;
    var height = data.height;
    var events = data.events;
    var lines = data.lines;
    var lastIndex = data.count - 1;

    var reduceMotion = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var clipRect = figure.querySelector('[data-race-clip]');
    var playhead = figure.querySelector('[data-race-playhead]');
    var playBtn = figure.querySelector('[data-race-play]');
    var scrubWrap = figure.querySelector('[data-race-scrub-wrap]');
    var scrub = figure.querySelector('[data-race-scrub]');
    var readout = figure.querySelector('[data-race-readout]');
    var standings = document.querySelector('[data-race-standings]');
    if (!clipRect || !playhead || !standings) return;

    var batons = {};
    Array.prototype.forEach.call(figure.querySelectorAll('[data-race-baton]'), function (el) {
      batons[el.getAttribute('data-race-baton')] = el;
    });
    // The line each dot rides. A shared lead has several ink lines; the dot
    // takes the first, the one the server named.
    var lineByRole = {};
    lines.forEach(function (line) { if (!lineByRole[line.role]) lineByRole[line.role] = line; });
    var viewerId = lineByRole.you ? String(lineByRole.you.user_id) : null;

    var rows = {};
    Array.prototype.forEach.call(standings.querySelectorAll('[data-race-row]'), function (row) {
      rows[row.getAttribute('data-user-id')] = {
        row: row,
        rank: row.querySelector('[data-race-rank]'),
        value: row.querySelector('[data-race-value]')
      };
    });

    function money(n) { return '$' + Math.round(n).toLocaleString('en-US'); }
    function easeOutQuart(t) { return 1 - Math.pow(1 - t, 4); }
    function lerp(a, b, f) { return a + (b - a) * f; }

    // The room after event k, in the sheet's order (total, then name) and in
    // competition rank: ties share a rank ("T2") and the next one gaps.
    function orderingAt(k) {
      var order = lines.map(function (line) {
        return { id: String(line.user_id), value: line.cumulative[k], name: line.name };
      });
      order.sort(function (a, b) {
        return b.value - a.value || a.name.toLowerCase().localeCompare(b.name.toLowerCase());
      });
      var shared = {};
      order.forEach(function (entry, i) {
        entry.rank = i && entry.value === order[i - 1].value ? order[i - 1].rank : i + 1;
        shared[entry.rank] = (shared[entry.rank] || 0) + 1;
      });
      order.forEach(function (entry) {
        entry.label = (shared[entry.rank] > 1 ? 'T' : '') + entry.rank;
      });
      return order;
    }

    // Who leads after event k, in words: the lead changing hands is said
    // beside the plot, not only in the standings under it.
    function leadAt(k) {
      var order = orderingAt(k);
      if (!order[0].value) return '';
      var top = order.filter(function (entry) { return entry.rank === 1; });
      if (top.length > 1) return ' ' + top.length + ' tied for the lead.';
      return top[0].id === viewerId ? ' You lead.' : ' ' + top[0].name + ' leads.';
    }

    function setValue(el, from, to, dur) {
      if (el._raf) { cancelAnimationFrame(el._raf); el._raf = null; }
      if (reduceMotion || dur <= 0 || from === to) { el.textContent = money(to); return; }
      var start = performance.now();
      function tick(now) {
        var t = Math.min(1, (now - start) / dur);
        el.textContent = money(from + (to - from) * easeOutQuart(t));
        el._raf = t < 1 ? requestAnimationFrame(tick) : null;
      }
      el._raf = requestAnimationFrame(tick);
    }

    var cumulativeById = {};
    lines.forEach(function (line) { cumulativeById[String(line.user_id)] = line.cumulative; });

    var displayed = lastIndex; // the event the standings show

    // Re-order the standings for event k: first positions, the new order, then
    // each row slides from where it was (FLIP).
    function applyStandings(k, fromK, animate) {
      var order = orderingAt(k);
      var firstTop = {};
      order.forEach(function (entry) {
        firstTop[entry.id] = rows[entry.id].row.getBoundingClientRect().top;
      });
      order.forEach(function (entry) { standings.appendChild(rows[entry.id].row); });
      order.forEach(function (entry) {
        var item = rows[entry.id];
        if (animate && !reduceMotion) {
          var dy = firstTop[entry.id] - item.row.getBoundingClientRect().top;
          if (dy) {
            item.row.style.transition = 'none';
            item.row.style.transform = 'translateY(' + dy + 'px)';
            item.row.getBoundingClientRect(); // reflow, so the slide starts from here
            item.row.style.transition = '';
            item.row.style.transform = '';
          }
        } else {
          item.row.style.transform = '';
        }
        item.rank.textContent = entry.label;
        setValue(item.value, cumulativeById[entry.id][fromK], entry.value, animate ? 420 : 0);
      });
    }

    var playing = false;
    var rafId = null;
    var startTime = 0;

    // Draw progress p (0 to lastIndex, fractional between events).
    function render(p, animateStandings) {
      var k0 = Math.floor(p);
      var k1 = Math.min(k0 + 1, lastIndex);
      var f = p - k0;
      var x = lerp(events[k0].x, events[k1].x, f);
      var settled = p >= lastIndex - 1e-6;
      var atFinal = settled && !playing;

      clipRect.setAttribute('width', (settled ? width : x).toFixed(1));
      playhead.setAttribute('x1', x.toFixed(1));
      playhead.setAttribute('x2', x.toFixed(1));

      ['leader', 'you'].forEach(function (role) {
        var baton = batons[role];
        var line = lineByRole[role];
        if (!baton || !line) return;
        var y = lerp(line.coords[k0][1], line.coords[k1][1], f);
        baton.style.setProperty('--x', (100 * x / width).toFixed(2) + '%');
        baton.style.setProperty('--y', (100 * y / height).toFixed(2) + '%');
      });

      var idx = Math.round(p);
      if (readout) {
        readout.textContent = atFinal
          ? 'Through ' + events[idx].the
          : 'After ' + events[idx].the + ' (' + (idx + 1) + ' of ' + data.count + ').' + leadAt(idx);
      }
      if (scrub) scrub.value = idx;
      figure.classList.toggle('golf-race--scrubbing', !atFinal);

      if (idx !== displayed) {
        applyStandings(idx, displayed, animateStandings);
        displayed = idx;
      }
    }

    var total = lastIndex * STRIDE_MS + DWELL_MS;

    function progressAt(t) {
      var e = Math.floor(t / STRIDE_MS);
      if (e >= lastIndex) return lastIndex;
      var local = t - e * STRIDE_MS;
      if (local <= DWELL_MS) return e;
      return e + easeOutQuart((local - DWELL_MS) / GLIDE_MS);
    }

    function setPlayLabel(isPlaying) {
      if (playBtn) playBtn.textContent = isPlaying ? 'Pause' : 'Play the season';
    }

    function stopPlay() {
      playing = false;
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      setPlayLabel(false);
    }

    function frame(now) {
      var t = now - startTime;
      // Stop first, so the last render sees the race at rest.
      if (t >= total) { stopPlay(); render(lastIndex, true); return; }
      render(progressAt(t), true);
      rafId = requestAnimationFrame(frame);
    }

    function startPlay() {
      playing = true;
      setPlayLabel(true);
      render(0, false); // back to the first tee
      startTime = performance.now();
      rafId = requestAnimationFrame(frame);
    }

    if (playBtn) {
      playBtn.addEventListener('click', function () {
        if (playing) { stopPlay(); render(displayed, false); }
        else { startPlay(); }
      });
    }

    if (scrub) {
      scrub.addEventListener('input', function () {
        if (playing) stopPlay();
        var k = parseInt(scrub.value, 10) || 0;
        scrub.setAttribute('aria-valuetext', events[k].name);
        render(k, false); // a hand on the slider: no glide
      });
    }

    // The slider's track lines up with the plot, so its thumb sits on the events.
    if (scrub && scrubWrap) {
      scrubWrap.style.setProperty('--pad-left', (100 * data.pad_left / width) + '%');
      scrubWrap.style.setProperty('--pad-right', (100 * data.pad_right / width) + '%');
      scrubWrap.removeAttribute('hidden');
    }
    // Under reduced motion the season does not play; the slider still steps it.
    if (playBtn && !reduceMotion) playBtn.removeAttribute('hidden');

    render(lastIndex, false); // the state the server drew
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
