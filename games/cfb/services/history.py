"""2025 season archive loader.

The committed snapshot (games/cfb/data/season_2025.json, written once by
scripts/export_2025_history.py) is the archive page's only data source.
No fallback path on purpose: a missing or corrupt snapshot raises at first
request; the integrity locks in tests/test_cfb_history.py make that
unshippable rather than a runtime concern. Returned dicts are cached per
process -- treat them as read-only.
"""
import json
from functools import lru_cache
from pathlib import Path

_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "season_2025.json"


@lru_cache(maxsize=1)
def get_season_2025():
    """Return the 2025 season archive (season, champion, standings, attrition)."""
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
