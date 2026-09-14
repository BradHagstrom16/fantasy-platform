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

  // A followed login redirect (302 -> /login) or any non-ok response is NOT a
  // genuine API success even though fetch reports resp.ok. Resolve true only for
  // a same-origin, non-redirected {ok:true} JSON body.
  function postedOk(resp) {
    if (resp.redirected || !resp.ok) { return Promise.resolve(false); }
    return resp.json().then(function (j) { return !!(j && j.ok); },
                            function () { return false; });
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
      // Best-effort heartbeat: validate the response so a lapsed session no
      // longer reads as success, but never flip state or drop the local sub —
      // the user stays subscribed pending re-auth.
      if (sub) { postJSON('/push/subscribe', subscriptionPayload(sub)).then(postedOk); }
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
        // Background path: any failure (incl. a lapsed session) falls back to
        // unsubscribed without a jarring redirect, dropping the orphan sub.
        return subscribe(reg).then(function (s) {
          return postJSON('/push/subscribe', subscriptionPayload(s))
            .then(postedOk)
            .then(function (ok) {
              if (ok) { setState('subscribed'); return; }
              s.unsubscribe().catch(function () {});
              setState('unsubscribed');
            });
        }).catch(function () { setState('unsubscribed'); });
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
            // Interactive path: a lapsed session (followed 302 → /login) routes
            // to sign-in; any other failure drops the sub and throws to the
            // catch below for the retry message.
            if (resp.redirected) {
              sub.unsubscribe().catch(function () {});
              window.location.href = '/login?next=/app';
              return;
            }
            return postedOk(resp).then(function (ok) {
              if (ok) { setState('subscribed'); return; }
              sub.unsubscribe().catch(function () {});
              throw new Error('subscribe post failed');
            });
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
      // Only report "off" when BOTH local unsubscribe and server cleanup
      // succeed — a lapsed session (followed 302) or a false unsubscribe() is
      // a failure, not a silent success.
      reg.pushManager.getSubscription().then(function (sub) {
        if (!sub) { return true; }  // nothing local to clear → already off
        var endpoint = sub.endpoint;
        return sub.unsubscribe().then(function (dropped) {
          if (!dropped) { return false; }
          return postJSON('/push/unsubscribe', { endpoint: endpoint }).then(function (resp) {
            return !resp.redirected && resp.ok;
          });
        });
      }).then(function (ok) {
        if (ok) {
          setState('unsubscribed');
          status('push-status', 'The buzz is off on this phone.', false);
        } else {
          status('push-status', 'Couldn’t turn the buzz off. Try once more.', true);
        }
      }).catch(function () {
        status('push-status', 'Couldn’t turn the buzz off. Try once more.', true);
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
          // A followed login redirect reports resp.ok=true; only a genuine,
          // non-redirected 200 means the test actually sent.
          if (resp.ok && !resp.redirected) {
            status('push-test-status', 'Sent. Lock your phone; it lands in a few seconds.', false);
          } else if (resp.status === 429) {  // rate-limited; never redirected
            status('push-test-status', 'Already sent one. Give it a minute.', false);
          } else if (resp.redirected) {
            status('push-test-status', 'Please sign in again to send the test.', false);
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
        // getRegistration() (not .ready) so logout still completes when no
        // worker is active — .ready never resolves without one, hanging the nav.
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
