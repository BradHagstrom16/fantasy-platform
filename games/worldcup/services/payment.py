"""Member-facing payment nudge gate ("Settle the Tab").

Single source of truth for WHETHER an enrolled member sees the payment nudge
and WHAT rails it carries. The `has_paid` flag stays admin-confirmed (toggled
from /worldcup/admin/payments after the money lands); this module is read-only
against it and never offers a member-facing self-mark affordance.
"""
from games.worldcup.constants import ENTRY_FEE, VENMO_URL, ZELLE_PHONE


def payment_nudge_for(enrollment, tournament_phase, is_platform_admin):
    """Return the nudge payload dict, or None when the nudge should not show.

    Shows only to an enrolled member who has submitted picks but not paid,
    while the tournament is still pre-kickoff or live. Hidden once
    ``tournament_phase == 'completed'`` so the post-tournament champion moment
    stays clean, and suppressed for platform admins (the Commish collects the
    tab, he doesn't pay it).

    Args:
        enrollment: the viewer's WorldCupEnrollment for the active season, or None.
        tournament_phase: one of 'pre_tournament' | 'group_stage' | 'knockout'
            | 'completed' (from routes._derive_tournament_phase).
        is_platform_admin: current_user.is_admin.

    Returns:
        {'entry_fee', 'venmo_url', 'zelle_phone'} when the nudge should render,
        else None.
    """
    if is_platform_admin:
        return None
    if enrollment is None or not enrollment.picks_submitted or enrollment.has_paid:
        return None
    if tournament_phase == 'completed':
        return None
    return {
        'entry_fee': ENTRY_FEE,
        'venmo_url': VENMO_URL,
        'zelle_phone': ZELLE_PHONE,
    }
