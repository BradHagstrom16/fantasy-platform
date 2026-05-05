"""Per-state data assembly for the WC blueprint home (Spec C Plan 4).

Mirrors core/main/home_context for the platform home (Spec B). The WC home
adds a 4th state — 'out' — for anonymous-or-unenrolled visitors. State is
resolved by games.worldcup.services.state.worldcup_hub_state(user) and
passed in.

Public entry point: build_worldcup_home_context(user, state) — dispatches
to one of four private builders. Each builder returns a flat dict
consumed by the matching _home_<state>.html partial.

Each builder's return-shape contract is documented at the function level.
"""
from typing import Any

from extensions import db
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupMatch,
)
from games.worldcup.services.state import WorldCupHubState, worldcup_state
from games.worldcup.services.voice import hub_copy


def _derive_tournament_phase() -> str:
    """Match-data derived tournament phase. Returns one of:
    'pre_tournament' | 'group_stage' | 'knockout' | 'completed'.

    Mirrors games.worldcup.routes._derive_tournament_phase exactly.
    Duplicated here (rather than imported) to avoid a circular import
    between the routes module and a service it depends on. CLAUDE.md
    "phase != stage" — distinct value space from stage_label.
    """
    completed_group = db.session.query(WorldCupMatch).filter_by(
        stage='group', is_completed=True
    ).count()
    completed_knockout = db.session.query(WorldCupMatch).filter(
        WorldCupMatch.stage != 'group',
        WorldCupMatch.is_completed == True  # noqa: E712
    ).count()
    final_completed = db.session.query(WorldCupMatch).filter_by(
        stage='final', is_completed=True
    ).count()

    if final_completed > 0:
        return 'completed'
    if completed_knockout > 0:
        return 'knockout'
    if completed_group > 0:
        return 'group_stage'
    return 'pre_tournament'


def build_worldcup_home_context(user: Any, state: WorldCupHubState) -> dict:
    """Dispatch to the per-state context builder.

    Raises ValueError on unknown state — fail loud per CLAUDE.md.
    """
    if state == 'out':
        return _context_out(user)
    if state == 'pre':
        return _context_pre(user)
    if state == 'live':
        return _context_live(user)
    if state == 'post':
        return _context_post(user)
    raise ValueError(f'unknown worldcup hub state: {state!r}')


# =====================================================================
# Per-state builders
# =====================================================================

def _context_out(user: Any) -> dict:
    """Marketing surface for anonymous + authenticated-unenrolled users.

    cta_state branches on (auth, tournament phase):
    - anon                       -> 'guest'
    - authenticated, pre kickoff -> 'unenrolled_pre'
    - authenticated, live        -> 'unenrolled_live'
    - authenticated, post        -> 'unenrolled_post'
    """
    is_authenticated = (
        user is not None
        and getattr(user, 'is_authenticated', False)
    )
    display_name = (
        user.get_display_name() if is_authenticated else None
    )

    if not is_authenticated:
        cta_state = 'guest'
    else:
        # 'out' state is set; phase still relevant for cta variant
        phase_state = worldcup_state()  # 'pre' | 'live' | 'post'
        cta_state = {
            'pre': 'unenrolled_pre',
            'live': 'unenrolled_live',
            'post': 'unenrolled_post',
        }[phase_state]

    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()

    top_3_preview = []
    if cta_state in ('unenrolled_live', 'unenrolled_post'):
        top_3_preview = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(
                WorldCupEnrollment.total_score.desc(),
                WorldCupEnrollment.id.asc(),
            )
            .limit(3)
            .all()
        )

    return {
        'state': 'out',
        'cta_state': cta_state,
        'copy': hub_copy('out', cta_state),
        'tournament_phase': _derive_tournament_phase(),
        'entry_fee': ENTRY_FEE,
        'total_enrolled': total_enrolled,
        'deadline_ct': TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ),
        'is_authenticated': is_authenticated,
        'display_name': display_name,
        'top_3_preview': top_3_preview,
    }


def _context_pre(user: Any) -> dict:
    """Stub — replaced in Task 7."""
    return {'_marker_pre': True}


def _context_live(user: Any) -> dict:
    """Stub — replaced in Task 8."""
    return {'_marker_live': True}


def _context_post(user: Any) -> dict:
    """Stub — replaced in Task 9."""
    return {'_marker_post': True}
