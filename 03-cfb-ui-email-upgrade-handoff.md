# CFB Survivor Pool — UI + Email Upgrade

## Context

This task upgrades the CFB Survivor Pool game surfaces and email system. **Files 1
and 2 are complete.** Here is the exact state Claude Code left things:

**What Files 1 & 2 delivered:**
- `static/css/style.css` — "The Commissioner's Club" design system with Teko +
  Newsreader typography, royal purple + gold platform palette, a `body.game-cfb`
  override block with **provisional** Wisconsin Badger red/midnight values, a fully
  built golf CSS section, and established patterns for game-specific CSS sections
- `templates/base.html` — unified platform base; all CFB templates already extend it
- CFB context processor already injects `body_class = 'game-cfb'`
- `games/golf/services/reminders.py` — fully upgraded HTML email system with
  `_html_wrapper()`, `_html_button()`, `GOLF_EMAIL` inline constants, and
  `send_results_recap_email()`. Use this as the direct pattern reference for CFB.

**What this file must do:**
1. **UI upgrade** — Finalize the CFB palette, add CFB-specific CSS component classes,
   and restyle all CFB templates using `--game-*` tokens. Likely fewer broken
   variable references than golf had (CFB templates didn't inherit a competing legacy
   design system), but the audit will confirm.
2. **Email upgrade** — CFB's `_send_email()` uses bare `MIMEText` (not
   `MIMEMultipart`). Upgrade it, build HTML email helpers in CFB's visual identity,
   and add the Weekly Results Recap as a net-new email.

**CFB design identity:** Dark, intense, high-stakes. Midnight backgrounds, Badger
crimson accents, bold Teko headings. The sport is about survival and elimination —
the design should feel like something is on the line every week. Execute within the
platform's unified design system, not as a standalone aesthetic.

---

## Step 0: Invoke Skills

**Invoke the `frontend-design` skill** and answer its four core questions before
reading any files:

- **Purpose**: CFB Survivor Pool for ~22 friends. Weekly picks, elimination stakes,
  2-life system. Members check standings to see who survived, who's on the bubble,
  who got eliminated. The pick submission page is used once per week under mild
  deadline pressure — primarily on mobile.
- **Tone**: High-stakes scoreboard energy. Midnight dark with Badger crimson — think
  ESPN bottom-line meets war room. Intensity without gimmickry.
- **Constraints**: Bootstrap 5 CDN, no JS build step, Teko + Newsreader loaded
  globally, existing card-selection JS in `pick.html` must stay functional, Gmail
  inline-style emails.
- **Differentiation**: The weekly results page is the emotional peak — who survived,
  who fell. The eliminations alert should feel like a headline, not a table row.

**Invoke the `writing-plans` skill** for the audit and plan phase (Steps 1–2).
**Invoke the `executing-plans` skill** once Brad approves (Step 3 onward).

---

## Step 1: Audit Phase (Plan Mode — No Code Yet)

### 1a. Read every file in scope

**CSS:**
- `static/css/style.css` — full file. Pay attention to:
  - `body.game-cfb` override block (provisional values to finalize)
  - Golf CSS section structure — CFB section should follow the same pattern
  - Which platform component classes consume `--game-*` variables (don't duplicate)

**CFB templates (`games/cfb/templates/cfb/`):**
- `index.html` — standings + championship page variant
- `pick.html` — card-based team selection (read the JS carefully)
- `my_picks.html` — pick history + strategy
- `weekly_results.html` — week results scoreboard
- All files in `admin/` subdirectory

**CFB services and models:**
- `games/cfb/services/reminders.py` — full file
- `games/cfb/services/game_logic.py` — `process_week_results()` specifically
- `games/cfb/services/automation.py` — where results finalization is triggered
- `games/cfb/models.py` — `CfbWeek`, `CfbPick`, `CfbEnrollment`, `CfbTeam`, `CfbGame`
- `games/cfb/utils.py` — timezone helpers, week display names, CFP helpers

**Pattern reference (already upgraded):**
- `games/golf/services/reminders.py` — full file. This is the direct template for
  CFB's email system. Understand `_html_wrapper()`, `_html_button()`, `GOLF_EMAIL`
  constants, and `send_results_recap_email()` before writing any CFB email code.

### 1b. Produce a written audit

**Broken reference inventory** — scan all CFB templates for dead CSS variables or
font references left over from any prior design system. Format as a table:

| File | Code snippet | Fix |
|------|-------------|-----|
| `index.html` | `color: var(--navy)` | `color: var(--game-primary)` |
| ... | ... | ... |

Use code snippets, not line numbers — line numbers drift after edits.

**Confirmed clean files** — explicitly list any CFB templates that have zero broken
references and need no variable cleanup. This saves an audit pass during execution.

**Inline style audit** — catalog `style="..."` attributes that should become CSS
classes vs. those that are one-off and can stay inline.

**CFB-specific CSS needed** — map each needed component class to the template(s)
that will use it. Do not propose classes with no consumer.

**`--game-*` auto-theming inventory** — list platform component classes that already
consume `--game-primary` / `--game-accent`. These auto-theme once `body.game-cfb`
values are finalized — don't duplicate their work in CFB-specific CSS.

**Card-selection JS audit** — read the JS in `pick.html` that handles card tap →
hidden input → form submit. Document exactly what HTML attributes and class names it
depends on. These must not change.

**Model/field mapping table** — before writing any email data queries, document the
platform equivalents of every model field needed:

| Data needed | Platform model + field |
|-------------|----------------------|
| User's pick this week | `CfbPick` filtered by `week_id` + `user_id` |
| Pick correct/incorrect | `CfbPick.is_correct` |
| Team name | `CfbPick.team` → `CfbTeam.name` (via relationship) |
| Was autopick | `CfbPick.is_autopick` |
| Lives remaining | `CfbEnrollment.lives_remaining` |
| Cumulative spread | `CfbEnrollment.cumulative_spread` |
| Is eliminated | `CfbEnrollment.is_eliminated` |
| Week display name | `utils.get_week_display_name(week)` |
| Week deadline | `CfbWeek.deadline` |
| Game score/result | `CfbGame` filtered by `week_id` |

Confirm field names against the actual models before writing queries.

**Email current state** — document each function in `reminders.py`: its trigger,
current content, and whether it uses plain text or HTML.

**Checkpoint: Present full audit to Brad before implementing.**

---

## Step 2: Design Direction

Still in Plan Mode.

### UI decisions:

**1. CFB palette finalization** — Update `body.game-cfb` with final values. Remove
the `/* PROVISIONAL */` comment. The `frontend-design` skill has authority to adjust
specific shades; Wisconsin Badger red + midnight dark is the directional brief:

```css
/* CFB overrides — finalize these values */
body.game-cfb {
  --game-primary:       #C5050C;   /* Badger red — adjust if skill prefers */
  --game-primary-dark:  #0f0f1a;   /* Deep midnight */
  --game-primary-light: #d63a40;   /* Lighter crimson for hover */
  --game-accent:        #f7f7f7;   /* Near-white — or gold if skill prefers */
  --game-accent-light:  #e0e0e0;
}
```

Additional CFB-specific tokens if needed (define in `body.game-cfb`):
- `--cfb-eliminated` — color for eliminated player rows/badges
- `--cfb-survived` — color for correct pick indicators
- `--cfb-lost-life` — color for incorrect pick indicators

**2. Standings page** — two modes, both need treatment:

*Regular season:*
- Lives remaining: visual indicator (dots, shields, or similar — `frontend-design`
  skill decides; must be immediately readable at a glance)
- Eliminated players: visually distinct but not hidden — muted rows or separate
  section, not removed
- Cumulative spread: secondary to lives, present but not dominant
- Current week pick status visible
- Current user row highlighted

*Championship page:*
- Champion reveal — should feel like a climax, not a standings table
- Fallen competitors list
- Season summary — celebratory energy

**3. Pick submission** — card-based (not Tom Select like golf). The JS handles
card tap → hidden input → form submit. Polish the cards, don't restructure them:
- Eligible team card: team name, spread, conference — feels like a matchup board
- Selected state: bold border, background shift, check indicator
- Ineligible teams: clearly disabled with visible reason (used, spread cap, game
  started)
- Touch targets ≥44px — this page is primarily used on mobile

**4. Weekly results** — this is the emotional high point of the week:
- User's own result (SURVIVED / LOST A LIFE) prominent at top
- Eliminations this week: treated like a headline, not a table row
- Full picks table: everyone's result, scannable

**5. CFB email color tokens** — define inline style constants matching the finalized
palette. Adapt the `GOLF_EMAIL` pattern from `games/golf/services/reminders.py`:

```python
CFB_EMAIL = {
    "primary":      "#C5050C",   # Badger red (confirm against finalized palette)
    "primary_dark": "#0f0f1a",   # Midnight
    "accent":       "#f7f7f7",   # Near-white or gold
    "bg_body":      "#1a1a2e",   # Dark background for CFB emails
    "bg_card":      "#ffffff",   # Content area stays white for readability
    "text_primary": "#1a1a1a",
    "text_muted":   "#666666",
    "font_heading": "Georgia, 'Times New Roman', serif",
    "font_body":    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
}
```

**6. Email tone** — urgency for reminders (elimination stakes are real), dramatic
post-game energy for the recap. The weekly recap is what members forward to each
other on Monday. Write it like a commissioner who lives for this.

**Checkpoint: Present design direction for approval before implementing.**

---

## Part 1: UI Implementation [Commit 1]

### 3a. CFB Palette Finalization in `style.css`

Update `body.game-cfb` with finalized values. Remove `/* PROVISIONAL */`. Add the
`/* === CFB SURVIVOR POOL === */` CSS section immediately after, following the same
structure as the golf section added in File 2.

### 3b. CFB-Specific CSS (additions to `static/css/style.css`)

Add a clearly marked `/* === CFB SURVIVOR POOL === */` section. Every class must be
consumed by at least one CFB template — no speculative CSS.

**Likely needed** (audit may revise this list):
- `.lives-indicator` — visual lives display; style TBD by `frontend-design` skill
- `.lives-indicator .life` — individual life dot/shield (active state)
- `.lives-indicator .life.lost` — spent life (muted/empty state)
- `.team-pick-card` — selectable team card base styles
- `.team-pick-card.selected` — active selection (bold border, background shift,
  check mark)
- `.team-pick-card.ineligible` — disabled state with reason text
- `.spread-badge` — spread display on team cards and tables
- `.badge-eliminated` — elimination status badge
- `.badge-survived` — correct pick indicator
- `.badge-lost-life` — incorrect pick indicator
- `.results-scoreboard` — weekly results picks table layout
- `.elimination-alert` — prominent eliminations-this-week callout
- `.championship-hero` — winner reveal display for season-end page

**JS-critical class names**: Cross-reference the card-selection JS audit from Step 1b.
Any class the JS reads or toggles must not change. Add new visual classes alongside
existing JS-functional classes, don't replace them.

→ **Run `code-review`** on CSS additions — focus on: hardcoded hex that should be
  custom properties, classes with no template consumer, JS-critical names at risk

### 3c. `games/cfb/templates/cfb/index.html` — Standings [Commit 1]

**Priority 1 — Fix broken references** (from audit inventory table):
Apply every fix in the broken reference inventory. Use the code snippets from the
audit to locate targets precisely.

**Priority 2 — Move inline styles to classes** (from inline style audit).

**Priority 3 — Regular season standings polish:**
- Hero: game title (Teko), season year, current week
- Current week status card: deadline, user's pick status
- Standings table/cards: `.lives-indicator`, `.badge-eliminated`, `.row-current-user`
- Eliminated players: visually distinct section or muted rows
- Sidebar: pool rules, lives explanation, spread explanation
- CFP alert banner when in playoff phase

**Priority 4 — Championship page polish:**
- Champion display via `.championship-hero`
- Fallen competitors list
- Season summary card — celebratory, not clinical

→ **Run `code-review`** — focus on: remaining broken refs, Jinja2 logic intact,
  JS-critical attributes untouched

### 3d. `games/cfb/templates/cfb/pick.html` — Pick Submission [Commit 1]

**Read the JS card-selection code first.** Understand exactly which class names and
data attributes it depends on before touching any HTML.

- Fix broken references (from audit)
- Apply `.team-pick-card`, `.team-pick-card.selected`, `.team-pick-card.ineligible`,
  `.spread-badge` around the existing JS hooks — not replacing them
- Deadline banner: prominent, above the fold
- Current pick display: if user has a pick, show it clearly with change option
- Form submit: prominent, one-thumb-reachable on mobile
- Sidebar: used teams list, strategy info, lives remaining

**Critical**: After any HTML changes to `pick.html`, manually verify the card
selection flow still works — card tap updates hidden input, form submits correctly.

→ **Run `code-review`** — focus on: JS-critical attributes intact, touch targets ≥44px

### 3e. `games/cfb/templates/cfb/my_picks.html` — Pick History [Commit 1]

- Fix broken references (from audit)
- Stats row: total picks, correct, incorrect, cumulative spread
- Pick history table/cards: `.badge-survived`, `.badge-lost-life` for outcomes
- Lives status with `.lives-indicator`
- Strategy section: available teams, conference coverage, CFP info
- Mobile: cards not horizontally scrolling tables

### 3f. `games/cfb/templates/cfb/weekly_results.html` — Week Results [Commit 1]

- Fix broken references (from audit)
- User's result (SURVIVED / LOST A LIFE / PENDING) prominent at top
- `.elimination-alert` for this week's eliminations — headline treatment, not a
  table row
- Summary stats: correct / incorrect / pending counts
- All picks table/cards: `.badge-survived`, `.badge-lost-life`, current user
  highlighted, `.results-scoreboard`
- Games section: scores and spread results

### 3g. Admin Templates (`games/cfb/templates/cfb/admin/`) [Commit 1]

- Fix broken references (from audit) — no exceptions, even for admin
- Light touch otherwise: palette alignment only
- Do not invest significant effort here

→ **Run `coderabbit`** after all UI templates — holistic analysis

---

## Part 2: Email Implementation [Commit 2]

### 4a. Email Infrastructure (`games/cfb/services/reminders.py`) [Commit 2]

**Replace `_send_email()` with HTML-capable version:**

```python
def _send_email(to_addr, subject, body, html_body=None):
    """Send an email with plain text and optional HTML body."""
    email_address = current_app.config.get('EMAIL_ADDRESS', '')
    email_password = current_app.config.get('EMAIL_PASSWORD', '')
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = current_app.config.get('SMTP_PORT', 587)

    if not email_address or not email_password:
        logger.warning("Email credentials not configured; skipping.")
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = email_address
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        logger.info("Email sent to %s", to_addr)
        return True
    except Exception as e:
        logger.error("Failed to send to %s: %s", to_addr, e)
        return False
```

**Add `CFB_EMAIL` inline constants** at module level — finalize hex values against
the palette chosen in Step 2:

```python
CFB_EMAIL = {
    "primary":      "#C5050C",   # Badger red (update to finalized value)
    "primary_dark": "#0f0f1a",   # Midnight
    "accent":       "#f7f7f7",   # Near-white or gold (update to finalized value)
    "bg_body":      "#1a1a2e",   # Dark email background
    "bg_card":      "#ffffff",   # Content area
    "text_primary": "#1a1a1a",
    "text_muted":   "#666666",
    "font_heading": "Georgia, 'Times New Roman', serif",
    "font_body":    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
}
```

**Add HTML builder helpers** — adapted from the golf pattern in
`games/golf/services/reminders.py`. CFB-branded, not a copy:

- `_cfb_html_wrapper(content, season_year)` — dark-header email shell with "The
  Commissioner's Club — CFB Survivor Pool" branding, content area, footer with
  site link. Table-based, max-width 600px, inline styles only.
- `_cfb_html_button(url, text)` — CTA `<a>` tag styled inline with CFB accent color
- `_cfb_html_week_card(week_name, deadline)` — week info block for reminder emails

### 4b. Pick Reminder Emails — Upgrade Existing [Commit 2]

Upgrade `send_pick_reminders()` to produce HTML. The existing scheduling logic
(25hr and 1hr windows, tolerance check, `get_users_without_picks()`) must not
change — only the email content/format.

Content per reminder:
- Week number and display name (via `utils.get_week_display_name()`)
- Deadline (Central Time)
- Time remaining
- User's lives remaining and cumulative spread
- **Urgency escalation**: 25hr reminder is informational; 1hr reminder uses crimson
  accent border and bold warning language — elimination stakes make this urgent
- CTA: "Make Your Pick" → `{site_url}/cfb/pick/{week_number}`
- Plain text fallback preserved

### 4c. Weekly Results Recap Email — Net New [Commit 2]

**New function**: `send_weekly_recap_email(week_id)` in `reminders.py`

This is the heartbeat of the pool. Write it like a post-game report from a
commissioner who lives for this.

**Data to include per recipient** (personalized per send).

Use the model/field mapping table from Step 1b for all queries:

1. **Their pick result:**
   - Team name (`CfbPick.team` → `CfbTeam.name`)
   - Outcome: SURVIVED / LOST A LIFE / AUTOPICK
   - Spread contributed (`CfbPick` → `CfbGame.get_spread_for_team()` or equivalent)
   - Whether autopicked (`CfbPick.is_autopick`)

2. **Their current status:**
   - Lives remaining (`CfbEnrollment.lives_remaining`) — visual: "●● 2 lives" /
     "●○ 1 life"
   - Cumulative spread (`CfbEnrollment.cumulative_spread`)
   - Rank among non-eliminated players

3. **Week summary — the dramatic section:**
   - Total picks submitted, correct count, incorrect count
   - **Eliminations this week** — names of eliminated players. This is the drama.
     Query: enrollments where `is_eliminated=True` that were not eliminated in a
     prior week (compare to pre-processing state, or check picks from this week
     where `is_correct=False` and enrollment now has 0 lives)
   - Players remaining in pool
   - If zero eliminations: "Everyone survived — impressive!"

4. **CTA**: "View Full Results" → `{site_url}/cfb/results/{week_number}`

**Edge cases — all must be handled:**
- User eliminated this week → "You've been eliminated" subject line, final stats,
  respectful tone (these are friends)
- User's pick was autopick → "Autopick: [team] was selected for you"
- No pick and no autopick → shouldn't happen; handle gracefully with $0 equivalent
- CFP phase → note team usage has reset, add context
- Week with no eliminations → note it explicitly

→ **Run `code-review`** after implementing

### 4d. Trigger Wiring (`games/cfb/services/automation.py`) [Commit 2]

Locate where `process_week_results()` is called in the automation flow. Add the
recap trigger immediately after successful processing. Pass `week.id` (not the ORM
object) to avoid detached instance errors — same pattern as golf's `sync.py`:

```python
# Send weekly recap email (once per week)
week = db.session.get(CfbWeek, week_id)
if week and not week.recap_email_sent:
    try:
        from games.cfb.services.reminders import send_weekly_recap_email
        emails_sent = send_weekly_recap_email(week.id)
        if emails_sent > 0:
            week.recap_email_sent = True
            db.session.commit()
            logger.info("Sent weekly recap to %s users for Week %s",
                        emails_sent, week.week_number)
    except Exception as e:
        logger.error("Failed to send recap for Week %s: %s",
                     week.week_number, e)
```

→ **Run `pyright-lsp`** after modifying `automation.py`
→ **Run `code-review`**

---

## Step 5: Gmail Compatibility Checklist

Verify each item before finalizing any HTML email:

- [ ] All styles inline (no `<style>` in `<body>`)
- [ ] Table-based layout (`<table>`, `<tr>`, `<td>`) — not flexbox/grid
- [ ] No external font imports (Teko/Newsreader won't render in Gmail)
- [ ] System font stacks via `CFB_EMAIL` constants
- [ ] CTA buttons are `<a>` tags, not `<button>` elements
- [ ] Max width 600px with `width="100%"` on outer table
- [ ] `MIMEMultipart('alternative')` with plain text fallback
- [ ] WCAG AA color contrast — especially white text on dark crimson backgrounds

→ **Invoke `frontend-design` skill** to review completed email templates — the recap
  especially should feel like a commissioner sent it, not a SaaS notification

---

## Step 6: Holistic Review and Commit

→ **Run `coderabbit`** — holistic analysis across all CFB changes
→ **Run `code-simplifier`** on `reminders.py` — look for: repeated inline style
  values not referencing `CFB_EMAIL` constants, builder helper called only once
  (candidate to inline), structural duplication with golf's email helpers that
  doesn't serve CFB's distinct visual identity

→ **Use the `verification-before-completion` skill** to work through every item in
  Verification Criteria below before committing.

→ **Run `commit-commands`** using the **`finishing-a-development-branch` skill**.
  Two commits, in this order:
  1. `feat: CFB survivor pool UI upgrade — Commissioner's Club crimson/dark palette`
     *(all template and CSS changes from Part 1)*
  2. `feat: CFB HTML email templates + weekly results recap notification`
     *(all reminders.py, automation.py, and models.py changes from Part 2)*

---

## Migration

One new column on `CfbWeek`.

### Model change (`games/cfb/models.py`) [Commit 2]

Add to the `CfbWeek` class alongside any existing boolean flags:

```python
recap_email_sent = db.Column(db.Boolean, default=False, nullable=False)
```

### Alembic migration

```bash
FLASK_APP=app.py venv/bin/flask db migrate -m "add cfb_week recap_email_sent flag"
FLASK_APP=app.py venv/bin/flask db upgrade
```

Review the generated migration before running `upgrade` — confirm it only adds the
one column.

→ **Run `pyright-lsp`** after modifying `models.py`

---

## Source Files

All source files are already present. No action needed:

- `_migration_source/CFB/style.css` ✓ — standalone CFB CSS, color/component reference
- `_migration_source/CFB/send_reminders.py` ✓ — standalone plain-text email reference
- `_migration_source/CFB/models.py` ✓ — field name reference if needed
- `_migration_source/CFB/config.py` ✓ — config structure reference

Primary email pattern reference is `games/golf/services/reminders.py` (already
upgraded in File 2), not the standalone CFB version which was plain text only.

---

## Verification Criteria

### UI [Commit 1]
- [ ] All broken references from audit inventory are resolved
- [ ] Confirmed-clean files from audit required no changes (or only palette alignment)
- [ ] `body.game-cfb` palette values finalized — `/* PROVISIONAL */` comment removed
- [ ] CFB-specific CSS section exists in `style.css`, clearly marked
- [ ] No CSS class added without a template consumer
- [ ] JS-critical class names and data attributes in `pick.html` are unchanged
- [ ] Card selection (tap → hidden input → form submit) still works after HTML changes
- [ ] `.lives-indicator` is immediately readable at a glance
- [ ] Eliminated players are visually distinct in standings (not hidden)
- [ ] Weekly results eliminations treated as a headline, not a table row
- [ ] Championship page feels celebratory, not clinical
- [ ] Touch targets ≥44px on all interactive elements
- [ ] Mobile layouts use cards, not horizontally scrolling tables
- [ ] All existing Jinja2 template logic remains 100% functional

### Email [Commit 2]
- [ ] `_send_email()` uses `MIMEMultipart('alternative')` with HTML support
- [ ] `CFB_EMAIL` inline constants defined at module level with finalized hex values
- [ ] `_cfb_html_wrapper()` and `_cfb_html_button()` helpers exist and are used
- [ ] Pick reminders send as HTML with urgency escalation (25hr informational → 1hr
      crimson/urgent)
- [ ] Weekly Results Recap fires once per week, gated by `recap_email_sent`
- [ ] Recap includes: pick result, lives status, eliminations (by name), pool rank
- [ ] Edge cases handled: elimination this week, autopick, no eliminations, CFP phase
- [ ] Gmail checklist passes (inline styles, table layout, system fonts, 600px max)
- [ ] No credentials in committed code
- [ ] `recap_email_sent` column exists on `CfbWeek` after migration
- [ ] Trigger in `automation.py` passes `week.id` (not ORM object)

---

## Final Note

CFB Survivor is the game with the highest emotional stakes — people get eliminated.
The design should reflect that. Dark backgrounds, bold crimson, dramatic moments.
The weekly recap email is what members forward to each other on Monday morning. Make
it feel like a post-game report from a commissioner who lives for this stuff.
