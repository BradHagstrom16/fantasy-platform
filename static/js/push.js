/* Corrupt Commish Club — web push client.
 *
 * On every page: registers the push-only service worker, and on a standalone
 * open bumps last_seen_at + clears the icon badge. On /app: resolves the
 * subscribed / unsubscribed / denied state that the pre-paint script left as
 * "checking", and wires the buzz button, the turn-off link, and the test buzz.
 * Logout is intercepted everywhere so a shared device unsubscribes before the
 * next member signs in.
 */
(function () {
  'use strict';

  if (!('serviceWorker' in navigator)) { return; }

  var el = document.documentElement;
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
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(payload || {})
    });
  }

  function keyBytes() {
    var padding = '='.repeat((4 - (VAPID_KEY.length % 4)) % 4);
    var base64 = (VAPID_KEY + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = window.atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) { out[i] = raw.charCodeAt(i); }
    return out;
  }

  function isStandalone() {
    return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)
      || window.navigator.standalone === true;
  }

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

  function setState(s) { el.setAttribute('data-app-state', s); }

  function status(id, msg, isError) {
    var node = document.getElementById(id);
    if (!node) { return; }
    node.textContent = msg;
    node.classList.toggle('is-error', !!isError);
  }

  function subscribe(reg) {
    return reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes()
    });
  }

  // Bump last_seen_at on every standalone open (pushsubscriptionchange is
  // unreliable, so upsert on open).
  function upsertOnOpen(reg) {
    reg.pushManager.getSubscription().then(function (sub) {
      if (sub) { postJSON('/push/subscribe', subscriptionPayload(sub)); }
    });
  }

  // Resolve the last states the pre-paint script left as "checking".
  function resolveAppState(reg) {
    if (el.getAttribute('data-app-state') !== 'checking') { return; }
    if (Notification.permission === 'denied') { setState('denied'); return; }
    reg.pushManager.getSubscription().then(function (sub) {
      if (sub) { setState('subscribed'); return; }
      if (Notification.permission === 'granted' && canSubscribe()) {
        // Granted but no subscription (revoked/expired) → silently re-subscribe.
        return subscribe(reg)
          .then(function (s) { return postJSON('/push/subscribe', subscriptionPayload(s)); })
          .then(function () { setState('subscribed'); })
          .catch(function () { setState('unsubscribed'); });
      }
      setState('unsubscribed');
    }).catch(function () { setState('unsubscribed'); });
  }

  function restoreCta(btn) {
    btn.removeAttribute('aria-busy');
    btn.disabled = false;
    btn.textContent = 'Turn on the buzz';
  }

  function wireCta(reg) {
    var btn = document.getElementById('push-cta');
    if (!btn) { return; }
    btn.addEventListener('click', function () {
      status('push-status', '', false);
      btn.setAttribute('aria-busy', 'true');
      btn.disabled = true;
      btn.textContent = 'Turning on.';
      Notification.requestPermission().then(function (perm) {
        if (perm === 'denied') { setState('denied'); return; }
        if (perm !== 'granted') { restoreCta(btn); return; }  // dismissed: stay
        return subscribe(reg).then(function (sub) {
          return postJSON('/push/subscribe', subscriptionPayload(sub)).then(function (resp) {
            if (resp.status === 401) { window.location.href = '/login?next=/app'; return; }
            if (!resp.ok) { sub.unsubscribe(); throw new Error('subscribe post failed'); }
            setState('subscribed');
          });
        });
      }).catch(function () {
        // Never leave the phone half-armed: drop the browser subscription.
        reg.pushManager.getSubscription().then(function (s) { if (s) { s.unsubscribe(); } });
        restoreCta(btn);
        status('push-status',
          'Couldn’t turn on the buzz. Try once more; email keeps coming either way.', true);
      });
    });
  }

  function wireTurnOff(reg) {
    var btn = document.getElementById('push-turn-off');
    if (!btn) { return; }
    btn.addEventListener('click', function () {
      reg.pushManager.getSubscription().then(function (sub) {
        var endpoint = sub && sub.endpoint;
        var done = sub ? sub.unsubscribe() : Promise.resolve();
        return done.then(function () {
          if (endpoint) { return postJSON('/push/unsubscribe', { endpoint: endpoint }); }
        });
      }).catch(function () {}).finally(function () {
        setState('unsubscribed');
        status('push-status', 'The buzz is off on this phone.', false);
      });
    });
  }

  function wireTest(reg) {
    var btn = document.getElementById('push-test');
    if (!btn) { return; }
    btn.addEventListener('click', function () {
      btn.disabled = true;
      reg.pushManager.getSubscription().then(function (sub) {
        if (!sub) { status('push-test-status', 'Turn the buzz on first.', false); return; }
        return postJSON('/push/test', { endpoint: sub.endpoint }).then(function (resp) {
          if (resp.ok) {
            status('push-test-status', 'Sent. Lock your phone; it lands in a few seconds.', false);
          } else if (resp.status === 429) {
            status('push-test-status', 'Already sent one. Give it a minute.', false);
          } else {
            status('push-test-status', 'Couldn’t send the test. Email keeps coming either way.', true);
          }
        });
      }).catch(function () {
        status('push-test-status', 'Couldn’t send the test.', true);
      }).finally(function () { btn.disabled = false; });
    });
  }

  function wireLogout() {
    var links = document.querySelectorAll('a.js-logout');
    if (!links.length) { return; }
    links.forEach(function (link) {
      link.addEventListener('click', function (event) {
        var href = link.getAttribute('href');
        event.preventDefault();
        navigator.serviceWorker.ready.then(function (reg) {
          return reg.pushManager.getSubscription();
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

  // Hide the "Get the buzz" distribution links once this device is subscribed.
  function hideBuzzLinkIfSubscribed(reg) {
    var links = document.querySelectorAll('.js-buzz-link');
    if (!links.length) { return; }
    reg.pushManager.getSubscription().then(function (sub) {
      if (sub) { links.forEach(function (n) { n.hidden = true; }); }
    }).catch(function () {});
  }

  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function (reg) {
      if (isStandalone()) {
        upsertOnOpen(reg);
        clearBadge();
      }
      if (document.querySelector('.app-card')) {
        resolveAppState(reg);
        wireCta(reg);
        wireTurnOff(reg);
        wireTest(reg);
      }
      hideBuzzLinkIfSubscribed(reg);
    }).catch(function () { /* registration failed; email still works */ });
    wireLogout();
  });
})();
