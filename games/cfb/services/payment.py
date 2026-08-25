"""CFB Survivor — the "Settle the Tab" payment nudge gate.

WHETHER a member sees the how-to-pay card (and the matching paragraph in the
picks-open email), and WHAT it carries — the platform rails from
utils/payment.py with the Survivor entry fee and a memo that names the pool
and the member. ``has_paid`` stays admin-confirmed (toggled from
/cfb/admin/payments); this module is read-only against it and never offers
a member-facing self-mark.
"""
from flask import current_app

from utils.payment import payment_rails

GAME_LABEL = 'CFB Survivor'


def payment_nudge_for(enrollment, is_platform_admin):
    """Return the nudge payload dict, or None when the nudge should not show.

    Shows to an enrolled member who has not paid. Join IS the commitment in
    Survivor (no upfront picks step), so the card appears the moment a member
    joins — exactly when they are primed to pay — and only ``has_paid``
    retires it. Suppressed for the platform admin (the Commish collects the
    tab, he doesn't pay it).
    """
    if is_platform_admin:
        return None
    if enrollment is None or enrollment.has_paid:
        return None
    config = current_app.config
    memo = (f'CCC {GAME_LABEL} {config.get("CFB_SEASON_YEAR", 2026)} - '
            f'{enrollment.get_display_name()}')
    return payment_rails(config.get('CFB_ENTRY_FEE', 25), memo)
