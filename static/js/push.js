/* Corrupt Commish Club — web push client.
 *
 * Registers the push-only service worker, wires the /app "Turn on the buzz"
 * button, bumps last_seen_at + clears the icon badge on every app open, and
 * intercepts logout so a shared device unsubscribes before the next member
 * signs in. PR 1 scope; PR 2 adds the full /app state machine on top.
 */
(function () {
  'use strict';

  if (!('serviceWorker' in navigator)) { return; }

  var VAPID_KEY = (document.body && document.body.dataset)
    ? (document.body.dataset.vapidKey || '') : '';

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function postJSON(url, payload) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      body: JSON.stringify(payload || {})
    });
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = window.atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) { out[i] = raw.charCodeAt(i); }
    return out;
  }

  function isStandalone() {
    return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)
      || window.navigator.standalone === true;
  }

  // The device can subscribe if the APIs exist and we have a key. On iOS the
  // Notification API is exposed only to the installed (standalone) web app; on
  // Android it exists in the browser tab too, so feature detection is the gate.
  function canSubscribe() {
    return VAPID_KEY && ('PushManager' in window) && ('Notification' in window);
  }

  function clearBadge() {
    if (navigator.clearAppBadge) { navigator.clearAppBadge().catch(function () {}); }
  }

  function subscriptionPayload(sub) {
    var json = sub.toJSON();
    return { endpoint: sub.endpoint, keys: json.keys };
  }

  // Bump last_seen_at (pushsubscriptionchange is unreliable, so upsert on open).
  function upsertOnOpen(reg) {
    reg.pushManager.getSubscription().then(function (sub) {
      if (sub) { postJSON('/push/subscribe', subscriptionPayload(sub)); }
    });
  }

  function setStatus(msg) {
    var el = document.getElementById('push-status');
    if (el) { el.textContent = msg; }
  }

  function wireButton(reg) {
    var wrap = document.getElementById('push-cta-wrap');
    var btn = document.getElementById('push-cta');
    if (!wrap || !btn) { return; }
    if (!canSubscribe()) { return; }
    wrap.hidden = false;

    btn.addEventListener('click', function () {
      // requestPermission MUST run inside the tap handler.
      Notification.requestPermission().then(function (perm) {
        if (perm !== 'granted') {
          setStatus('The buzz is blocked on this phone. You can allow it in Settings.');
          return;
        }
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_KEY)
        }).then(function (sub) {
          return postJSON('/push/subscribe', subscriptionPayload(sub)).then(function (resp) {
            if (resp.ok) {
              setStatus('The buzz is on. See you Saturday.');
            } else {
              // Never leave the phone half-armed.
              sub.unsubscribe();
              setStatus('Couldn’t turn on the buzz. Try once more; email keeps coming either way.');
            }
          });
        });
      }).catch(function () {
        setStatus('Couldn’t turn on the buzz. Try once more; email keeps coming either way.');
      });
    });
  }

  function wireLogout() {
    var links = document.querySelectorAll('a.js-logout');
    if (!links.length) { return; }
    links.forEach(function (link) {
      link.addEventListener('click', function (event) {
        var href = link.getAttribute('href');
        if (!('serviceWorker' in navigator)) { return; }
        event.preventDefault();
        // getRegistration (not .ready): .ready never resolves when no worker is
        // active, which would hang this preventDefault()'d logout forever.
        navigator.serviceWorker.getRegistration().then(function (reg) {
          return reg ? reg.pushManager.getSubscription() : null;
        }).then(function (sub) {
          if (!sub) { return null; }
          var endpoint = sub.endpoint;
          return sub.unsubscribe().catch(function () {}).then(function () {
            return postJSON('/push/unsubscribe', { endpoint: endpoint }).catch(function () {});
          });
        }).catch(function () {}).finally(function () {
          window.location.href = href;
        });
      });
    });
  }

  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function (reg) {
      wireButton(reg);
      // Refresh last_seen_at on every open — including a browser tab, where
      // Android subscribes — so in-tab subscriptions aren't the unfair eviction
      // target. The icon badge only exists for the installed app.
      upsertOnOpen(reg);
      if (isStandalone()) { clearBadge(); }
    }).catch(function () { /* registration failed; email still works */ });
    wireLogout();
  });
})();
