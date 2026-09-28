"""
utils/job_alert.py
==================
What a scheduled job's exit tells someone. Run by two systemd templates, never
by hand in production:

    deploy/job-alert@.service   OnFailure=  ->  python -m utils.job_alert fail <unit>
    deploy/job-ping@.service    OnSuccess=  ->  python -m utils.job_alert ok <unit>

`<unit>` is the job's name without `.service` (systemd's %N), e.g. docket-scores.

fail: ping healthchecks.io's /fail for the job, then email the admin inbox the
      job's last journal lines. The ping goes first and over a separate path, so
      a failure still reaches Brad when our own mail (Brevo) is what broke.
ok:   ping healthchecks.io for the job. That is the dead-man half: healthchecks
      alerts when a job stops checking in on its schedule, which catches the
      failures OnFailure= cannot see (a timer disabled by mistake, a box that
      is down, a systemd that never fired).

Imports only config, Flask and utils.email, never `app` or a game: a deploy
that breaks the app's import fails every job, and this must still report it.
A blank HEALTHCHECKS_PING_KEY skips the pings; the email still goes.
"""
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from flask import Flask

from config import config
from utils.email import send_platform_email

logger = logging.getLogger(__name__)

PING_BASE = 'https://hc-ping.com'
JOURNAL_LINES = 40


def ping(ping_key, unit, *, fail=False, attempts=3, backoff=2):
    """Tell healthchecks.io the job ran (or failed). Never raises.

    `?create=1` makes the first ping for a new job create its check, so adding a
    timer needs no dashboard step before its schedule is set there. A dropped
    ping of a weekly job would read as a missed run for a whole week, so it
    retries a few times (healthchecks.io's own advice); three 10 s attempts and
    their pauses fit inside job-ping@'s 1-minute TimeoutStartSec.
    """
    if not ping_key:
        return False
    url = f'{PING_BASE}/{ping_key}/{unit}{"/fail" if fail else ""}?create=1'
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                # 201 Created is the answer to the ping that auto-creates a
                # new check (`?create=1`); both mean the ping landed.
                if 200 <= resp.status < 300:
                    return True
                reason = f'HTTP {resp.status}'
        except (urllib.error.URLError, OSError) as exc:
            reason = str(exc)
        # The key is in the URL, so log the job and the reason, never the URL.
        logger.warning('healthchecks ping for %s failed (attempt %d/%d): %s',
                       unit, attempt, attempts, reason)
        if attempt < attempts:
            time.sleep(backoff * attempt)
    return False


def journal_tail(unit):
    """The job's last journal lines, or why they could not be read."""
    try:
        result = subprocess.run(
            ['journalctl', '-u', f'{unit}.service', '-n', str(JOURNAL_LINES),
             '--no-pager', '-o', 'short-iso'],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f'(could not read the journal: {exc})'
    return result.stdout.strip() or f'(journalctl printed nothing: {result.stderr.strip()})'


def failure_letter(unit, journal):
    """Subject and plain-text body of the failure alert (admin mail stays plain)."""
    subject = f'[CCC ops] {unit} failed'
    body = (
        f'{unit}.service exited with a failure on the droplet.\n\n'
        f'Last {JOURNAL_LINES} journal lines:\n\n{journal}\n\n'
        f'Full log:  journalctl -u {unit}.service -n 200 --no-pager\n'
        f'Re-run:    sudo systemctl start {unit}.service\n'
    )
    return subject, body


def _app():
    """A bare Flask app carrying the config: all send_platform_email needs."""
    app = Flask(__name__)
    app.config.from_object(config[os.environ.get('ENVIRONMENT', 'default')])
    return app


def main(argv):
    if len(argv) != 3 or argv[1] not in ('fail', 'ok'):
        print('usage: python -m utils.job_alert {fail|ok} <unit-name>', file=sys.stderr)
        return 2
    mode, unit = argv[1], argv[2]
    app = _app()
    ping_key = app.config['HEALTHCHECKS_PING_KEY']

    if mode == 'ok':
        ping(ping_key, unit)
        return 0

    ping(ping_key, unit, fail=True)
    recipient = app.config['ADMIN_EMAIL'] or app.config['EMAIL_ADDRESS']
    if not recipient:
        print(f'{unit} failed, and no ADMIN_EMAIL/EMAIL_ADDRESS is set to tell.',
              file=sys.stderr)
        return 1
    subject, body = failure_letter(unit, journal_tail(unit))
    with app.app_context():
        sent = send_platform_email(recipient, subject, body)
    print(f'{unit} failure alert {"sent" if sent else "NOT sent"} to the admin inbox.')
    return 0 if sent else 1


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv))
