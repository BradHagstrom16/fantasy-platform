"""The Docket — the "Settle the Tab" payment nudge gate.

WHETHER a member sees the how-to-pay card (and the matching paragraph in the
picks-open email), and WHAT it carries — the platform rails from
utils/payment.py with the Docket entry fee and a memo that names the pool
and the member. ``has_paid`` stays admin-confirmed (toggled from
/docket/admin/payments); this module is read-only against it and never
offers a member-facing self-mark.
"""
from flask import current_app

from games.docket.services.weeks import SEASON_YEAR
from utils.payment import payment_rails

GAME_LABEL = 'The Docket'


def payment_nudge_for(enrollment, is_platform_admin):
    """Return the nudge payload dict, or None when the nudge should not show.

    Shows to an enrolled member who has not paid, from the moment they join
    (the pre-season "awaiting the docket" sheet included); only ``has_paid``
    retires it. Suppressed for the platform admin.
    """
    if is_platform_admin:
        return None
    if enrollment is None or enrollment.has_paid:
        return None
    memo = f'CCC {GAME_LABEL} {SEASON_YEAR} - {enrollment.get_display_name()}'
    return payment_rails(current_app.config.get('DOCKET_ENTRY_FEE', 60), memo)
