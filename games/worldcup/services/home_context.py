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

from games.worldcup.services.state import WorldCupHubState


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
# Stub builders — each task in Section C replaces one of these
# with the full implementation + tests.
# =====================================================================

def _context_out(user: Any) -> dict:
    """Stub — replaced in Task 6."""
    return {'_marker_out': True}


def _context_pre(user: Any) -> dict:
    """Stub — replaced in Task 7."""
    return {'_marker_pre': True}


def _context_live(user: Any) -> dict:
    """Stub — replaced in Task 8."""
    return {'_marker_live': True}


def _context_post(user: Any) -> dict:
    """Stub — replaced in Task 9."""
    return {'_marker_post': True}
