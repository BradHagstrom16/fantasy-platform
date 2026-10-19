"""The Pay Sheet: the "Settle the Tab" nudge gate (ADR-056; ADR-075 D4).

WHETHER a member sees the how-to-pay leaf on a league's sheet (and the strip
in that league's picks-open letter), and WHAT it carries: the platform rails
from utils/payment.py with THAT league's entry fee and a memo naming the
league and the member, so a member of both sheets never pays one believing
it covered the other. ``has_paid`` stays admin-confirmed (The Roster and The
Tab); this module is read-only against it and never offers a self-mark.
"""
from utils.payment import payment_rails


def payment_nudge_for(line, is_platform_admin):
    """The nudge payload for one line (a ``GolfEnrollment`` with its league),
    or None when nothing should show: no line, a paid line, the platform
    admin (the Commish collects the tab) or that league's commissioner, or
    rails the platform has not configured (``payment_rails`` is None)."""
    if is_platform_admin or line is None or line.is_admin or line.has_paid:
        return None
    league = line.league
    memo = f'CCC {league.name} {line.season_year} - {line.user.get_display_name()}'
    rails = payment_rails(league.entry_fee, memo)
    if rails is None:
        return None
    return {**rails, 'league_name': league.name}
