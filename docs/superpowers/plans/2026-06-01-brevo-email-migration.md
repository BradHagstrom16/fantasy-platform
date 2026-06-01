# Brevo Email Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move transactional email off Gmail SMTP (port 587, permanently blocked by DigitalOcean) to Brevo's SMTP relay on port 2525, sending DKIM-signed mail from a branded `commish@cccfantasy.com` sender.

**Architecture:** Keep the existing `smtplib` + STARTTLS path in `utils/email.py` intact; the only code change decouples the `From:` header (`MAIL_FROM_ADDRESS`) from the SMTP auth user (`EMAIL_ADDRESS`). All transport changes are config (`.env`). Deliverability comes from Brevo domain authentication (SPF/DKIM/DMARC in Cloudflare DNS). Replies to `commish@` are received via Cloudflare Email Routing forwarding to Brad's Gmail.

**Tech Stack:** Flask, Python `smtplib`, pytest + `unittest.mock`, Brevo (transactional email), Cloudflare (DNS + Email Routing).

---

## Reference: spec

Design spec: `docs/superpowers/specs/2026-06-01-brevo-email-migration-design.md`

## Who does what

- **Tasks 1** (code) — agent/engineer, in-repo, TDD.
- **Tasks 2–6** (Brevo + Cloudflare dashboards, prod `.env`, deploy) — **Brad** performs the
  clicks (the agent cannot reach those dashboards or the production server). The agent
  provides exact steps and sanity-checks the values Brad pastes back **before** he saves DNS.

## Branch note

The port-587 breakage was surfaced during production testing. Memory says prod-test-script
findings batch onto `platform/prod-test-script-fixes-2026-05-29` for one PR. The current
checkout is on `worldcup/production-testing` with unrelated staged spine-doc edits. **Before
Task 1, confirm with Brad** whether the code change rides the prod-test-fixes branch or a
dedicated `platform/brevo-email-migration` branch. The commands below assume a dedicated
branch; adjust the branch name if folding into the prod-test batch.

---

## File Structure

- `utils/email.py` — **modify.** Add `MAIL_FROM_ADDRESS` config read; use it in the `From:`
  header with fallback to `EMAIL_ADDRESS`. One responsibility unchanged: build + send one
  transactional message.
- `tests/test_email.py` — **create.** Unit tests for the `From:`-header set/fallback
  behavior, mocking `smtplib.SMTP` (no network).
- Production `.env` (server-side, not in repo) — **modify.** SMTP host/port/creds + from.

No migrations. No template changes (email HTML already meets the table-layout + inline-style
standard in CLAUDE.md).

---

## Task 1: Decouple the From-address in `utils/email.py` (TDD)

**Files:**
- Modify: `utils/email.py:41-51`
- Create: `tests/test_email.py`

- [ ] **Step 0: Create the branch** (confirm name with Brad first — see Branch note)

```bash
git checkout -b platform/brevo-email-migration
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_email.py`:

```python
"""Tests for utils/email.send_platform_email From-header handling."""
from unittest import mock

from app import create_app
from utils.email import PLATFORM_FROM_NAME, send_platform_email


def _send_and_capture(config_overrides):
    """Run send_platform_email with a mocked SMTP, return the sent message."""
    app = create_app('testing')
    app.config.update(config_overrides)
    captured = {}
    with app.app_context():
        with mock.patch('utils.email.smtplib.SMTP') as MockSMTP:
            server = MockSMTP.return_value.__enter__.return_value
            server.send_message.side_effect = lambda msg: captured.update(msg=msg)
            ok = send_platform_email('player@example.com', 'Subject', 'plain body')
    return ok, captured.get('msg')


def test_from_header_uses_mail_from_address_when_set():
    ok, msg = _send_and_capture({
        'EMAIL_ADDRESS': 'brevo-login@example.com',
        'EMAIL_PASSWORD': 'smtp-key',
        'MAIL_FROM_ADDRESS': 'commish@cccfantasy.com',
    })
    assert ok is True
    assert msg['From'] == f'{PLATFORM_FROM_NAME} <commish@cccfantasy.com>'


def test_from_header_falls_back_to_email_address_when_unset():
    ok, msg = _send_and_capture({
        'EMAIL_ADDRESS': 'fallback@example.com',
        'EMAIL_PASSWORD': 'pw',
        'MAIL_FROM_ADDRESS': None,
    })
    assert ok is True
    assert msg['From'] == f'{PLATFORM_FROM_NAME} <fallback@example.com>'


def test_send_returns_false_when_credentials_missing():
    ok, msg = _send_and_capture({
        'EMAIL_ADDRESS': '',
        'EMAIL_PASSWORD': '',
        'MAIL_FROM_ADDRESS': 'commish@cccfantasy.com',
    })
    assert ok is False
    assert msg is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_email.py -v`
Expected: `test_from_header_uses_mail_from_address_when_set` FAILS — the current code uses
`email_address` in the `From:` header, so it renders `<brevo-login@example.com>`, not
`<commish@cccfantasy.com>`. (The fallback and missing-creds tests may already pass — that's
fine; the first test is the red one driving the change.)

- [ ] **Step 3: Implement the minimal change**

In `utils/email.py`, change the config-read block and the `From:` header line.

Current (lines ~41-51):

```python
    email_address = current_app.config.get('EMAIL_ADDRESS', '')
    email_password = current_app.config.get('EMAIL_PASSWORD', '')
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(current_app.config.get('SMTP_PORT', 587))

    if not email_address or not email_password:
        logger.warning("Email credentials not configured — skipping send to %s", to_addr)
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = f'{PLATFORM_FROM_NAME} <{email_address}>'
```

New:

```python
    email_address = current_app.config.get('EMAIL_ADDRESS', '')
    email_password = current_app.config.get('EMAIL_PASSWORD', '')
    # From-address decouples from the SMTP auth user: Brevo authenticates as the account
    # login but sends from the branded domain sender. Falls back to the auth address so
    # dev/test behavior is unchanged when MAIL_FROM_ADDRESS is absent.
    from_address = current_app.config.get('MAIL_FROM_ADDRESS') or email_address
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(current_app.config.get('SMTP_PORT', 587))

    if not email_address or not email_password:
        logger.warning("Email credentials not configured — skipping send to %s", to_addr)
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = f'{PLATFORM_FROM_NAME} <{from_address}>'
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_email.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the broader suite to confirm no regression**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_asset_versioning.py tests/test_logo_assets.py tests/test_email.py -q`
Expected: all pass (the asset/logo tests touch the reset email and must stay green).

- [ ] **Step 6: Commit**

```bash
git add utils/email.py tests/test_email.py
git commit -m "feat(email): decouple From-address from SMTP auth user

Add MAIL_FROM_ADDRESS config so mail sends from commish@cccfantasy.com
while authenticating as the Brevo relay login. Falls back to
EMAIL_ADDRESS when unset (dev/test unchanged).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Create the Brevo account + start domain authentication (Brad)

**No repo changes.** Goal: get a Brevo account and capture the exact DNS records Brevo wants
for `cccfantasy.com` — but do **not** add them to Cloudflare yet (DNS ordering is handled in
Tasks 3–4 to avoid a double-SPF record).

- [ ] **Step 1: Sign up**

Go to <https://www.brevo.com>, create a free account using `bhagstrom0@gmail.com`. Complete
the onboarding (company name "Corrupt Commish Club"; choose the **Free** plan — 300
emails/day). Brevo may ask a few sender-reputation questions; answer truthfully (transactional
app email for a sports pool).

- [ ] **Step 2: Open domain authentication**

In the Brevo dashboard: **Senders, Domains & Dedicated IPs** → **Domains** tab → **Add a
domain** → enter `cccfantasy.com` → choose "I want to use it to send emails / authenticate".

- [ ] **Step 3: Capture the records Brevo displays**

Brevo will show a set of DNS records to add. Typically:
- a **Brevo code** TXT record on the root (e.g. host `@`, value `brevo-code:xxxxxxxxxxxx`),
- a **DKIM** record (a TXT record at host `brevo1._domainkey` / `brevo2._domainkey` **or** a
  single `mail._domainkey` TXT with a long `k=rsa; p=...` value — Brevo's exact host/format
  varies by account),
- an **SPF** include (`include:spf.brevo.com`),
- optionally a **DMARC** TXT at `_dmarc`.

Copy each record's **Type, Host/Name, and exact Value** verbatim (use Brevo's copy buttons).
**Paste them back to the agent before editing Cloudflare** — the agent will confirm host
naming and, critically, how to merge SPF with Cloudflare Email Routing's SPF (Task 4) so you
publish exactly one SPF record. Leave the Brevo verification screen open.

---

## Task 3: Enable Cloudflare Email Routing for replies (Brad)

**No repo changes.** Do this **before** adding Brevo's SPF so Cloudflare creates the base SPF
record, then Task 4 merges Brevo into it (deterministic single SPF record).

- [ ] **Step 1: Enable Email Routing**

Cloudflare dashboard → select `cccfantasy.com` → left sidebar **Email** → **Email Routing**
→ **Get started / Enable**. Cloudflare will offer to **automatically add** the required `MX`
records and a routing `TXT` (SPF `v=spf1 include:_spf.mx.cloudflare.net ~all`). Accept —
let Cloudflare add them.

- [ ] **Step 2: Add the custom address**

Under **Email Routing → Routing rules → Custom addresses → Create address**:
- Custom address: `commish@cccfantasy.com`
- Action: **Send to an email**
- Destination: `bhagstrom0@gmail.com`

- [ ] **Step 3: Verify the destination**

Cloudflare emails `bhagstrom0@gmail.com` a verification link. Click it. The destination
shows **Verified** in **Email Routing → Destination addresses**.

- [ ] **Step 4: Confirm the SPF record Cloudflare created**

In **DNS → Records**, find the `TXT` record beginning `v=spf1`. Note its exact current value
(should be `v=spf1 include:_spf.mx.cloudflare.net ~all`). **Paste it to the agent** — Task 4
edits this same record rather than adding a second SPF.

---

## Task 4: Add Brevo DNS records in Cloudflare + verify (Brad)

**No repo changes.** Uses the values captured in Task 2 and the existing SPF from Task 3.
**Do not save the SPF edit until the agent confirms the merged value.**

- [ ] **Step 1: Add the Brevo code TXT**

DNS → Records → **Add record**: Type `TXT`, Name `@` (root), Content = Brevo's
`brevo-code:...` value. Proxy status is N/A for TXT. Save.

- [ ] **Step 2: Add the DKIM record(s)**

Add exactly what Brevo showed (host + value verbatim) — one or two TXT/`_domainkey` records.
For a long `k=rsa; p=...` value, paste the **entire** string; do not insert line breaks.
Cloudflare accepts the full value in one Content field. Save each.

- [ ] **Step 3: Merge SPF (single record — critical)**

Edit the **existing** SPF TXT record from Task 3 (do **not** add a second `v=spf1` record).
Insert Brevo's include before the closing `~all`. Target value:

```
v=spf1 include:spf.brevo.com include:_spf.mx.cloudflare.net ~all
```

**Before saving, paste your intended final SPF value to the agent for confirmation** (order
of includes does not matter; having exactly one `v=spf1` record does). Save.

- [ ] **Step 4: Add DMARC (if Brevo provided one, else this baseline)**

If Brevo gave a DMARC value, use it. Otherwise add: Type `TXT`, Name `_dmarc`, Content:

```
v=DMARC1; p=none; rua=mailto:commish@cccfantasy.com
```

(`p=none` = monitor only; safe starting policy. Reports route to the now-receivable
`commish@` address.) Save.

- [ ] **Step 5: Verify in Brevo**

Back in the Brevo domain screen, click **Verify / Authenticate**. DNS can take a few minutes
to propagate (Cloudflare is usually fast). All of SPF, DKIM, and the Brevo code should turn
green. If DKIM stays unverified after ~15 min, re-check the host name matches Brevo's exactly
(a common slip is Cloudflare auto-appending the zone — `brevo1._domainkey` not
`brevo1._domainkey.cccfantasy.com.cccfantasy.com`). Report status to the agent.

---

## Task 5: Generate the SMTP key + set production `.env` + deploy (Brad)

**No repo changes** (the `.env` is server-side, not committed). Requires Task 1 merged/pushed
and Task 4 verified.

- [ ] **Step 1: Generate a Brevo SMTP key**

Brevo dashboard → **SMTP & API** → **SMTP** tab. Note the **SMTP server** (`smtp-relay.brevo.com`),
the **login** (your Brevo account email), and **Generate a new SMTP key**. Copy the key (shown
once).

- [ ] **Step 2: Edit the production `.env`**

```bash
ssh deploy@104.131.28.136
cd /home/deploy/fantasy-platform
nano .env
```

Set/replace these keys (keep `ENVIRONMENT=production` and all other keys untouched):

```
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=2525
EMAIL_ADDRESS=<your brevo account login email>
EMAIL_PASSWORD=<the brevo SMTP key from Step 1>
MAIL_FROM_ADDRESS=commish@cccfantasy.com
```

Save (`Ctrl+O`, `Enter`, `Ctrl+X`).

- [ ] **Step 3: Deploy**

The code change (Task 1) must be on `main` first. From local:

```bash
git checkout main && git pull
git merge platform/brevo-email-migration   # or merge via PR, per your normal flow
git push origin main
```

Then on the server:

```bash
./deploy.sh
```

`deploy.sh` runs `git pull` → `pip install` → `flask db upgrade` (no-op here, no migrations)
→ `systemctl restart`. The restart reloads the new `.env`.

---

## Task 6: Verify end-to-end (Brad, with agent sanity-checks)

- [ ] **Step 1: Local DKIM smoke (optional, fastest signal before prod)**

From the local repo with a throwaway script, send one email through Brevo to
`bhagstrom0@gmail.com`. Run in a Python shell with the Brevo creds exported:

```bash
EMAIL_ADDRESS='<brevo login>' EMAIL_PASSWORD='<brevo smtp key>' \
MAIL_FROM_ADDRESS='commish@cccfantasy.com' \
SMTP_SERVER='smtp-relay.brevo.com' SMTP_PORT='2525' \
ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    import os
    app.config.update({k: os.environ[k] for k in
        ('EMAIL_ADDRESS','EMAIL_PASSWORD','MAIL_FROM_ADDRESS','SMTP_SERVER','SMTP_PORT')})
    from utils.email import send_platform_email
    print('sent:', send_platform_email('bhagstrom0@gmail.com',
        'Brevo smoke test', 'plain body', '<p>html body</p>'))
"
```

Expected: `sent: True`. (Local dev does NOT have port 587 blocked, but using 2525 here
exercises the real relay path.)

- [ ] **Step 2: Confirm DKIM/SPF pass**

In Gmail, open the test email → **⋮ → Show original**. Confirm:
- **DKIM: 'PASS' with domain cccfantasy.com**
- **SPF: 'PASS'**
- The **From** shows `Corrupt Commish Club <commish@cccfantasy.com>`.

If DKIM shows the Brevo domain instead of `cccfantasy.com`, domain authentication didn't fully
verify — recheck Task 4 Step 5.

- [ ] **Step 3: Reply test**

Reply to the test email. Confirm the reply lands in `bhagstrom0@gmail.com` (via Cloudflare
Email Routing). This proves the replyable address works end-to-end.

- [ ] **Step 4: Production password-reset verification**

After deploy (Task 5), on cccfantasy.com use **Forgot password** for your own account.
Confirm the reset email:
- arrives in the **inbox** (not spam/Promotions),
- is from `commish@cccfantasy.com`,
- the reset link works.

- [ ] **Step 5: Update CLAUDE.md production-ops note**

Add a short line to the **Production ops** section of `CLAUDE.md` recording that outbound mail
goes through Brevo SMTP relay (`smtp-relay.brevo.com:2525`, DO blocks 587), from
`commish@cccfantasy.com`, DKIM-signed via Cloudflare DNS, with `commish@` replies received via
Cloudflare Email Routing. Commit:

```bash
git add CLAUDE.md
git commit -m "docs(ops): record Brevo SMTP-relay email setup

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done when

- `tests/test_email.py` passes (3 tests) and the broader suite is green.
- A production password-reset email arrives in the inbox from `commish@cccfantasy.com`,
  DKIM-PASS signed by `cccfantasy.com`.
- A reply to that address forwards to `bhagstrom0@gmail.com`.
- CLAUDE.md records the new mail path.
