# World Cup 2026 — Fantasy Pool Scoring Audit & Optimal Lineup

_Analysis date: 2026-06-03 · picks lock June 11 · 48 teams, 104 matches_

## TL;DR

- **Scoring audit: PASS / PASS / PASS.** No catastrophic flaw. The multipliers are well-balanced (mean EV per tier is flat across T1–T4), the tier assignments match the betting-market ordering exactly, and the fixed 2/1/2/2/2 pick structure makes a tier-loading exploit impossible. Largest best-pick EV gap between any two tiers is **23 points — well under the 50-point catastrophic bar.** No change recommended.
- **Optimal EV lineup** (expected total ≈ **429** multiplied points): Spain, England, Belgium, Switzerland, United States, Canada, Austria, Iran, Australia.

---

## 1. Methodology

**Objective.** Expected fantasy points are driven by *how far a team advances* (points accrue at every round), not by championship odds alone — so a strength-calibrated Monte Carlo of the whole tournament is required, scored with the exact production scoring rules.

**Data (pulled June 2–3, 2026).** Consensus outright-winner odds for all 48 teams (Yahoo + ESPN boards, de-vigged to sum to 100%); plus FOX Sports stage markets — *reach Round-of-16*, *reach Quarterfinal*, and *advance from group* — used as multi-stage calibration anchors. The group-advance market was de-vigged **within each group** (exactly 2 of 4 advance) to remove a cross-group inconsistency in the raw prices.

**Model.** Each team gets a strength rating. Matches are simulated as Poisson scorelines (rating gap → goal supremacy); knockout ties resolve by a strength-weighted ET/penalty draw. The real Dec-2025 group draw is used; the knockout bracket is pot-protective (group winners shielded in the Round of 32, random thereafter), with a knockout-determinism parameter tuned so favorites' deep-run rates match the market. Team strengths are fit by coordinate-ascent to the market stage probabilities (28 iterations).

**Scoring fidelity.** The scoring constants and tier/multiplier/group data are imported **directly from the repo** (`games/worldcup/constants.py`, `world_cup_countries.py`) so they cannot drift from production. The base-point ladder is asserted before any output is trusted: advance-only=13, lose-R16=21, lose-QF=32, reach-SF=47, 3rd=55, runner-up=74, champion=116. Final run: **200,000 simulated tournaments.**

**Stability.** Re-running on an independent seed moves every team's EV by less than **±0.3** points — conclusions are not Monte-Carlo noise.

**Calibration check — simulation vs. market:**

| Team | Tier | Champion % (mkt) | Champion % (sim) | Reach-QF % (mkt) | Reach-QF % (sim) |
| --- | --- | --- | --- | --- | --- |
| Spain | 1 | 14.4 | 13.4 | 58.6 | 55.7 |
| France | 1 | 14.1 | 12.5 | 59.3 | 51.9 |
| England | 1 | 10.8 | 13.2 | 56.4 | 54.8 |
| Brazil | 1 | 8.8 | 8.8 | 48.8 | 49.3 |
| Argentina | 1 | 8.6 | 8.5 | 47.6 | 48.2 |
| Portugal | 1 | 7.7 | 9.1 | 48.8 | 49.1 |
| Germany | 1 | 5.4 | 5.1 | 38.9 | 39.9 |
| Netherlands | 2 | 3.7 | 6.1 | 38.9 | 39.5 |
| Belgium | 2 | 2.3 | 6.1 | 42.3 | 42.6 |
| United States | 3 | 1.7 | 2.0 | 26.5 | 26.6 |
| Mexico | 3 | 1.1 | 1.7 | 25.1 | 25.8 |
| Morocco | 3 | 1.8 | 1.0 | 21.6 | 21.8 |
| South Korea | 4 | 0.3 | 0.2 | 10.0 | 10.0 |

**Limitations / confidence.** Qualitative findings (no 50-pt gap, monotonic tiering, no structural exploit) are robust to model error. Exact *within-tier* EV ordering is less certain where teams cluster (notably the T3 pack and the T5 wildcards, whose EV leans on the softer group-advance market). A single-strength model also slightly compresses the very top of the title market (e.g. Belgium's championship odds are modestly overstated), so treat T1/T2 internal gaps as near-ties — see close-call flags in §3.

---

## 2. Scoring Audit

### Tier EV summary (multiplied points)

| Tier | Name | ×mult | # teams | Best pick | 2nd | Median | Mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Favorites | 1.0 | 7 | 40.8 | 40.1 | 34.9 | 35.7 |
| T2 | Contenders | 1.5 | 4 | 44.9 | 40.9 | 35.6 | 36.5 |
| T3 | Dark Horses | 2.5 | 11 | 50.8 | 47.8 | 40.1 | 39.8 |
| T4 | Underdogs | 4.0 | 11 | 64.3 | 58.2 | 42.6 | 37.3 |
| T5 | Wildcards | 7.0 | 15 | 41.8 | 40.1 | 17.9 | 22.5 |

### Check A — does any tier's expected points exceed another by 50+?

Per-slot best-pick EV by tier: T1=40.8, T2=44.9, T3=50.8, T4=64.3, T5=41.8. **Largest gap = 23.5** (T4 vs T1). Mean tier EVs are flat for T1–T4 (~36–40) and lowest for T5 (~22).

**Verdict: PASS.** No tier's expected points exceed another's by anywhere near 50.

### Check B — is any team catastrophically mis-tiered vs. current odds?

Ranking all 48 teams by market strength (championship odds + reach-QF) is **perfectly monotonic with the tier bands**: strength ranks 1–7 are exactly the seven Tier-1 teams, ranks 8–11 are exactly the four Tier-2 teams, then Tier 3, and so on. No favorite is sitting in a low tier and no longshot is over-tiered. No single team is so dominant that skipping it is disqualifying — the best Tier-4 pick leads the third-best by only ~14 EV.

**Verdict: PASS.**

### Check C — does the pick structure create a tier-loading exploit?

The structure fixes the tier counts (2×T1, 1×T2, 2×T3, 2×T4, 2×T5), so **every entrant takes the identical tier allocation** — there is no freedom to overweight a single dominant tier. Combined with Check A (no tier dominates by 50+), no tier-combination exploit exists. The only lever is *which* team to pick inside each tier, which is the intended skill of the game.

**Verdict: PASS.**

### Non-catastrophic observation (informational — no action)

Tier 4 (Underdogs, ×4) is the richest tier and Tier 5 (Wildcards, ×7) is a low-floor lottery: the ×7 multiplier doesn't fully compensate for how rarely wildcards advance (T5 mean EV ≈ 22, the lowest of any tier), while ×4 hits the sweet spot of teams good enough to escape their group and occasionally win a knockout match. This is intentional risk/reward texture, it is identical for every entrant, and **changing live multipliers after picks have started flowing in would itself be unfair.** Leave as-is; revisit only as a design tweak for a future edition.

---

## 3. Optimal EV Lineup

_Pure expected value (each pick scores independently, so the EV-optimal lineup is simply the highest-EV team in each required slot)._

| Slot | Pick | Group | EV | Rationale (odds / EV) |
| --- | --- | --- | --- | --- |
| T1 ×1.0 | **Spain** | H | 40.8 | Co-favorite; best reach-QF in the field. |
| T1 ×1.0 | **England** | L | 40.1 | Elite deep-run odds; ~tied with France. |
| T2 ×1.5 | **Belgium** | G | 44.9 | Top Tier-2 by stage odds — best ×1.5 value. |
| T3 ×2.5 | **Switzerland** | B | 50.8 | Best Tier-3 deep-run rate; clear tier leader. |
| T3 ×2.5 | **United States** | D | 47.8 | Host, soft Group D path. |
| T4 ×4.0 | **Canada** | B | 64.3 | Highest EV on the board — host in weak Group B, ×4 on near-certain advancement. |
| T4 ×4.0 | **Austria** | J | 58.2 | Likely Group J runner-up behind Argentina; ×4 on a reliable advancer. |
| T5 ×7.0 | **Iran** | G | 41.8 | Best ×7 advancer (Group G); top wildcard ceiling. |
| T5 ×7.0 | **Australia** | D | 40.1 | Next-best ×7 advancer. |
|  |  |  | **≈429** | **expected total** |

**Strategic logic.** Value concentrates in the *amplified-advancer* zone — Tier 4 (×4) and the strong end of Tier 5 (×7) — because a team that reliably escapes its group and wins one knockout game out-scores a ×1 favorite reaching the same round. So the lineup anchors Tier 4 hard (Canada and Austria are the two richest single slots in the pool), takes the best deep-run favorites where the multiplier is flat (Spain/England, Belgium), and uses the strongest *advancers* in the lottery tiers rather than reaching for upside.

**Close calls (your judgment):**
- **T1:** England (40.1) is essentially tied with France (37.4).
- **T3:** United States (47.8) is essentially tied with Mexico (47.2), Uruguay (45.6), Morocco (44.5).
- **T5:** Australia (40.1) is essentially tied with Tunisia (39.0) — and these wildcards are the most model-sensitive picks.

> Note: this is the EV-maximizing lineup. EV-max is not the same as win-probability-max in a small pool — this lineup is fairly chalky at the top of each tier. Optimizing to *win* (rather than score most on average) would deliberately fade some chalk for contrarian high-multiplier swings; that version was not requested here.

---

## 4. Full per-team EV table

Sorted by tier, then EV. `Champ%/Adv%/R16%/QF%/SF%` = simulated probability of winning the title / advancing from group / reaching each round. `E[base]` = expected base points; `EV` = expected **multiplied** points (E[base] × tier multiplier).

| Team | Grp | Tier | ×mult | Champ% | Adv% | R16% | QF% | SF% | E[base] | EV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Spain | H | T1 | 1.0 | 13.43 | 98.0 | 81.1 | 55.7 | 36.3 | 40.83 | 40.83 |
| England | L | T1 | 1.0 | 13.22 | 97.2 | 80.0 | 54.8 | 35.6 | 40.12 | 40.12 |
| France | I | T1 | 1.0 | 12.48 | 93.4 | 75.9 | 51.9 | 33.9 | 37.39 | 37.39 |
| Brazil | C | T1 | 1.0 | 8.80 | 98.1 | 77.7 | 49.3 | 29.3 | 34.93 | 34.93 |
| Portugal | K | T1 | 1.0 | 9.05 | 96.9 | 77.0 | 49.1 | 29.4 | 34.81 | 34.81 |
| Argentina | J | T1 | 1.0 | 8.46 | 96.6 | 76.2 | 48.2 | 28.5 | 34.02 | 34.02 |
| Germany | E | T1 | 1.0 | 5.15 | 94.7 | 68.5 | 39.9 | 21.4 | 27.55 | 27.55 |
| Belgium | G | T2 | 1.5 | 6.09 | 95.0 | 71.8 | 42.6 | 23.5 | 29.94 | 44.91 |
| Netherlands | F | T2 | 1.5 | 6.07 | 86.0 | 64.8 | 39.5 | 22.5 | 27.26 | 40.88 |
| Norway | I | T2 | 1.5 | 2.53 | 85.6 | 56.0 | 29.1 | 13.8 | 20.19 | 30.29 |
| Colombia | K | T2 | 1.5 | 1.70 | 92.7 | 57.3 | 26.9 | 11.5 | 20.08 | 30.11 |
| Switzerland | B | T3 | 2.5 | 1.31 | 96.1 | 57.4 | 25.6 | 10.2 | 20.31 | 50.77 |
| United States | D | T3 | 2.5 | 1.97 | 83.2 | 53.6 | 26.6 | 12.1 | 19.12 | 47.81 |
| Mexico | A | T3 | 2.5 | 1.69 | 85.5 | 53.7 | 25.8 | 11.3 | 18.90 | 47.25 |
| Uruguay | H | T3 | 2.5 | 1.14 | 92.6 | 52.2 | 23.1 | 9.2 | 18.23 | 45.58 |
| Morocco | C | T3 | 2.5 | 1.05 | 94.2 | 49.8 | 21.8 | 8.5 | 17.80 | 44.49 |
| Croatia | L | T3 | 2.5 | 0.85 | 89.6 | 45.2 | 19.2 | 7.3 | 16.06 | 40.14 |
| Turkey | D | T3 | 2.5 | 0.92 | 79.1 | 43.5 | 19.1 | 7.4 | 15.07 | 37.67 |
| Ecuador | E | T3 | 2.5 | 0.60 | 87.5 | 41.3 | 16.7 | 6.0 | 14.33 | 35.83 |
| Japan | F | T3 | 2.5 | 0.76 | 73.1 | 38.3 | 16.6 | 6.5 | 13.30 | 33.25 |
| Senegal | I | T3 | 2.5 | 0.41 | 75.9 | 33.4 | 13.1 | 4.5 | 11.62 | 29.05 |
| Sweden | F | T3 | 2.5 | 0.34 | 67.3 | 29.9 | 11.3 | 3.8 | 10.50 | 26.24 |
| Canada | B | T4 | 4.0 | 0.45 | 94.3 | 44.9 | 16.9 | 5.6 | 16.07 | 64.29 |
| Austria | J | T4 | 4.0 | 0.51 | 88.5 | 41.1 | 16.0 | 5.6 | 14.56 | 58.23 |
| Ivory Coast | E | T4 | 4.0 | 0.32 | 85.0 | 36.1 | 13.2 | 4.2 | 12.52 | 50.09 |
| Egypt | G | T4 | 4.0 | 0.21 | 83.5 | 33.9 | 11.4 | 3.3 | 12.13 | 48.51 |
| Czech Republic | A | T4 | 4.0 | 0.23 | 75.1 | 31.6 | 10.8 | 3.2 | 11.12 | 44.47 |
| South Korea | A | T4 | 4.0 | 0.18 | 73.8 | 30.1 | 10.0 | 2.9 | 10.66 | 42.64 |
| Paraguay | D | T4 | 4.0 | 0.04 | 60.1 | 19.2 | 5.1 | 1.1 | 7.47 | 29.88 |
| Algeria | J | T4 | 4.0 | 0.00 | 58.4 | 8.9 | 1.1 | 0.1 | 5.43 | 21.73 |
| Scotland | C | T4 | 4.0 | 0.00 | 56.1 | 5.5 | 0.4 | 0.0 | 4.72 | 18.89 |
| Ghana | L | T4 | 4.0 | 0.00 | 48.9 | 5.8 | 0.6 | 0.0 | 4.43 | 17.71 |
| Bosnia & Herzegovina | B | T4 | 4.0 | 0.00 | 40.5 | 1.6 | 0.1 | 0.0 | 3.44 | 13.75 |
| Iran | G | T5 | 7.0 | 0.00 | 60.2 | 11.0 | 1.7 | 0.2 | 5.97 | 41.76 |
| Australia | D | T5 | 7.0 | 0.01 | 50.8 | 12.6 | 2.5 | 0.4 | 5.73 | 40.11 |
| Tunisia | F | T5 | 7.0 | 0.02 | 47.1 | 12.9 | 3.0 | 0.6 | 5.57 | 38.96 |
| South Africa | A | T5 | 7.0 | 0.00 | 39.1 | 5.9 | 0.7 | 0.1 | 4.02 | 28.14 |
| DR Congo | K | T5 | 7.0 | 0.00 | 45.5 | 4.2 | 0.3 | 0.0 | 3.99 | 27.94 |
| Saudi Arabia | H | T5 | 7.0 | 0.00 | 38.6 | 2.4 | 0.1 | 0.0 | 3.38 | 23.64 |
| New Zealand | G | T5 | 7.0 | 0.00 | 28.9 | 1.7 | 0.1 | 0.0 | 2.79 | 19.54 |
| Qatar | B | T5 | 7.0 | 0.00 | 27.9 | 0.6 | 0.0 | 0.0 | 2.56 | 17.91 |
| Panama | L | T5 | 7.0 | 0.00 | 25.6 | 1.2 | 0.0 | 0.0 | 2.48 | 17.34 |
| Cape Verde | H | T5 | 7.0 | 0.00 | 26.1 | 0.9 | 0.0 | 0.0 | 2.46 | 17.22 |
| Uzbekistan | K | T5 | 7.0 | 0.00 | 24.4 | 1.0 | 0.0 | 0.0 | 2.36 | 16.52 |
| Jordan | J | T5 | 7.0 | 0.00 | 21.6 | 0.8 | 0.0 | 0.0 | 2.18 | 15.24 |
| Iraq | I | T5 | 7.0 | 0.00 | 18.3 | 1.4 | 0.1 | 0.0 | 2.01 | 14.05 |
| Haiti | C | T5 | 7.0 | 0.00 | 12.9 | 0.2 | 0.0 | 0.0 | 1.49 | 10.44 |
| Curacao | E | T5 | 7.0 | 0.00 | 9.9 | 0.2 | 0.0 | 0.0 | 1.25 | 8.78 |

---

## Appendix — scoring rules (from `constants.py`) & reproduction

- Group: win **3**, draw **1**, loss 0 base pts.
- Advancement: group winner **4**, runner-up **3**, best third **1**.
- Knockout win: R32 **8**, R16 **11**, QF **15**, SF **19**.
- Podium: champion **50**, runner-up **8**, third **8**.
- Multipliers: T1 ×1.0, T2 ×1.5, T3 ×2.5, T4 ×4.0, T5 ×7.0.
- Pick structure: 2×T1, 1×T2, 2×T3, 2×T4, 2×T5 = 9 picks.

_Model: 200,000-tournament Monte Carlo, strengths calibrated to consensus championship + FOX reach-R16 / reach-QF / group-advance markets (June 2–3, 2026). Odds shift daily; re-run before relying on exact numbers near lock._
