"""Shared reminder de-dup gate.

Every game that mails deadline reminders records the closest window/tier it
has already sent on the week/tournament row (CFB `CfbWeek.last_reminder_type`,
Golf `GolfTournament.last_reminder_type`, Docket `DocketWeek.last_reminder_tier`)
and skips a window at or below that mark. The order-gate math lives here; the
RECORD policy stays per-game because it touches each game's model and session,
but the contract is identical everywhere:

  - never record when nobody needed the reminder — the window stays open, so a
    player who withdraws a pick later in the same window is still reachable;
  - never record when zero sends succeeded — a full mail outage must not
    swallow the window; the next firing retries;
  - record once ANY send succeeds — gating on all-recipient success would let
    one permanently bad address re-mail every good recipient each firing.

Semantics are deliberately fail-loud on the ACTIVE tier (the Docket doctrine):
an active tier missing from ``order`` raises KeyError, because a caller
holding a tier outside its own vocabulary is corrupt and should crash, not
silently skip. The STORED tier falls back to -1 — an unknown or legacy stored
value must never block a send.
"""


def tier_already_sent(last_tier, active_tier, order):
    """True if ``active_tier`` (or a later one) was already mailed.

    Args:
        last_tier: the tier recorded on the row, or None if nothing sent yet.
        active_tier: the tier whose window is active now. Must be a key of
            ``order`` (KeyError otherwise — see module docstring).
        order: mapping of tier name -> rank; higher = closer to the deadline.
    """
    return order[active_tier] <= order.get(last_tier, -1)
