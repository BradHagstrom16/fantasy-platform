"""
Golf Pick 'Em — Utility Functions
===================================
Shared helpers for formatting, parsing, and calculations.
"""
import logging
from typing import Optional, List

import pytz

logger = logging.getLogger(__name__)

# League timezone (Central Time)
GOLF_LEAGUE_TZ = pytz.timezone('America/Chicago')


def get_current_time():
    """Get current time in the golf league timezone."""
    from datetime import datetime
    return datetime.now(GOLF_LEAGUE_TZ)


def format_score_to_par(score) -> Optional[str]:
    """
    Format integer score to par for display.

    Args:
        score: Integer score relative to par (e.g., -22, 0, +3)

    Returns:
        Formatted string: "-22", "E", "+3", or None
    """
    if score is None:
        return None
    if score == 0:
        return "E"
    return f"+{score}" if score > 0 else str(score)


def parse_score_to_par(total_str) -> Optional[int]:
    """
    Parse the 'total' field from SlashGolf API into an integer score to par.

    API returns values like: "-22", "+3", "E", "-", "", None
    MongoDB number format also possible: {"$numberInt": "-22"}

    Returns:
        Integer score to par, or None if unparseable
    """
    if total_str is None:
        return None

    # Handle MongoDB-style number format
    if isinstance(total_str, dict):
        if '$numberInt' in total_str:
            try:
                return int(total_str['$numberInt'])
            except (ValueError, TypeError):
                return None
        if '$numberLong' in total_str:
            try:
                return int(total_str['$numberLong'])
            except (ValueError, TypeError):
                return None
        return None

    # Handle numeric types directly
    if isinstance(total_str, (int, float)):
        return int(total_str)

    # Handle string values
    total_str = str(total_str).strip()

    if not total_str or total_str in ('-', 'N/A', ''):
        return None

    if total_str.upper() == 'E':
        return 0

    try:
        return int(total_str)
    except ValueError:
        logger.warning("Unable to parse score to par: '%s'", total_str)
        return None


# PGA Tour Standard Payout Percentages (positions 1-65)
# Source: PGA Tour payout structure for full-field events
PAYOUT_PERCENTAGES = {
    1: 0.1800,   2: 0.1090,   3: 0.0690,   4: 0.0490,   5: 0.0410,
    6: 0.0363,   7: 0.0338,   8: 0.0313,   9: 0.0293,  10: 0.0273,
   11: 0.0253,  12: 0.0233,  13: 0.0213,  14: 0.0193,  15: 0.0183,
   16: 0.0173,  17: 0.0163,  18: 0.0153,  19: 0.0143,  20: 0.0133,
   21: 0.0123,  22: 0.0113,  23: 0.0105,  24: 0.0097,  25: 0.0089,
   26: 0.0081,  27: 0.0078,  28: 0.0075,  29: 0.0072,  30: 0.0069,
   31: 0.0066,  32: 0.0063,  33: 0.0060,  34: 0.0057,  35: 0.0055,
   36: 0.0052,  37: 0.0050,  38: 0.0048,  39: 0.0046,  40: 0.0044,
   41: 0.0042,  42: 0.0040,  43: 0.0038,  44: 0.0036,  45: 0.0034,
   46: 0.0032,  47: 0.0030,  48: 0.0028,  49: 0.0027,  50: 0.0026,
   51: 0.0025,  52: 0.0025,  53: 0.0024,  54: 0.0024,  55: 0.0024,
   56: 0.0023,  57: 0.0023,  58: 0.0023,  59: 0.0023,  60: 0.0023,
   61: 0.0022,  62: 0.0022,  63: 0.0022,  64: 0.0022,  65: 0.0022,
}


def calculate_projected_earnings(position_str: str, purse: int, all_positions: List[str]) -> int:
    """
    Calculate projected earnings for a player based on current position.

    Uses standard PGA Tour payout percentages. When players are tied,
    they split the combined prize money for all tied positions evenly.

    Args:
        position_str: Position from API (e.g., "1", "T2", "T10", "CUT")
        purse: Tournament purse in dollars
        all_positions: List of all position strings from leaderboard

    Returns:
        Projected earnings in dollars (integer)
    """
    if not position_str or position_str.upper() in ('CUT', 'WD', 'DQ', '-', ''):
        return 0

    if not purse or purse <= 0:
        return 0

    position_upper = position_str.upper()
    is_tied = position_upper.startswith('T')

    try:
        base_position = int(position_upper[1:] if is_tied else position_upper)
    except ValueError:
        return 0

    if base_position > 80:
        return 0

    tie_count = sum(1 for p in all_positions if p and p.upper() == position_upper)
    if tie_count == 0:
        tie_count = 1

    total_percentage = 0.0
    for i in range(tie_count):
        pos = base_position + i
        if pos <= 65:
            total_percentage += PAYOUT_PERCENTAGES.get(pos, 0)
        elif pos <= 80:
            beyond_65_pct = max(0, 0.00213 - (pos - 66) * 0.00002)
            total_percentage += beyond_65_pct

    player_percentage = total_percentage / tie_count if tie_count > 0 else 0

    return int(purse * player_percentage)
