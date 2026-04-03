# 2026 FIFA World Cup Fantasy Pool — Game Design Document (v6)

**Format:** Pick-and-hold country fantasy pool · 20–50 players · Picks lock before kickoff (June 11, 2026)

---

## How It Works

Each player selects **9 national teams** across 5 tiers before the tournament starts. Points accumulate as those teams win matches and advance through the bracket. Lower-tier teams carry higher multipliers. Every player can choose from all 48 countries to assemble their lineup so long as they adhere to the rules and structure outlined below.

---

## Tier Structure

| Tier | Name | Picks | Multiplier | Countries |
|------|------|-------|-----------|-----------|
| **1** | Favorites | 2 | ×1 | Spain, France, England, Argentina, Brazil, Portugal, Germany |
| **2** | Contenders | 1 | ×1.5 | Netherlands, Norway, Belgium, Colombia |
| **3** | Dark Horses | 2 | ×2.5 | USA, Morocco, Japan, Uruguay, Mexico, Switzerland, Türkiye, Ecuador, Sweden, Croatia, Senegal |
| **4** | Underdogs | 2 | ×4 | Austria, Canada, Paraguay, Czechia, Scotland, Côte d'Ivoire, Egypt, Ghana, Bosnia & Herzegovina, Algeria, South Korea |
| **5** | Wildcards | 2 | ×7 | Iran, Australia, Tunisia, DR Congo, Saudi Arabia, South Africa, Panama, Qatar, Iraq, New Zealand, Cape Verde, Uzbekistan, Jordan, Curaçao, Haiti |

**Total: 9 picks from 48 teams.** Each team can only be selected once per entry.

Tiers are based on April 2026 sportsbook outright-winner odds aggregated across four major books (DraftKings, FanDuel, Caesars, BetMGM) and validated through K-means and hierarchical clustering analysis on log-transformed odds. Full rationale in the Design Notes section.

---

## Scoring System

Points come from two sources: **group stage results** and **knockout stage results**, both multiplied by the team's tier multiplier.

### Group Stage

**Match results (scored every game day):**

| Result | Base Points |
|--------|------------|
| Win | 3 |
| Draw | 1 |
| Loss | 0 |

**Advancement milestones (awarded after group stage concludes):**

| Milestone | How Earned | Base Points |
|-----------|-----------|------------|
| Win Group | Finish 1st in group | 4 |
| Advance as Runner-Up | Finish 2nd in group | 3 |
| Advance as Best 3rd | Finish 3rd but among best 8 of 12 third-place teams | 1 |

### Knockout Stage

Each knockout result has a single point value. There are no separate "match points" and "milestone" categories — the value below is the total earned for that result.

| Result | Base Points |
|--------|------------|
| Win R32 | 8 |
| Win R16 | 11 |
| Win QF | 15 |
| Win SF | 19 |
| **Champion** | **50** |
| Runner-Up | 8 |
| Win 3rd-Place Match | 8 |

> The Champion earns 50 base points for winning the Final — the single largest scoring event in the game. The Runner-Up earns 8 base points for losing the Final.

### Why Graduated Group Advancement?

The 2026 World Cup uses a new 48-team format where 32 of 48 teams advance (66.7%). A flat advancement bonus would give nearly free points to strong teams. The graduated system rewards **how** you advance:

- **Win group (4 pts):** You dominated. Full credit.
- **Runner-up (3 pts):** You advanced comfortably. Most of the credit.
- **Best 3rd (1 pt):** You scraped through. Token credit — now prove it in the knockouts.

This also adds a strategic layer: when picking teams, you're not just asking "will they advance?" but "will they top the group?" A group winner earns 4× the milestone points of a third-place qualifier.

---

## Points Per Achievement by Tier

| Achievement | Base | Tier 1 (×1) | Tier 2 (×1.5) | Tier 3 (×2.5) | Tier 4 (×4) | Tier 5 (×7) |
|-------------|------|-------------|---------------|---------------|-------------|-------------|
| Group Win | 3 | 3 | 4.5 | 7.5 | 12 | 21 |
| Group Draw | 1 | 1 | 1.5 | 2.5 | 4 | 7 |
| Win Group | 4 | 4 | 6 | 10 | 16 | 28 |
| Advance Runner-Up | 3 | 3 | 4.5 | 7.5 | 12 | 21 |
| Advance Best 3rd | 1 | 1 | 1.5 | 2.5 | 4 | 7 |
| Win R32 | 8 | 8 | 12 | 20 | 32 | 56 |
| Win R16 | 11 | 11 | 16.5 | 27.5 | 44 | 77 |
| Win QF | 15 | 15 | 22.5 | 37.5 | 60 | 105 |
| Win SF | 19 | 19 | 28.5 | 47.5 | 76 | 133 |
| **Champion** | **50** | **50** | **75** | **125** | **200** | **350** |
| Runner-Up | 8 | 8 | 12 | 20 | 32 | 56 |
| Win 3rd Place | 8 | 8 | 12 | 20 | 32 | 56 |

---

## Example Scoring Scenarios

### Spain + Argentina (both Tier 1, ×1) — Spain wins the World Cup, Argentina loses in QF

**Spain** — 3 group wins, wins every knockout round, champion:

| Source | Points |
|--------|--------|
| Group results (3W) | 9 |
| Win Group | 4 |
| Win R32 | 8 |
| Win R16 | 11 |
| Win QF | 15 |
| Win SF | 19 |
| Champion | 50 |
| **Raw total** | **116** |
| **× Tier 1 (×1)** | **116 pts** |

**Argentina** — 2 group wins, 1 draw, wins R32 and R16, loses in QF:

| Source | Points |
|--------|--------|
| Group results (2W, 1D) | 7 |
| Win Group | 4 |
| Win R32 | 8 |
| Win R16 | 11 |
| **Raw total** | **30** |
| **× Tier 1 (×1)** | **30 pts** |

**Combined Tier 1 total: 146 pts**

---

### Norway (Tier 2, ×1.5) reaches the Final — loses

| Source | Points |
|--------|--------|
| Group results (2W, 1D) | 7 |
| Advance Runner-Up | 3 |
| Win R32 | 8 |
| Win R16 | 11 |
| Win QF | 15 |
| Win SF | 19 |
| Runner-Up | 8 |
| **Raw total** | **71** |
| **× Tier 2 (×1.5)** | **106.5 pts** |

> Spain's undefeated championship (116) outscores Norway's runner-up finish (106.5) by 9.5 points. The multiplier rewards Norway's upset run, but picking the actual World Cup champion is still worth more.

---

### Senegal (Tier 3, ×2.5) wins group, reaches QF, loses

| Source | Points |
|--------|--------|
| Group results (2W, 1D) | 7 |
| Win Group | 4 |
| Win R32 | 8 |
| Win R16 | 11 |
| **Raw total** | **30** |
| **× Tier 3 (×2.5)** | **75 pts** |

---

### Canada (Tier 4, ×4) surprises with an R16 run

| Source | Points |
|--------|--------|
| Group results (1W, 2D) | 5 |
| Advance Runner-Up | 3 |
| Win R32 | 8 |
| **Raw total** | **16** |
| **× Tier 4 (×4)** | **64 pts** |

> A modest Tier 4 run — one knockout win — still produces 64 pts. The ×4 multiplier makes every Underdog knockout match a leaderboard event.

---

### Iran (Tier 5, ×7) Cinderella run to QF — squeaks through groups, loses in QF

| Source | Points |
|--------|--------|
| Group results (1W, 1D, 1L) | 4 |
| Advance Best 3rd | 1 |
| Win R32 | 8 |
| Win R16 | 11 |
| **Raw total** | **24** |
| **× Tier 5 (×7)** | **168 pts** |

> Iran's miracle QF run produces 168 points — the highest single-team score in any of these examples. But it required winning two knockout matches as a +40,000 longshot. The ×7 multiplier rewards the pick massively when it hits, but the probability is extremely low. Meanwhile, the undefeated World Cup Champion (Spain, 116 pts at ×1) still anchors the portfolio as the highest-floor pick in the game.

---

### Curaçao (Tier 5, ×7) exits in groups — 3 losses

> **0 pts.** That's the risk of a Wildcard pick.

---

## Podium Scoring Proof

The Champion must always outscore the Runner-Up, and the Runner-Up must always outscore Third Place, regardless of how matches are decided. Here are the worst-case comparisons for teams in the same tier:

| Finish | Scenario | Raw Total |
|--------|----------|-----------|
| **Champion** (worst case) | 0W 3D in group, advance best 3rd, win R32–Final | 3+1+8+11+15+19+50 = **107** |
| **Runner-Up** (best case) | 3W in group, win group, win R32–SF, lose Final | 9+4+8+11+15+19+8 = **74** |
| **Runner-Up** (worst case) | 0W 3D in group, advance best 3rd, win R32–SF, lose Final | 3+1+8+11+15+19+8 = **65** |
| **3rd Place** (best case) | 3W in group, win group, win R32–QF, lose SF, win 3rd | 9+4+8+11+15+8 = **55** |
| **4th Place** (best case) | 3W in group, win group, win R32–QF, lose SF, lose 3rd | 9+4+8+11+15 = **47** |

> Champion (107) > Runner-Up (74) > 3rd Place (55) > 4th Place (47) — even comparing the worst champion against the best runner-up, the gap is 33 raw points. Apply any multiplier and the ordering holds.

### Cross-Tier Validation

An undefeated Tier 1 champion outscores a best-case Tier 2 runner-up in all realistic scenarios:

| Scenario | Points |
|----------|--------|
| T1 undefeated champion (3W group, win group) | 116 × 1 = **116** |
| T2 best-case runner-up (3W group, win group, win R32–SF, lose Final) | 74 × 1.5 = **111** |
| **T1 wins by 5** | |

Even a T1 champion with a mediocre group stage (2W 1L, runner-up advance) scores 112, still edging the best-case T2 runner-up (111). A Tier 3 runner-up (74 × 2.5 = 185) can outscore a Tier 1 champion — a team making the Final from that tier would be a 2022-Morocco-level upset, and the multiplier rewards that appropriately.

---

## Tiebreaker

If players are tied on total points:

1. **First tiebreaker:** Closest guess to USA's total goals scored in the tournament (submitted at pick time).
2. **If still tied:** Co-champions.

---

## Edge Cases & Admin Rules

**Team withdrawal or disqualification:** If a team withdraws or is disqualified before the tournament, players who selected that team may substitute any available team from the same tier. If withdrawal occurs mid-tournament, all points earned to that point stand; no future points are awarded.

**Forfeited matches:** A forfeit counts as a 3-0 win/loss. The winning team earns 3 match points; the losing team earns 0. Advancement milestones are awarded based on final group/bracket standings regardless of how results were achieved.

**Replayed matches:** If FIFA orders a match replayed, only the replay result counts for scoring.

**Walkovers in the knockout round:** If a team receives a walkover (opponent unable to play), the advancing team earns the applicable knockout round points.

**Third-place match opt-out:** If FIFA modifies or cancels the third-place match, the "Win 3rd-Place Match" milestone is void. Both semifinal losers receive 3 milestone points as consolation.

**Extra time:** Extra time is part of the match. A win decided in extra time is a win. A loss in extra time is a loss. There is no separate scoring for extra time.

**Penalty shootouts:** A penalty shootout is how the match is decided, not a separate event. The team that advances earns the knockout round points; the team eliminated earns 0.

**Best third-place determination:** If FIFA's official third-place rankings require tiebreakers (goal difference, fair play, etc.), the pool uses FIFA's official determination. We do not independently calculate third-place rankings.

**Red cards, yellow cards, and suspensions:** These have no scoring impact. Only match results and advancement matter.

**Own goals:** Goals scored do not factor into pool scoring. Only match results (W/D/L) matter. An own goal that changes a match result is reflected in the match result points, not separately.

---

## Design Notes

### Tier Assignment Methodology

Tier assignments are based on outright-winner odds from four major US sportsbooks (DraftKings, FanDuel, Caesars, BetMGM) collected in late March 2026. For each team, the average and median odds were computed. Teams were then clustered using K-means and hierarchical (Ward's method) clustering on log-transformed average odds. Both algorithms produced identical groupings, with four natural break points validated by the largest log-scale gaps in the data:

| Boundary | Log₁₀ Gap | Between |
|----------|----------|---------|
| Tier 1 → 2 | 0.201 | Germany (+1,275) → Netherlands (+2,025) |
| Tier 2 → 3 | 0.118 | Colombia (+4,000) → USA (+5,250) |
| Tier 3 → 4 | 0.130 | Senegal (+9,275) → Austria (+12,500) |
| Tier 4 → 5 | 0.143 | South Korea (+28,750) → Iran (+40,000) |

Silhouette score analysis confirmed k=4 (for non-Tier-1 teams) as the optimal cluster count, producing a silhouette coefficient of 0.643.

### Tier 1 — Favorites (7 teams, pick 2, ×1)

**Spain, France, England, Argentina, Brazil, Portugal, Germany**

The seven teams with the shortest outright-winner odds. Spain (+440) leads the field; Germany (+1,275) sits at the back of this tier with a clear gap to the next cluster. Two picks here means your Tier 1 pair is the backbone of your entry — if one wins the tournament, the 50-point Champion bonus is the single largest raw scoring event in the game. If both reach the quarterfinals or beyond, the combined late-stage milestones create a formidable floor.

### Tier 2 — Contenders (4 teams, pick 1, ×1.5)

**Netherlands, Norway, Belgium, Colombia**

Four teams clustered at +2,000 to +4,000 odds. Netherlands is the class of the tier; Norway's perfect UEFA qualifying campaign earned them +2,625 odds; Belgium's golden generation has aged but they still carry +3,325 implied quality; Colombia rounds out the tier at +4,000. The ×1.5 multiplier means a deep Contender run generates more points per match than Tier 1.

*Strategic tradeoff:* Only 4 options — every pick is defensible, and your single selection here is a true pivot point that defines your portfolio's secondary anchor. Expect heavy selection on Netherlands and Norway.

### Tier 3 — Dark Horses (11 teams, pick 2, ×2.5)

**USA, Morocco, Japan, Uruguay, Mexico, Switzerland, Türkiye, Ecuador, Sweden, Croatia, Senegal**

The deepest strategic tier. Morocco (+5,650, 2022 semifinalist) and Croatia (+7,775, 2022 semifinalist and 2018 finalist) carry recent deep-run pedigree but their odds place them here, not in Tier 2. The USA (+5,250) benefits from home-field advantage across 11 host cities. Japan's pressing system dismantled Germany and Spain in 2022. Türkiye and Sweden arrive via strong qualifying campaigns. Senegal (+9,275) sits at the tier's edge — the last team before a significant odds gap.

*Strategic tradeoff:* Two picks from 11 teams (55 combinations). This is where roster differentiation happens in the middle of the board. A correct call on which dark horse makes a quarterfinal run will separate contenders from the pack.

### Tier 4 — Underdogs (11 teams, pick 2, ×4)

**Austria, Canada, Paraguay, Czechia, Scotland, Côte d'Ivoire, Egypt, Ghana, Bosnia & Herzegovina, Algeria, South Korea**

These teams span +12,500 (Austria) to +28,750 (South Korea). They are realistically fighting to advance from their groups and steal a knockout match. At ×4, a group win (12 pts) plus advancement (12–16 pts) plus an R32 victory (32 pts) creates meaningful scoring without requiring a miracle run. South Korea — despite their 2002 semifinal history — lands here on current odds, not reputation.

*Strategic tradeoff:* Identify which of these teams landed in a favorable group draw and has the best path to an R32 win.

### Tier 5 — Wildcards (15 teams, pick 2, ×7)

**Iran, Australia, Tunisia, DR Congo, Saudi Arabia, South Africa, Panama, Qatar, Iraq, New Zealand, Cape Verde, Uzbekistan, Jordan, Curaçao, Haiti**

Two lottery tickets from 15 teams. Most will score zero or near-zero, but with 66.7% of teams advancing from groups, even a Wildcard has a chance of reaching the knockouts — and at ×7, a single R32 win is worth 56 points. Iran (+40,000), Australia (+43,750), and Tunisia (+45,000) are the class of this tier and the only realistic group-stage threats. Below them, the odds stretch to +175,000 for Curaçao and Haiti.

*Strategic tradeoff:* Iran and Australia are the clear value picks. The rest are true long shots where group draw luck is everything. Two picks from 15 teams gives 105 possible pairs.

### Why These Multipliers? (×1 / ×1.5 / ×2.5 / ×4 / ×7)

The multipliers are calibrated so that no tier dominates expected value, while preserving a deliberate top-heaviness that rewards knowledge over lottery tickets. An undefeated Tier 1 World Cup champion outscores a best-case Tier 2 runner-up in all realistic scenarios — picking the actual winner should feel like the best decision in the game. Lower-tier multipliers amplify Cinderella moments without letting a single upset run override the champion.

| Tier | Picks | Avg Raw EV | Mult | EV/Pick | Tier EV | % of Portfolio |
|------|-------|-----------|------|---------|---------|----------------|
| 1 | 2 | ~46 | ×1 | ~46 | ~92 | 31% |
| 2 | 1 | ~24 | ×1.5 | ~36 | ~36 | 12% |
| 3 | 2 | ~13 | ×2.5 | ~33 | ~65 | 22% |
| 4 | 2 | ~7 | ×4 | ~28 | ~56 | 19% |
| 5 | 2 | ~4 | ×7 | ~25 | ~50 | 17% |
| | **9** | | | | **~299** | |

The EV per pick ranges from ~25 (Tier 5) to ~46 (Tier 1), a max/min ratio of 1.84×. Tiers 1 and 2 are hot by design — this ensures that correct top-tier selections and late-tournament knockout results determine the winner, not a lucky Wildcard flyer. Tier 5 trades expected value for variance: most tickets lose, but the winners pay big.

### Why the Podium Bonuses? (Champion 50 / Runner-Up 8 / 3rd Place 8)

The Champion bonus (50 base pts) is the single largest scoring event in the game — more than double the Semifinal round (19). Picking the World Cup winner should be the most rewarding individual outcome. The scoring is designed so that a Tier 1 undefeated champion (116 pts) outscores a best-case Tier 2 runner-up (111 pts), ensuring the actual World Cup winner anchors the top of the leaderboard.

The Runner-Up bonus (8) ensures the team that loses the Final still outscores the third-place finisher in every possible scenario, rewarding players who correctly identified a finalist. The Runner-Up and Win 3rd Place bonuses are both 8 base points, but the Runner-Up's path includes a Win SF (19 pts) that the 3rd-place finisher did not earn, guaranteeing the podium ordering holds.

### Why Graduated Group Advancement? (4 / 3 / 1)

With 32 of 48 teams advancing, group qualification is no longer the survival test it was in the 32-team era. The graduated system prevents "free" advancement points for strong teams:

- A Tier 5 group winner earns **28 pts** (4 × 7) — a massive haul for a Wildcard pick.
- A Tier 1 best-third qualifier earns **1 pt** — a token acknowledgment, not a windfall.

### How Many Unique Lineups Exist?

| Tier | Teams | Picks | Combinations |
|------|-------|-------|-------------|
| 1 | 7 | 2 | 21 |
| 2 | 4 | 1 | 4 |
| 3 | 11 | 2 | 55 |
| 4 | 11 | 2 | 55 |
| 5 | 15 | 2 | 105 |
| **Total unique lineups** | | | **26,680,500** |

With ~26.7 million possible lineups and 20–50 players, virtually every entry will be unique.

---

## Administration Notes

### Score Update Cadence

During the group stage (June 11–26), multiple matches occur daily. Scores should be updated at least once per day, ideally after each match day concludes. During the knockout stage, matches are less frequent and each result is higher-stakes — update promptly after each match.

### What the Admin Tracks

For each completed match, the admin records: the two teams, the match result (W/D/L for group; advance/eliminated for knockout), and the applicable knockout round points. The system calculates multiplied scores automatically.

At the end of the group stage, the admin confirms: which teams advanced, their advancement method (group winner, runner-up, or best third), and the R32 bracket.

### Data Source

Primary: FIFA's official match results and standings. Fallback: manual entry from live broadcast or FIFA.com. The system will support both API-driven updates and manual entry.

---

## 2026 World Cup Format (Quick Reference)

- **48 teams** in 12 groups of 4 (new expanded format)
- Top 2 per group + best 8 third-place teams advance (**32 teams** reach knockouts)
- Knockout bracket: R32 → R16 → QF → SF → 3rd-place match → Final
- **104 total matches** across 39 days (June 11 – July 19, 2026)
- Hosted across USA (11 cities), Mexico (3 cities), and Canada (2 cities)
- Final at MetLife Stadium, East Rutherford, NJ

---

*Pool administered by Brad Hagstrom. Questions? Disputes? Complaints about your Wildcard picks? You know where to find me.*
