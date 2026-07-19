"""Per-state data assembly for the home page (Spec B section 4).

Public entry point: ``build_home_context(user, state)`` dispatches to
one of four private builders based on state, returning a dict the
template consumes via ``**ctx``.
"""
from typing import Any

from flask_login import AnonymousUserMixin
from sqlalchemy.orm import joinedload

from games.registry import (
    available_games,
    coming_soon_games,
    joined_games,
)
from games.worldcup.constants import (
    SEASON_YEAR,
    TOURNAMENT_DEADLINE_UTC,
    WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupRankSnapshot,
    WorldCupTeam,
)
from games.worldcup.services.elimination import eliminated_team_ids
from games.worldcup.services.ranking import compute_rank_neighbors
from games.worldcup.services.scoring import display_points_for_pick_on_match
from games.worldcup.services.stage import best_finish_label
from games.worldcup.services.stage import stage_label as _stage_label
from games.worldcup.services.state import WorldCupState, now_utc
from games.worldcup.world_cup_countries import TIERS
from models.content import commish_note_paragraphs


def build_home_context(user: Any, state: WorldCupState | None) -> dict:
    """Assemble the render context for the home page in the given state.

    state=None for unauthenticated users (logged-out marketing surface).
    For authenticated users, state must be 'pre' | 'live' | 'post'.
    """
    if state is None:
        return _context_out()
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR
    ).first()
    if state == 'pre':
        ctx = _context_pre(user, enrollment)
    elif state == 'live':
        ctx = _context_live(user, enrollment)
    else:
        ctx = _context_post(user, enrollment)
    # Admin-editable "From the Commish" note for the narrative band. The post
    # body may interpolate {champion}, so pass the champion through when set.
    ctx['commish_paragraphs'] = commish_note_paragraphs(
        state, ctx.get('champion_team')
    )
    return ctx


def _tagline_for(rank: int, week_delta_rank: int | None,
                 alive_count: int, is_you: bool = False) -> str | None:
    """Return a contextual one-liner for a leaderboard row, or None.

    Finite string set per Spec B D11 — server-derived from data, not LLM-style
    free-form text.
    """
    if is_you and week_delta_rank is not None:
        if week_delta_rank <= -10:
            return f"Climbed {abs(week_delta_rank)} · the Commish takes notes."
        if week_delta_rank < 0:
            return f"Climbing {abs(week_delta_rank)} spots quietly."
        if week_delta_rank == 0:
            return "Holding steady."
        if week_delta_rank < 10:
            return f"Slipped {week_delta_rank} spots. The Commish notices."
        return f"Down {week_delta_rank} · the Commish averts his eyes."
    # Rank 2 and 3 carried the SAME tagline ("Still warm. Still winning." on
    # both when all 9 were alive), so a top-3 preview stacked the identical
    # line twice — an identical-repeat slop tell against a voice-led brand
    # ($impeccable critique 2026-05-24 r2). Give each podium step its own line.
    if rank == 1:
        return "Paid tribute. Paid off."
    if rank == 2:
        return "Still warm. Still winning." if alive_count == 9 else "Played the favorites."
    if rank == 3:
        return "Breathing down the lead." if alive_count == 9 else "Hanging in the chase."
    return None


def _context_out() -> dict:
    """Logged-out marketing surface — no user, no WC enrollment."""
    anon = AnonymousUserMixin()
    return {
        'available_games': available_games(anon),
        'coming_soon_games': coming_soon_games(),
        'total_enrolled': WorldCupEnrollment.query.filter_by(
            season_year=SEASON_YEAR
        ).count(),
    }


_TIER_SINGULAR = {
    'Favorites': 'Favorite',
    'Contenders': 'Contender',
    'Dark Horses': 'Dark Horse',
    'Underdogs': 'Underdog',
    'Wildcards': 'Wildcard',
}


def _build_roster_spine(picks: list) -> dict:
    """Tier composition + average multiplier for the sealed ballot card.

    Surfaces the WC scoring identity (tiers + multipliers) on the home for
    sealed users, closing the progressive-disclosure gap flagged by the
    post-PR-29 critique. Casual-default, analyst-respected: tier counts
    are scannable in one beat; the avg multiplier rewards the curious.

    Clarify P2 (Critique 2026-05-15) — `tier_breakdown` rows now carry
    a `picks` list per tier so the ballot card spine can render the
    actual country names under each tier label. Previously the spine
    only counted ("2 Favorites · 1 Contender · ..."), forcing the
    sealed user to recall *which* of their nine sat in which tier
    from a row of flag emojis above.
    """
    from collections import Counter
    tier_counts = Counter(p.team.tier for p in picks)
    picks_by_tier: dict[int, list] = {}
    for p in picks:
        picks_by_tier.setdefault(p.team.tier, []).append(p)
    tier_breakdown = []
    for tier_num in (1, 2, 3, 4, 5):
        count = tier_counts.get(tier_num, 0)
        if count <= 0:
            continue
        tier_info = TIERS[tier_num]
        plural_name = tier_info['name']
        name = plural_name if count != 1 else _TIER_SINGULAR.get(plural_name, plural_name)
        tier_breakdown.append({
            'tier': tier_num,
            'count': count,
            'name': name,
            'multiplier': tier_info['multiplier'],
            'picks': picks_by_tier.get(tier_num, []),
        })
    return {
        'tier_breakdown': tier_breakdown,
    }


def _context_pre(user, enrollment) -> dict:
    """Pre-deadline state: countdown card, optional ballot, opening matches."""
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    picks = []
    roster_spine = None
    roster_team_ids = set()
    if is_enrolled and enrollment.picks_submitted:
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        roster_spine = _build_roster_spine(picks)
        roster_team_ids = {p.team_id for p in picks}

    next_3_matches = (
        WorldCupMatch.query
        .filter(WorldCupMatch.kickoff_utc.isnot(None))
        .filter(WorldCupMatch.is_completed == False)  # noqa: E712
        .order_by(WorldCupMatch.kickoff_utc.asc())
        .limit(3)
        .all()
    )

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    # court_line: "Thursday · Tribute window open · 2 days to kickoff"
    now = now_utc()
    now_local = now.astimezone(WORLDCUP_TZ)
    weekday = now_local.strftime('%A')
    delta = TOURNAMENT_DEADLINE_UTC - now
    days = delta.days
    hours = delta.seconds // 3600
    if days > 1:
        proximity = f'{days} days to kickoff'
    elif days == 1:
        proximity = '1 day to kickoff'
    elif hours >= 2:
        proximity = f'{hours} hours to kickoff'
    elif hours == 1:
        proximity = '1 hour to kickoff'
    elif delta.total_seconds() > 0:
        minutes = (delta.seconds // 60) % 60
        proximity = f'{minutes} minute{"s" if minutes != 1 else ""} to kickoff'
    else:
        proximity = 'kickoff imminent'
    # Polish (Critique 2026-05-15) — separator unified to middle dot.
    # `◆` (filled diamond) was a third symbol alongside DESIGN.md's
    # reserved `◈` (ceremonial) + `◇` (informational) eyebrow glyphs;
    # it served only as a separator here. `·` is the canonical CCC
    # text separator and avoids inventing a third diamond register.
    court_line = f'{weekday} · Tribute window open · {proximity}'

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'picks': picks,
        'display_name': display_name,
        'deadline_utc': TOURNAMENT_DEADLINE_UTC,
        'now_utc': now,
        'deadline_ct': deadline_ct,
        'total_enrolled': WorldCupEnrollment.query.filter_by(
            season_year=SEASON_YEAR
        ).count(),
        'next_3_matches': next_3_matches,
        'court_line': court_line,
        'roster_spine': roster_spine,
        'roster_team_ids': roster_team_ids,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
        # Expose stage_label so partials (e.g., _fixture_card.html) can render
        # match.stage through the SSoT mapping instead of falling back to the
        # banned `match.stage|title` filter (DESIGN.md §6 Don't #10; CLAUDE.md
        # "Stage labels"). Jinja's |title mangles ALL-CAPS knockout codes
        # ('SF' -> 'Sf') and underscored values ('third_place' -> 'Third_Place').
        'stage_label': _stage_label,
    }


def _context_live(user, enrollment) -> dict:
    """Live-tournament state: dossier, leaderboard preview, recent results."""
    is_enrolled = enrollment is not None
    now = now_utc()

    # Leaderboard query — used for both rank and top-3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
    total_count = len(all_enrollments)
    top_3 = all_enrollments[:3]

    # Single batched picks fetch for the leaderboard rows we render
    # (top 3 + the viewer if enrolled). Joined with WorldCupTeam so we
    # can derive both alive_count and the viewer's roster set without
    # round-tripping per enrollment.
    relevant_ids = [e.id for e in top_3]
    if is_enrolled and enrollment.id not in relevant_ids:
        relevant_ids.append(enrollment.id)

    picks_by_enr: dict[int, list] = {}
    if relevant_ids:
        # joinedload(WorldCupPick.team) so the roster/leverage builders below
        # can read team display fields without firing one query per pick.
        rows = (
            WorldCupPick.query
            .filter(WorldCupPick.enrollment_id.in_(relevant_ids))
            .options(joinedload(WorldCupPick.team))
            .all()
        )
        for p in rows:
            picks_by_enr.setdefault(p.enrollment_id, []).append(p)

    # Tournament-wide "out" set (group exit OR completed-knockout loss). This is
    # the canonical alive/out read-site per CLAUDE.md — NOT team.is_eliminated,
    # which is group-stage-only and would keep a KO loser counted as "alive."
    eliminated_ids = eliminated_team_ids(SEASON_YEAR)

    def _alive_count(eid: int) -> int:
        return sum(
            1 for p in picks_by_enr.get(eid, [])
            if p.team_id not in eliminated_ids
        )

    user_team_ids: set[int] = set()
    user_picks_by_team_id: dict[int, WorldCupPick] = {}
    if is_enrolled:
        user_team_ids = {p.team_id for p in picks_by_enr.get(enrollment.id, [])}
        for p in picks_by_enr.get(enrollment.id, []):
            user_picks_by_team_id[p.team_id] = p

    dossier = None
    if is_enrolled:
        # Competition rank + lead deltas via the canonical helper. CLAUDE.md
        # mandates competition rank everywhere ("tied scores share a rank, the
        # next distinct score gaps by the size of the tie") — derived once in
        # compute_rank_neighbors() so the lounge stays in lockstep with the WC
        # hub leaderboard for any tied-score pair.
        neighbors = compute_rank_neighbors(enrollment.id)
        user_rank = neighbors['rank']

        # Week-delta + sparkline from snapshot history
        week_delta_rank = None
        week_delta_points = None
        sparkline_data = []
        recent_snapshots = list(reversed(
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_date.desc())
            .limit(7)
            .all()
        ))
        if recent_snapshots:
            sparkline_data = [s.rank for s in recent_snapshots]
            # Only surface the "week delta" trend once we actually have a
            # week of data — otherwise early-deploy days overstate trends
            # (e.g., "you're climbing" computed from a 2-day window).
            if len(recent_snapshots) >= 7:
                oldest = recent_snapshots[0]
                week_delta_rank = user_rank - oldest.rank
                # Suppress the points-delta when the 7-day-ago baseline scored
                # 0: the delta would equal the current total (redundant with
                # the points total already shown, and reads as a glitch —
                # $impeccable critique 2026-05-24). The rank-delta stays; a
                # baseline rank is always meaningful.
                if float(oldest.total_score) > 0:
                    week_delta_points = float(enrollment.total_score) - float(oldest.total_score)

        # Bolder P1 — "Top earner from your nine" extra ledger line,
        # the lounge-canonical-richness signature beyond what the WC hub
        # parity embed renders. Reads as an editorial Tribune callout
        # ("Top earner: 🇺🇸 USA — 7.5 pts") not a stat tile. None when
        # no pick has scored yet (pre-first-result live window); the
        # template guards on truthy.
        user_picks_with_points = picks_by_enr.get(enrollment.id, [])
        top_earner = None
        leader_team_id = None
        if user_picks_with_points:
            best = max(
                user_picks_with_points,
                key=lambda p: float(p.multiplied_points or 0),
            )
            if best.multiplied_points and best.multiplied_points > 0:
                leader_team_id = best.team_id
                top_earner = {
                    'team_code': best.team.fifa_code,
                    'team_iso': best.team.iso_code,
                    'team_name': best.team.display_name,
                    'points': float(best.multiplied_points),
                }

        # Full nine-nation roster ledger for the live home panel — flag, code,
        # name, multiplier, points-so-far, alive/out status. The crowned leader
        # is the same pick as top_earner (one SSoT for "who leads your nine").
        # Deliberately NO per-pick share bars: the lounge keeps the rank
        # sparkline as its signature and leaves the Leverage Board to the WC
        # hub (lounge != hub, games/worldcup/DESIGN.md).
        _STATUS_ORDER = {'scoring': 0, 'dormant': 1, 'out': 2}
        roster = []
        for p in user_picks_with_points:
            pts = float(p.multiplied_points or 0)
            if p.team_id in eliminated_ids:
                status = 'out'
            elif pts > 0:
                status = 'scoring'
            else:
                status = 'dormant'
            roster.append({
                'team_id': p.team_id,
                'iso': p.team.iso_code,
                'code': p.team.fifa_code,
                'name': p.team.display_name,
                'tier': p.team.tier,
                'mult_display': f'{float(p.team.multiplier):g}',
                'multiplier': float(p.team.multiplier),
                'points': pts,
                'status': status,
                'is_leader': p.team_id == leader_team_id,
            })
        # Carriers first (most points on top), then dormant by upside (higher
        # multiplier), then the eliminated tail. Leader lands first.
        roster.sort(key=lambda r: (
            _STATUS_ORDER[r['status']], -r['points'], -r['multiplier'],
        ))

        dossier = {
            'rank': user_rank,
            'total_count': total_count,
            'total_score': enrollment.total_score,
            'alive_count': _alive_count(enrollment.id),
            'week_delta_rank': week_delta_rank,
            'week_delta_points': week_delta_points,
            'sparkline_data': sparkline_data,
            # Bolder P1 — lead-delta line that the WC hub embed already
            # surfaces. Bringing it to the canonical (lounge) surface
            # honors the lounge/room architecture: the lounge should
            # be the richer of the two, not the leaner.
            'lead_delta_up': neighbors['lead_delta_up'],
            'lead_delta_down': neighbors['lead_delta_down'],
            'top_earner': top_earner,
            'roster': roster,
        }

    # Top 3 + you row (if user is enrolled and outside top 3).
    # Competition rank — tied scores share a rank, the next distinct score
    # gaps by the size of the tie (1, 1, 3). Matches WC hub leaderboard idiom
    # (CLAUDE.md "Competition rank everywhere").
    top_3_plus_you = []
    _comp_rank = 0
    _prev_score = None
    for i, enr in enumerate(top_3):
        if enr.total_score != _prev_score:
            _comp_rank = i + 1
        _prev_score = enr.total_score
        top_3_plus_you.append({
            'rank': _comp_rank,
            'enrollment': enr,
            'is_you': is_enrolled and enr.id == enrollment.id,
            'tagline': _tagline_for(_comp_rank, None, _alive_count(enr.id), is_you=False),
        })
    if is_enrolled and dossier and dossier['rank'] and dossier['rank'] > 3:
        top_3_plus_you.append({
            'rank': dossier['rank'],
            'enrollment': enrollment,
            'is_you': True,
            'tagline': _tagline_for(
                dossier['rank'], dossier['week_delta_rank'],
                dossier['alive_count'], is_you=True,
            ),
            'separator_above': True,
        })

    # Recent results — last 5 completed matches
    recent_results = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.kickoff_utc.desc())
        .limit(5)
        .all()
    )

    your_pick_results = []
    for match in recent_results:
        roster_match = None
        points_earned: float | None = None
        podium_label: str | None = None
        # BOTH sides can be on the roster (USA-BEL R16, 2026-07-07): score
        # every matched pick and label the side that earned the points, so the
        # home side never shadows the away side's win.
        matched = [
            (tid, side)
            for tid, side in ((match.home_team_id, 'home'),
                              (match.away_team_id, 'away'))
            if tid in user_team_ids
        ]
        if matched:
            # Display helper folds podium bonuses (champion / runner-up / 3rd)
            # into their deciding match — the base helper renders a won bronze
            # final as 0.0 (the 2026-07-19 England "NO POINTS" incident).
            scored = [
                (tid, side, *display_points_for_pick_on_match(
                    user_picks_by_team_id[tid], match))
                for tid, side in matched
            ]
            points_earned = sum(pts for _, _, pts, _ in scored)
            # max() is stable — a tie (both scoreless, or a shared group draw)
            # keeps the home-side label, matching the prior single-side shape.
            top_tid, top_side, _, _ = max(scored, key=lambda row: row[2])
            roster_match = {'team_id': top_tid, 'side': top_side}
            # Composite label when BOTH finalists are on the roster (the final
            # awards podium bonuses to both sides): points_earned is the sum,
            # so the label must name every contributor — "Champion" alone
            # would misattribute the aggregate. Ordered by points so the
            # champion leads.
            podium_hits = sorted(
                ((pts, code) for _, _, pts, code in scored if code is not None),
                key=lambda hit: hit[0], reverse=True,
            )
            if podium_hits:
                podium_label = ' & '.join(
                    best_finish_label(code) for _, code in podium_hits
                )
        your_pick_results.append({
            'match': match,
            'roster_match': roster_match,
            'points_earned': points_earned,
            'podium_label': podium_label,
            'is_draw': match.is_draw,
            # Display-ready label so the template doesn't fall back to
            # `match.stage|title` (which mangles 'SF' → 'Sf', 'QF' → 'Qf',
            # 'third_place' → 'Third_Place'). _stage_label is the same
            # mapping the court_line uses below — single source of truth.
            'stage_label': _stage_label(match.stage),
        })

    # Court line + stage label
    most_recent = recent_results[0] if recent_results else None
    stage_label = _stage_label(most_recent.stage if most_recent else 'group')
    weekday = now.astimezone(WORLDCUP_TZ).strftime('%A')
    if dossier and dossier['week_delta_rank'] is not None:
        if dossier['week_delta_rank'] < 0:
            trend = "you're climbing"
        elif dossier['week_delta_rank'] == 0:
            trend = "you're holding"
        else:
            trend = "you're slipping"
    else:
        trend = "the Council is in session"
    # Polish (Critique 2026-05-15) — separator unified to middle dot.
    # See _context_pre for the rationale.
    court_line = f'{weekday} · {stage_label} · {trend}'

    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'dossier': dossier,
        'top_3_plus_you': top_3_plus_you,
        'your_pick_results': your_pick_results,
        'court_line': court_line,
        'stage_label': stage_label,
        'display_name': display_name,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }


def _context_post(user, enrollment) -> dict:
    """Post-tournament state: champion banner + podium + roster recap."""
    is_enrolled = enrollment is not None

    # Champion data — match #104. Guards against malformed Final rows
    # (admin manual edit dropping a winner FK to neither side, or scores
    # left null on a row marked complete). In either case we surface the
    # champion banner without the defeat summary rather than silently
    # rendering "Defeated X 0-0" or score-flipped nonsense.
    final_match = WorldCupMatch.query.filter_by(match_number=104).first()
    champion_team = None
    champion_summary = ''
    if final_match and final_match.winner_team_id:
        champion_team = final_match.winner_team
        winner_id = final_match.winner_team_id
        winner_is_home = winner_id == final_match.home_team_id
        winner_is_away = winner_id == final_match.away_team_id
        scores_present = (
            final_match.home_score is not None
            and final_match.away_score is not None
        )
        if (winner_is_home or winner_is_away) and scores_present:
            if winner_is_home:
                loser = final_match.away_team
                winner_score = final_match.home_score
                loser_score = final_match.away_score
            else:
                loser = final_match.home_team
                winner_score = final_match.away_score
                loser_score = final_match.home_score
            suffix = ''
            if final_match.penalties:
                suffix = ' on penalties'
            elif final_match.extra_time:
                suffix = ' in extra time'
            if loser:
                champion_summary = (
                    f'Defeated {loser.display_name} {winner_score}–{loser_score}{suffix}'
                )

    # Final podium — top 3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
    top_3_final = all_enrollments[:3]
    total_count = len(all_enrollments)

    your_final_rank = None
    your_climbed_n = None
    your_roster_recap = []
    if is_enrolled:
        your_final_rank = next(
            (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
            None,
        )
        # Climbed N spots — first snapshot vs latest
        snapshots = (
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_date.asc())
            .all()
        )
        if snapshots and your_final_rank:
            first = snapshots[0]
            your_climbed_n = first.rank - your_final_rank  # positive = climbed

        # Roster recap — every pick with points + best_finish
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        for pick in picks:
            your_roster_recap.append({
                'pick': pick,
                'tier_name': TIERS[pick.tier]['name'],
                'best_finish': best_finish_label(pick.team.best_finish),
                'points': pick.multiplied_points,
                'is_champion': champion_team and pick.team_id == champion_team.id,
            })

    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'champion_team': champion_team,
        'champion_summary': champion_summary,
        'final_match': final_match,
        'top_3_final': top_3_final,
        'total_count': total_count,
        'your_final_rank': your_final_rank,
        'your_climbed_n': your_climbed_n,
        'your_roster_recap': your_roster_recap,
        'display_name': display_name,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }
