"""Shared World Cup test data helpers — used by Plan 4's builder tests
(tests/test_worldcup_home_context.py) and any future analytics tests.

Naming convention matches tests/_registry_helpers.py — the leading
underscore signals "test helper, not a pytest discovery file."
These are plain functions, not pytest fixtures (each test file
owns its own ``app`` fixture; helpers seed data inside it).
"""
from datetime import datetime, timezone, date, timedelta

from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupPick, WorldCupTeam, WorldCupMatch,
    WorldCupRankSnapshot,
)


def make_user(email='u@test', display_name='U'):
    u = User(
        username=email.split('@', 1)[0],
        email=email,
        password_hash='x',
        display_name=display_name,
    )
    db.session.add(u)
    db.session.flush()
    return u


def make_enrollment(user, total_score=0.0, picks_submitted=False,
                    usa_goals_guess=0, season=SEASON_YEAR, display_name=None):
    e = WorldCupEnrollment(
        user_id=user.id,
        season_year=season,
        total_score=total_score,
        picks_submitted=picks_submitted,
        usa_goals_guess=usa_goals_guess,
        display_name=display_name,
    )
    db.session.add(e)
    db.session.flush()
    return e


def make_team(fifa_code, name=None, tier=1, multiplier=1.0,
              group_letter='A', confederation='UEFA'):
    """Create a WorldCupTeam.

    Note: WorldCupTeam.flag_emoji is a derived @property (computed from
    fifa_code), not a column — so we don't accept a ``flag`` kwarg here.
    The model also requires ``name``, ``display_name``, and ``confederation``
    as NOT-NULL columns; we default them sensibly so the helper is
    safe to call with just a fifa_code.
    """
    label = name or fifa_code
    t = WorldCupTeam(
        fifa_code=fifa_code,
        name=label,
        display_name=label,
        tier=tier,
        multiplier=multiplier,
        group_letter=group_letter,
        confederation=confederation,
    )
    db.session.add(t)
    db.session.flush()
    return t


def make_pick(enrollment, team):
    p = WorldCupPick(
        enrollment_id=enrollment.id,
        team_id=team.id,
        tier=team.tier,
    )
    db.session.add(p)
    db.session.flush()
    return p


def make_match(match_number, home_team=None, away_team=None,
               stage='group', kickoff=None, is_completed=False,
               home_score=None, away_score=None, winner_team=None):
    m = WorldCupMatch(
        match_number=match_number,
        stage=stage,
        home_team_id=home_team.id if home_team else None,
        away_team_id=away_team.id if away_team else None,
        kickoff_utc=kickoff or datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc),
        is_completed=is_completed,
        home_score=home_score,
        away_score=away_score,
        winner_team_id=winner_team.id if winner_team else None,
    )
    db.session.add(m)
    db.session.flush()
    return m


def make_snapshot(enrollment, days_back=0, total_score=0.0, rank=1):
    s = WorldCupRankSnapshot(
        enrollment_id=enrollment.id,
        captured_date=date.today() - timedelta(days=days_back),
        total_score=total_score,
        rank=rank,
    )
    db.session.add(s)
    db.session.flush()
    return s


def seed_full_tournament(num_enrollments=5, num_picks_each=9,
                         seed_snapshots=False, snapshot_days=7):
    """Create enrollments + 48 dummy teams + picks + optional snapshots.

    Returns dict with:
        users         — list[User]
        enrollments   — list[WorldCupEnrollment] in score-DESC order
        teams         — list[WorldCupTeam] (48 teams across 5 tiers)
        picks_by_enr  — dict[enrollment_id, list[WorldCupPick]]

    The ``num_picks_each`` matches TIER_PICK_COUNTS = (1, 1, 2, 2, 3) -> 9.
    Each enrollment gets distinct teams to avoid roster overlap.
    """
    # 48 teams: 5 across tier 1, 5 tier 2, 11 tier 3, 11 tier 4, 16 tier 5
    teams = []
    for tier_num, count in [(1, 5), (2, 5), (3, 11), (4, 11), (5, 16)]:
        for i in range(count):
            t = make_team(
                fifa_code=f'T{tier_num}{i:02d}',
                name=f'Tier{tier_num}-{i}',
                tier=tier_num,
                multiplier={1: 1.0, 2: 1.5, 3: 2.0, 4: 2.5, 5: 3.0}[tier_num],
                group_letter='ABCDEFGHIJKL'[i % 12],
            )
            teams.append(t)

    users = []
    enrollments = []
    picks_by_enr = {}
    # score descending by index — enr 0 is leader
    scores = [100.0 - i * 5 for i in range(num_enrollments)]
    for i, score in enumerate(scores):
        u = make_user(email=f'u{i}@test', display_name=f'Player{i}')
        e = make_enrollment(
            u, total_score=score, picks_submitted=True, usa_goals_guess=i,
            display_name=f'Player{i}',
        )
        users.append(u)
        enrollments.append(e)
        # 9 picks: tier 1×1, tier 2×1, tier 3×2, tier 4×2, tier 5×3
        # Pull from disjoint slices so two enrollments never share teams
        # (avoids primary-key-style collisions in any future stricter rules).
        tier_offsets = [0, 5, 10, 21, 32]   # start indices into `teams` per tier
        tier_pick_counts = [1, 1, 2, 2, 3]
        picks = []
        for tier_idx, (offset, count) in enumerate(zip(tier_offsets, tier_pick_counts)):
            for k in range(count):
                team = teams[offset + (i * count + k) % {0: 5, 1: 5, 2: 11, 3: 11, 4: 16}[tier_idx]]
                picks.append(make_pick(e, team))
        picks_by_enr[e.id] = picks

    if seed_snapshots:
        for e in enrollments:
            for d in range(snapshot_days):
                make_snapshot(
                    e, days_back=d,
                    total_score=float(e.total_score) - d * 0.5,
                    rank=enrollments.index(e) + 1,
                )

    db.session.commit()
    return {
        'users': users,
        'enrollments': enrollments,
        'teams': teams,
        'picks_by_enr': picks_by_enr,
    }
