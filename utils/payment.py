"""Platform payment rails for the member-facing "Settle the Tab" nudge.

One builder for every game's how-to-pay surface (the room card and the
picks-open email): the Commish's Venmo + Zelle, read from platform config
(``PAYMENT_VENMO_HANDLE`` / ``PAYMENT_ZELLE_PHONE``) so a change of commish
is an env flip, never a code change. Each game owns its own gate
(``games/<game>/services/payment.py::payment_nudge_for``) and its fee; this
module only says WHERE the money goes and pre-fills the Venmo amount + memo.

``has_paid`` stays admin-confirmed from ``/<game>/admin/payments``; nothing
here offers a member a self-mark.

The archived World Cup carries its own frozen copy
(``games/worldcup/constants.py``) and does not read this module.
"""
from urllib.parse import quote_plus

from flask import current_app


def venmo_pay_url(handle: str, amount: int, memo: str) -> str:
    """Venmo's documented pay deep link: the app opens on the recipient with
    the amount and memo already filled, so the member only confirms. The
    memo names the pool and the member — it is what lets the Commish match
    a payment to a ``has_paid`` toggle without guessing.
    """
    return f'https://venmo.com/{handle}?txn=pay&amount={amount}&note={quote_plus(memo)}'


def payment_rails(entry_fee: int, memo: str) -> dict | None:
    """The nudge payload — ``{'entry_fee', 'venmo_url', 'zelle_phone'}`` —
    or ``None`` when either rail is blank in config (a deliberately blanked
    env hides every nudge platform-wide rather than rendering a half-card).
    """
    handle = (current_app.config.get('PAYMENT_VENMO_HANDLE') or '').strip()
    zelle = (current_app.config.get('PAYMENT_ZELLE_PHONE') or '').strip()
    if not handle or not zelle:
        return None
    return {
        'entry_fee': entry_fee,
        'venmo_url': venmo_pay_url(handle, entry_fee, memo),
        'zelle_phone': zelle,
    }
