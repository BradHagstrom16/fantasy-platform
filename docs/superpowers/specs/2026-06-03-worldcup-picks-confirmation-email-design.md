# World Cup Picks Confirmation Email — Design

**Date:** 2026-06-03
**Status:** Approved (send policy + content blocks confirmed by Brad in brainstorming)

## Problem

When a player submits their World Cup picks, the only acknowledgment is a flash
message that disappears on the next page load. Players have no durable record of
what they entered: which 9 teams, which tiers, what tiebreaker guess. Before the
deadline this matters twice over, because picks are editable and a player who
revises their roster has no receipt of what is currently saved.

## Goal

Send a branded confirmation email on every successful picks submission containing
the player's full roster, so their inbox always holds a receipt of the
currently-saved entry.

## Decisions (confirmed)

1. **Send on every save.** Each successful POST to `/worldcup/picks` emails the
   now-current roster. First save subject: `Your World Cup picks are in`. Later
   saves: `Your updated World Cup picks` — so inbox history reads correctly and
   no stale email masquerades as the entry of record.
2. **Content blocks:** 9-pick roster (flag, team, group, tier, multiplier) +
   tiebreaker guess (USA goals) + edit-window note with the deadline in CT +
   CTA button to `/worldcup/picks`. No scoring teaser, no pool-size line.

## Architecture

Mirrors the daily digest (PR #62) exactly — same module, same design system,
same test pattern. No new infrastructure.

### Service — `games/worldcup/services/notifications.py`

New public function:

```python
def send_picks_confirmation(enrollment, is_update: bool = False) -> bool
```

- Queries the enrollment's picks ordered by tier, then team display name
  (same ordering as the picks page roster).
- Builds template rows: `team`, `multiplier_str` (reuses `_fmt_multiplier`),
  tier name from `TIERS`, `group_letter`.
- Deadline rendered in CT via `TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)`
  (constant imported from `games.worldcup.constants`, its canonical home).
- `site_url` / `logo_url` / `_asset_version()` identical to the digest.
- Renders `worldcup/email/wc_picks_confirmation.j2` (HTML) + a
  `_plain_confirmation()` text fallback; sends via `send_platform_email`.
- **Never raises.** Whole body wrapped in try/except with `logger.exception`;
  returns `True`/`False`. A template bug or SMTP failure must never break the
  picks submission that triggered it.

### Route hook — `games/worldcup/routes.py` `picks()` POST

```python
was_update = enrollment.picks_submitted   # captured BEFORE mutation
...
enrollment.picks_submitted = True
db.session.commit()
send_picks_confirmation(enrollment, is_update=was_update)
```

Fire-and-forget after the commit: the email outcome does not affect the flash
or redirect. At pool scale (10–30 players) the synchronous SMTP send (~1s) in
the request is acceptable; no queue is warranted.

### Template — `games/worldcup/templates/worldcup/email/wc_picks_confirmation.j2`

Forks the digest skeleton (table layout, inline styles, Gmail-safe):

- Navy header band `#2A1150` + CCC stacked logo + "World Cup Fantasy Pool".
- Hero on bone `#F3EFE6`: greeting, Teko headline ("Your picks are in" /
  "Your picks are updated"), Newsreader receipt sub-line.
- 2px navy `#002868` rule.
- Roster on white, grouped by tier: small Teko tier header
  (`Favorites ×1` … `Wildcards ×7`), then per-team rows — hosted flag SVG
  (`{{ site_url }}/static/flags/{{ iso }}.svg?v={{ asset_version }}`, never
  emoji), Teko team name, Newsreader `Group X` meta.
- Tiebreaker line: `Tiebreaker — USA goals: N`.
- Edit-window note: editable until `<deadline in CT>`; locks after.
- Gold-gradient CTA → `{{ site_url }}/worldcup/picks`.
- Dark navy footer band.

## Error handling

- Service catches everything, logs via `logger.exception`, returns bool.
- `send_platform_email` already logs missing-credential and SMTP failures.
- Validation-failure POSTs never reach the send (it sits after the commit).

## Testing — `tests/test_worldcup_picks_confirmation.py`

Established pattern: `@mock.patch('games.worldcup.services.notifications.send_platform_email')`,
assert on `call_args[0]` = `(to, subject, plain, html)`.

Service-level: roster completeness (all 9 teams, tier names, multipliers,
flag URLs, groups), tiebreaker + CT deadline present, plain-text fallback
mirrors HTML content, first-vs-update subject, returns False (not raises) on
render/send failure.

Route-level: valid first POST triggers exactly one send with first-save
subject; second POST uses update subject; invalid POST sends nothing;
a send failure still persists picks and redirects normally.

## Out of scope

- No queue/async sending.
- No unsubscribe preference (transactional receipt, same as digest).
- No scoring/rules content in the email.
