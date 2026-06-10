# World Cup Fantasy Pool — Excel Replication Guide

A complete blueprint for running the World Cup Fantasy Pool in an Excel workbook with
automated scoring. Results pull live from a free football API; Excel formulas turn them
into a leaderboard. No programming required — just Excel on Windows (Microsoft 365).

This mirrors the setup the original web version runs in production: same API, same
scoring rules, same refresh cadence.

---

## 1. What you're building

Each player picks **9 national teams** across 5 risk tiers before the first kickoff.
Teams earn points for everything they do in the tournament (wins, draws, advancing,
knockout runs). Each pick's points are multiplied by its tier's risk multiplier —
underdogs are worth far more per result than favorites. Highest total wins.

The automation flow:

```
football-data.org  ──►  Power Query   ──►  Matches table  ──►  scoring formulas  ──►  Leaderboard
(free API)              (built into         (one row per        (COUNTIFS on the      (one row per
                         Excel; refreshes    match, auto-        Teams sheet)          player)
                         on a timer)         updating)
```

You set it up once before the tournament. During the tournament the only manual work is
clicking **Refresh All** (or letting the auto-refresh timer do it) and filling in one
small group-advancement table after the group stage ends.

---

## 2. The scoring rules

### Tiers and picks

Every player submits exactly **9 picks** with this composition:

| Tier | Name        | Picks required | Multiplier |
|------|-------------|----------------|------------|
| 1    | Favorites   | 2              | ×1.0       |
| 2    | Contenders  | 1              | ×1.5       |
| 3    | Dark Horses | 2              | ×2.5       |
| 4    | Underdogs   | 2              | ×4.0       |
| 5    | Wildcards   | 2              | ×7.0       |

Picks lock at the first match kickoff (June 11, 2026 — 2:00 PM CT / 7:00 PM UTC).

### Tier rosters (2026)

| Tier | Teams |
|------|-------|
| 1 — Favorites | Argentina, Brazil, England, France, Germany, Portugal, Spain |
| 2 — Contenders | Belgium, Colombia, Netherlands, Norway |
| 3 — Dark Horses | Croatia, Ecuador, Japan, Mexico, Morocco, Senegal, Sweden, Switzerland, Turkey, United States, Uruguay |
| 4 — Underdogs | Algeria, Austria, Bosnia & Herzegovina, Canada, Czech Republic, Egypt, Ghana, Ivory Coast, Paraguay, Scotland, South Korea |
| 5 — Wildcards | Australia, Cape Verde, Curacao, DR Congo, Haiti, Iran, Iraq, Jordan, New Zealand, Panama, Qatar, Saudi Arabia, South Africa, Tunisia, Uzbekistan |

(Feel free to re-tier for your own pool — the spreadsheet doesn't care which team is in
which tier, only that the multipliers and pick counts are applied consistently.)

### How teams earn base points

| Event | Base points |
|-------|-------------|
| Group-stage win | 3 |
| Group-stage draw | 1 |
| Group-stage loss | 0 |
| Wins its group | +4 |
| Advances as group runner-up | +3 |
| Advances as a best third-place team | +1 |
| Wins a Round-of-32 match | +8 |
| Wins a Round-of-16 match | +11 |
| Wins a Quarterfinal | +15 |
| Wins a Semifinal | +19 |
| **Wins the Final (champion)** | **+50** |
| Loses the Final (runner-up) | +8 |
| Wins the third-place match | +8 |

Two details that matter for the formulas later:

- Winning the Final earns the **champion bonus (50)** — there is no separate
  "final-win" entry on top of it. Same idea for the third-place match (+8 to its
  winner only).
- A knockout win counts the same whether it came in regulation, extra time, or
  penalties.

A team that wins it all from a group win maxes out at **116 base points**
(9 group + 4 advancement + 8 + 11 + 15 + 19 + 50).

### Player score

> **Player total = Σ over their 9 picks of (team base points × tier multiplier)**

A Wildcard champion would be worth 116 × 7.0 = 812 points. That's the whole game.

---

## 3. The API: football-data.org

### Why this one

- The **free tier actually includes World Cup 2026**. (Watch out: API-Football's free
  tier does *not* — we checked.)
- Generous limits: **10 requests/minute, no daily cap**. A spreadsheet refreshing every
  30–60 minutes uses a tiny fraction of that.
- Dead-simple auth: one token in one HTTP header. No OAuth.

### Sign up (free)

1. Go to <https://www.football-data.org/client/register> and register for the **free
   tier**.
2. Your API token arrives by email within a minute or two.
3. Treat the token like a password — it's tied to your account. Don't post it anywhere
   public. (Register your own; don't borrow someone else's.)

### The endpoints

Two URLs cover everything. Auth is the header `X-Auth-Token: <your token>` on every
request.

| URL | What it returns | Used for |
|-----|-----------------|----------|
| `https://api.football-data.org/v4/competitions/WC/matches` | All 104 fixtures with status and scores | **The whole scoring pipeline** — this is the one Excel refreshes |
| `https://api.football-data.org/v4/competitions/WC/standings` | The 12 group tables | Optional reference when filling in the Advancement sheet |

Quick smoke test before touching Excel — paste this into PowerShell (with your token):

```powershell
Invoke-RestMethod -Uri "https://api.football-data.org/v4/competitions/WC/matches" -Headers @{"X-Auth-Token"="YOUR_TOKEN_HERE"} | Select-Object -ExpandProperty matches | Select-Object -First 2
```

If you get match data back, you're in business.

### What a match looks like

Each entry in the `matches` list is a JSON object. The fields that matter:

```jsonc
{
  "id": 537119,
  "utcDate": "2026-06-11T19:00:00Z",
  "status": "FINISHED",            // only trust scores when this says FINISHED
  "stage": "GROUP_STAGE",          // GROUP_STAGE, LAST_32, LAST_16, QUARTER_FINALS,
                                   // SEMI_FINALS, THIRD_PLACE, FINAL
  "group": "Group A",              // null for knockout matches
  "homeTeam": { "name": "Mexico", "tla": "MEX" },
  "awayTeam": { "name": "South Africa", "tla": "RSA" },
  "score": {
    "winner": "HOME_TEAM",         // HOME_TEAM, AWAY_TEAM, or DRAW (null until finished)
    "duration": "REGULAR",         // REGULAR, EXTRA_TIME, or PENALTY_SHOOTOUT
    "fullTime": { "home": 2, "away": 0 }
  }
}
```

Two lessons from running this in production:

- **Only score a match when `status` is `"FINISHED"`.** In-play and half-time rows have
  partial data.
- **Treat the API's team names as the canonical spelling in your workbook.** Don't
  invent your own and try to map them — every name in your Teams and Picks sheets should
  match the API's spelling exactly, or the COUNTIFS lookups silently return 0. (The web
  version had to maintain a code-mapping table only because it had pre-existing FIFA
  codes; a fresh spreadsheet can skip that entire class of bugs.)

---

## 4. Pulling the data into Excel (Power Query)

Power Query is built into Windows desktop Excel. The fastest path is to paste a
ready-made query; the click-through path is below it if you prefer to see each step.

### Option A — paste the ready-made query (recommended)

1. **Data** tab → **Get Data** → **From Other Sources** → **Blank Query**.
2. In the Power Query window: **Home** → **Advanced Editor**.
3. Delete whatever is there and paste this, replacing `PASTE_YOUR_TOKEN_HERE`:

```text
let
    Source = Json.Document(
        Web.Contents(
            "https://api.football-data.org/v4/competitions/WC/matches",
            [Headers = [#"X-Auth-Token" = "PASTE_YOUR_TOKEN_HERE"]]
        )
    ),
    MatchList = Source[matches],
    AsTable = Table.FromList(MatchList, Splitter.SplitByNothing(), {"Match"}),
    Expanded = Table.ExpandRecordColumn(AsTable, "Match",
        {"id", "utcDate", "status", "stage", "group", "homeTeam", "awayTeam", "score"}),
    Home  = Table.ExpandRecordColumn(Expanded, "homeTeam", {"name"}, {"HomeTeam"}),
    Away  = Table.ExpandRecordColumn(Home, "awayTeam", {"name"}, {"AwayTeam"}),
    Score = Table.ExpandRecordColumn(Away, "score",
        {"winner", "duration", "fullTime"}, {"Winner", "Duration", "FullTime"}),
    Goals = Table.ExpandRecordColumn(Score, "FullTime",
        {"home", "away"}, {"HomeGoals", "AwayGoals"}),
    AddWinnerName = Table.AddColumn(Goals, "WinnerName", each
        if [Winner] = "HOME_TEAM" then [HomeTeam]
        else if [Winner] = "AWAY_TEAM" then [AwayTeam]
        else null, type text),
    AddLoserName = Table.AddColumn(AddWinnerName, "LoserName", each
        if [Winner] = "HOME_TEAM" then [AwayTeam]
        else if [Winner] = "AWAY_TEAM" then [HomeTeam]
        else null, type text),
    Typed = Table.TransformColumnTypes(AddLoserName, {
        {"id", Int64.Type}, {"utcDate", type datetimezone}, {"status", type text},
        {"stage", type text}, {"group", type text},
        {"HomeTeam", type text}, {"AwayTeam", type text},
        {"Winner", type text}, {"Duration", type text},
        {"HomeGoals", Int64.Type}, {"AwayGoals", Int64.Type}
    })
in
    Typed
```

4. Click **Done**. If Excel asks how to connect, choose **Anonymous** — the token header
   inside the query does the actual authentication. (If asked about privacy levels,
   "Public" is fine.)
5. Rename the query **Matches** (right panel), then **Home** → **Close & Load**. You get
   a `Matches` table on its own sheet: all 104 fixtures, one row each, including
   not-yet-played ones (so it doubles as the schedule).

The `WinnerName` / `LoserName` helper columns are the secret to keeping every scoring
formula short — they put the winning and losing team's *name* directly on each finished
row.

> **Heads up:** the token sits in plain text inside the query, so anyone you share the
> workbook with can see it. For an office pool that's usually fine — but it's the reason
> to register your own free token rather than borrowing one.

### Option B — click-through

**Data** → **Get Data** → **From Other Sources** → **From Web** → pick **Advanced** →
URL parts: `https://api.football-data.org/v4/competitions/WC/matches` → under **HTTP
request header parameters** add `X-Auth-Token` = your token → **OK** → in the Power
Query editor, click the **List** next to `matches` → **To Table** → expand the record
columns with the ⇄ button (status, stage, group, homeTeam.name, awayTeam.name,
score.winner, score.duration, score.fullTime.home/away) → **Close & Load**. You'll still
want to add the `WinnerName`/`LoserName` columns (Add Column → Custom Column) using the
`if … then … else` expressions from Option A.

### Auto-refresh

1. **Data** tab → **Queries & Connections** → right-click the **Matches** query →
   **Properties**.
2. Check **Refresh every 60 minutes** (anything ≥ 30 is plenty — the production version
   syncs every 30) and **Refresh data when opening the file**.

One honest caveat: Excel only refreshes **while the workbook is open**. There's no
server doing this for you overnight — open the file on match days (or leave it open) and
the scores take care of themselves. **Refresh All** (Ctrl+Alt+F5) forces it anytime.

---

## 5. Workbook structure

Five sheets. Make each data range a real **Excel Table** (select it → Ctrl+T) and name
it as shown (Table Design tab → Table Name) — every formula below uses those names.

```
Matches      ← Power Query output (never edit by hand)
Teams        ← 48 teams, tier, multiplier, computed points   (Table: Teams)
Advancement  ← small manual table, filled after group stage  (Table: Advancement)
Picks        ← one row per player per pick (9 rows/player)   (Table: Picks)
Leaderboard  ← one row per player                            (Table: Leaderboard)
```

### `Teams` sheet

After your **first successful refresh**, generate the 48 team names straight from the
API data so the spelling is guaranteed to match — put this in a scratch cell:

```
=SORT(UNIQUE(VSTACK(Matches[HomeTeam], Matches[AwayTeam])))
```

Copy → Paste-as-values into column A, delete any blank row, then add the columns:

| Column | Name | How it's filled |
|--------|------|-----------------|
| A | `Team` | Pasted from the formula above (API spelling — don't retype) |
| B | `Tier` | Typed by you (1–5, from the tier roster table in §2) |
| C | `Multiplier` | Typed by you (1.0 / 1.5 / 2.5 / 4.0 / 7.0) |
| D | `GroupWins` | formula below |
| E | `GroupDraws` | formula below |
| F | `AdvPts` | formula below |
| G | `KOPts` | formula below |
| H | `PodiumPts` | formula below |
| I | `BasePoints` | formula below |
| J | `FinalPoints` | formula below |

Formulas (enter once in row 2 — an Excel Table auto-fills the rest):

**D — GroupWins**

```
=COUNTIFS(Matches[status],"FINISHED",Matches[stage],"GROUP_STAGE",Matches[WinnerName],[@Team])
```

**E — GroupDraws**

```
=COUNTIFS(Matches[status],"FINISHED",Matches[stage],"GROUP_STAGE",Matches[Winner],"DRAW",Matches[HomeTeam],[@Team])
+COUNTIFS(Matches[status],"FINISHED",Matches[stage],"GROUP_STAGE",Matches[Winner],"DRAW",Matches[AwayTeam],[@Team])
```

**F — AdvPts** (reads the manual Advancement sheet; returns 0 until you fill it in)

```
=SUMIFS(Advancement[Points],Advancement[Team],[@Team])
```

**G — KOPts** (8 / 11 / 15 / 19 per knockout-round win)

```
=8*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"LAST_32",Matches[WinnerName],[@Team])
+11*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"LAST_16",Matches[WinnerName],[@Team])
+15*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"QUARTER_FINALS",Matches[WinnerName],[@Team])
+19*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"SEMI_FINALS",Matches[WinnerName],[@Team])
```

**H — PodiumPts** (champion 50 / runner-up 8 / third place 8 — this is where the
`LoserName` helper pays off)

```
=50*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"FINAL",Matches[WinnerName],[@Team])
+8*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"FINAL",Matches[LoserName],[@Team])
+8*COUNTIFS(Matches[status],"FINISHED",Matches[stage],"THIRD_PLACE",Matches[WinnerName],[@Team])
```

**I — BasePoints**

```
=3*[@GroupWins]+[@GroupDraws]+[@AdvPts]+[@KOPts]+[@PodiumPts]
```

**J — FinalPoints**

```
=[@BasePoints]*[@Multiplier]
```

### `Advancement` sheet (the one manual step)

Three columns; you fill it in once, when the group stage ends:

| Team | Milestone | Points |
|------|-----------|--------|
| *(API spelling)* | Group Winner / Runner-up / Best Third | formula |

`Points` formula:

```
=SWITCH([@Milestone],"Group Winner",4,"Runner-up",3,"Best Third",1,0)
```

One row per advancing team (32 rows in 2026: 12 winners + 12 runners-up + 8 best
thirds). Teams not listed simply get 0 from the `AdvPts` SUMIFS.

Why manual? The match feed tells you results, but "who advanced as a best third" is a
tie-breaker decision FIFA publishes — it isn't derivable from scores alone. The
production version makes the same trade-off: results apply automatically, advancement is
confirmed by a human. The `standings` endpoint (§3) shows each group's final table if
you want to double-check positions 1 and 2; the best thirds are simply whoever shows up
in the Round-of-32 bracket.

### `Picks` sheet

Long format — **one row per pick**, 9 rows per player:

| Column | Name | Formula |
|--------|------|---------|
| A | `Player` | typed |
| B | `Team` | typed (API spelling — a Data Validation dropdown pointed at `Teams[Team]` prevents typos) |
| C | `Tier` | `=XLOOKUP([@Team],Teams[Team],Teams[Tier])` |
| D | `Points` | `=XLOOKUP([@Team],Teams[Team],Teams[FinalPoints])` |

### `Leaderboard` sheet

One row per player:

| Column | Name | Formula |
|--------|------|---------|
| A | `Player` | typed |
| B | `Total` | `=SUMIFS(Picks[Points],Picks[Player],[@Player])` |
| C | `Rank` | see below |
| D | `RosterOK` | see below |

**Rank** — two options:

```
=RANK([@Total],Leaderboard[Total])
```

is the standard Excel rank, where two players tied for 2nd makes the next player 4th
(1, 2, 2, 4). The original game uses **dense rank** instead — ties share a rank and the
next distinct score is just one below (1, 2, 2, 3):

```
=SUMPRODUCT((Leaderboard[Total]>[@Total])/COUNTIF(Leaderboard[Total],Leaderboard[Total]))+1
```

Either is fine; just pick one and tell your pool which you're using.

**RosterOK** — validates each player's tier composition (2/1/2/2/2):

```
=IF(AND(COUNTIFS(Picks[Player],[@Player],Picks[Tier],1)=2,
        COUNTIFS(Picks[Player],[@Player],Picks[Tier],2)=1,
        COUNTIFS(Picks[Player],[@Player],Picks[Tier],3)=2,
        COUNTIFS(Picks[Player],[@Player],Picks[Tier],4)=2,
        COUNTIFS(Picks[Player],[@Player],Picks[Tier],5)=2),
   "OK","CHECK PICKS")
```

Run your eye down this column right after the pick deadline.

---

## 6. Operating checklist during the tournament

- **Before kickoff (by June 11):** all picks entered, every `RosterOK` says OK, one test
  Refresh All works.
- **Match days:** open the workbook; auto-refresh handles the rest (or Ctrl+Alt+F5).
- **Spot-check early:** after the first finished match, verify the score against any
  livescore site. Trust the feed *after* you've verified it once — that habit caught
  every data quirk in the production version.
- **When the group stage ends (~June 27):** fill in the Advancement sheet (32 rows).
  This is the only manual scoring step all tournament.
- **After the Final:** one last Refresh All — champion bonus and runner-up points land
  automatically — then crown your winner.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Refresh fails with **HTTP 403** | Token missing, mistyped, or quotes mangled in the query. Re-open Advanced Editor and check the `X-Auth-Token` line. |
| Refresh fails with **HTTP 429** | Rate limit (10 requests/min). Only happens if something refreshes in a tight loop — bump the refresh interval back up. |
| A finished match shows blank goals | Its `status` isn't `FINISHED` yet. The feed marks matches final within minutes of the whistle; refresh again shortly. |
| A team's points are stuck at 0 | Name mismatch: the spelling in `Teams[Team]` (or a pick) doesn't exactly match the API's. Re-run the `UNIQUE(VSTACK(...))` formula from §5 and compare. This is the #1 failure mode — it fails *silently*, which is why the Teams sheet is built by pasting API values instead of typing names. |
| Knockout match decided on penalties scored wrong | It isn't — `WinnerName` comes from `score.winner`, which already reflects the shootout. The `Duration` column (`PENALTY_SHOOTOUT`) is informational only. |
| Excel asks for credentials again | Choose **Anonymous**. The token header in the query is the real auth. |

---

*Scoring rules and API integration mirror the production Corrupt Commish Club World Cup
Fantasy Pool (cccfantasy.com) as of June 2026.*
