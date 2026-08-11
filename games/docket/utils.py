"""
The Docket — Utilities
======================
Canonical "now" reader per the platform time-seam convention (CLAUDE.md):
honors DOCKET_FAKE_NOW only when ENVIRONMENT is development/testing, mirrors
the CFB/WC seams. Also the one sanctioned aware→naive-UTC converter for the
D6 all-UTC column contract.
"""
import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def _fake_now_utc():
    """Return the DOCKET_FAKE_NOW override as an aware-UTC datetime, or None.

    Non-production test seam mirroring the CFB contract
    (games/cfb/utils._fake_now_utc): active only when ENVIRONMENT is
    development/testing; a naive ISO string is treated as UTC; malformed
    values are logged and ignored. Production never reads DOCKET_FAKE_NOW.
    """
    if os.environ.get('ENVIRONMENT') not in ('development', 'testing'):
        return None
    fake = os.environ.get('DOCKET_FAKE_NOW')
    if not fake:
        return None
    try:
        dt = datetime.fromisoformat(fake.replace('Z', '+00:00'))
    except ValueError:
        logger.warning(
            'DOCKET_FAKE_NOW is not a valid ISO 8601 datetime: %r — '
            'falling back to real time', fake,
        )
        return None
    if dt.tzinfo:
        return dt.astimezone(UTC)
    return dt.replace(tzinfo=UTC)


def now_utc():
    """Current time as an aware-UTC datetime. Honors the DOCKET_FAKE_NOW seam."""
    fake = _fake_now_utc()
    if fake is not None:
        return fake
    return datetime.now(UTC)


def to_naive_utc(dt):
    """Convert an aware datetime to the naive-UTC form docket columns store.

    The D6 contract's single write-side converter: every datetime that
    reaches a docket_* column passes through here. Naive input is assumed
    to already be UTC and returned unchanged.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)
