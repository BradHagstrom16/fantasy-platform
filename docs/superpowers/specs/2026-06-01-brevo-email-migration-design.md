# Brevo Email Migration — Design

**Date:** 2026-06-01
**Status:** Approved (brainstorming)
**Author:** Brad Hagstrom + Claude

## Problem

The platform's transactional email (`utils/email.py` → `send_platform_email()`) sends
via Gmail SMTP on port 587 from a Gmail from-address. In production the app runs on a
DigitalOcean droplet, and **DO permanently blocks outbound ports 25, 465, and 587** as
anti-abuse policy. DO support confirmed they will not lift the restriction and pointed to
two paths: an alternate SMTP port (2525) or an HTTP REST sending service.

Gmail's SMTP does not listen on 2525 — that port is exposed by transactional email
*providers* precisely so cloud servers can bypass the 587 block. So "keep using Gmail SMTP
from the droplet" is not viable. The platform must move to a real sending provider.

This also upgrades deliverability: sending from a Gmail address via raw SMTP on a server
was already the fragile option (spam/Promotions placement). A branded, DKIM-signed sender
is a strict improvement.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Sender identity | Branded `commish@cccfantasy.com` | Best deliverability; on-brand (Corrupt Commish Club); replyable. |
| Transport | SMTP relay on port 2525 | Keeps the tested `smtplib` path intact; lowest risk to load-bearing reset/signup mail; DO's sanctioned unblocked port. REST upgrade stays available later as a localized change. |
| Provider | Brevo | Free tier 300/day (ample for this volume); simple domain-auth wizard; SMTP relay on 2525; domain DKIM. |
| Reply handling | Cloudflare Email Routing | Brevo only sends; a replyable address needs an inbox. Free CF routing forwards `commish@` → Brad's Gmail. |

**Non-goal / explicitly deferred:** REST API transport, webhook bounce/open tracking,
Brevo's drag-and-drop email designer. Email *design* stays in our own HTML templates
(table layout + inline styles per CLAUDE.md), which is provider-agnostic.

## Architecture

### Code change — `utils/email.py` (minimal)

Today `EMAIL_ADDRESS` does double duty: it's both the SMTP `login()` user **and** the
`From:` header. With Brevo these decouple — you authenticate as the Brevo account login
(password = a Brevo **SMTP key**, not the account password) but send *from*
`commish@cccfantasy.com`.

Change:
- Read a new `MAIL_FROM_ADDRESS` config value; **default to `EMAIL_ADDRESS` when unset**
  so dev/test behavior is unchanged.
- Use `MAIL_FROM_ADDRESS` in the `From:` header (`f'{PLATFORM_FROM_NAME} <{from_addr}>'`).
- Keep `EMAIL_ADDRESS` / `EMAIL_PASSWORD` as the SMTP auth pair.
- Everything else stays byte-for-byte: `MIMEMultipart('alternative')`, `starttls()`,
  exception logging, `return False` on failure. STARTTLS works identically on 2525.

### Config — `config.py` / production `.env`

No code-level default changes required; the existing `current_app.config.get(...)`
fallbacks remain (the Gmail defaults are harmless in dev, where sends are skipped when
creds are absent). Production `.env` gains:

```
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=2525
EMAIL_ADDRESS=<brevo account login email>
EMAIL_PASSWORD=<brevo SMTP key>
MAIL_FROM_ADDRESS=commish@cccfantasy.com
```

### Brevo + DNS setup (ops runbook — exact steps in the plan)

1. Create Brevo account; start domain authentication for `cccfantasy.com`.
2. Add Brevo's **SPF**, **DKIM**, and **DMARC** records as Cloudflare DNS entries
   (Brevo provides exact values). DKIM is the deliverability lever.
3. Verify authentication succeeds in Brevo; generate an SMTP key.
4. **Cloudflare Email Routing:** add a custom-address route forwarding
   `commish@cccfantasy.com` → Brad's Gmail, plus the MX/TXT records CF auto-creates, so
   replies land somewhere.

> DNS note: Brevo (SPF/DKIM/DMARC, sending) and Cloudflare Email Routing (MX, receiving)
> coexist. SPF is a single merged TXT record — if both want SPF content, combine into one
> `v=spf1 ... include:... ~all` record rather than publishing two SPF TXT records (two SPF
> records = permerror). The plan calls this out explicitly.

## Verification

- **Local smoke:** send one email through Brevo to Brad's inbox; confirm it (a) arrives and
  (b) passes DKIM — Gmail → "Show original" should report `DKIM: PASS` signed by
  `cccfantasy.com` and `SPF: PASS`.
- **Reply test:** reply to that email; confirm it forwards to Brad's Gmail via CF routing.
- **Prod:** after deploy, trigger a real password-reset email on cccfantasy.com and confirm
  inbox (not spam/Promotions) placement.

## Tests

There is no existing direct test of `send_platform_email()` (only `test_asset_versioning.py`
/ `test_logo_assets.py` touch the reset email's seal URL, and they stay green — unaffected).
Add a new `tests/test_email.py`:
- `From:` header uses `MAIL_FROM_ADDRESS` when set.
- `From:` header falls back to `EMAIL_ADDRESS` when `MAIL_FROM_ADDRESS` is unset.
- Both assert against the constructed message by mocking `smtplib.SMTP` and capturing the
  `send_message` argument (no real network).

## Rollout

Single pass, all of: code change + test + Brevo account + DNS (SPF/DKIM/DMARC) + CF Email
Routing + prod `.env` + deploy + verify. The production-deployment defense-in-depth
invariant (`ENVIRONMENT=production` in `.env`, systemd, crontab) is untouched — only the
SMTP-related `.env` keys change.

## Files touched

- `utils/email.py` — add `MAIL_FROM_ADDRESS`, use in `From:` header.
- `tests/test_email.py` — **new** file; from-header set/fallback tests.
- Production `.env` (server-side, not in repo) — SMTP keys.
- No migrations. No template changes (email HTML is already to standard).
