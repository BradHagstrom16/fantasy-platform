"""
Golf Pick 'Em — Constants
============================
League-specific constants for tournament filtering, purse estimates,
and season configuration.
"""
from datetime import UTC, datetime

# Tournaments to EXCLUDE from the league
# (opposite-field events, playoffs finale, special events)
EXCLUDED_TOURNAMENTS = {
    'Puerto Rico Open',
    'ONEflight Myrtle Beach Classic',
    'ISCO Championship',
    'Corales Puntacana Championship',
    'TOUR Championship',
    'Presidents Cup',
}

# Ignore any API events starting on or after this date
SEASON_CUTOFF_DATE = datetime(2026, 8, 24, tzinfo=UTC)

# 2026 PGA Tour purse amounts (in dollars)
# Names must match exactly what API returns or what's in database
PURSE_ESTIMATES = {
    'Sony Open in Hawaii': 9_100_000,
    'The American Express': 9_200_000,
    'Farmers Insurance Open': 9_600_000,
    'WM Phoenix Open': 9_600_000,
    'AT&T Pebble Beach Pro-Am': 20_000_000,
    'The Genesis Invitational': 20_000_000,
    'Cognizant Classic': 9_600_000,
    'Arnold Palmer Invitational presented by Mastercard': 20_000_000,
    'THE PLAYERS Championship': 25_000_000,
    'Valspar Championship': 9_100_000,
    "Texas Children's Houston Open": 9_900_000,
    'Valero Texas Open': 9_800_000,
    'Masters Tournament': 22_500_000,
    'RBC Heritage': 20_000_000,
    'Zurich Classic of New Orleans': 9_500_000,
    'Cadillac Championship': 20_000_000,
    'Truist Championship': 20_000_000,
    'PGA Championship': 19_000_000,
    'THE CJ CUP Byron Nelson': 10_300_000,
    'Charles Schwab Challenge': 9_900_000,
    'the Memorial Tournament presented by Workday': 20_000_000,
    'RBC Canadian Open': 9_800_000,
    'U.S. Open': 21_500_000,
    'Travelers Championship': 20_000_000,
    'John Deere Classic': 8_800_000,
    'Genesis Scottish Open': 9_000_000,
    'The Open Championship': 17_000_000,
    '3M Open': 8_800_000,
    'Rocket Classic': 10_000_000,
    'Wyndham Championship': 8_500_000,
    'FedEx St. Jude Championship': 20_000_000,
    'BMW Championship': 20_000_000,
}
DEFAULT_PURSE = 10_000_000  # Fallback for tournaments not in PURSE_ESTIMATES

# Minimum field size for "picks open" notification
MIN_FIELD_SIZE = 50

# ============================================================================
# Locked 2026 schedule — seeded by `flask golf seed-schedule`
# ============================================================================
# The league's 32-tournament season is fixed. Mirrors the standalone
# `import_tournaments.py` (start dates, team-event flag) and additionally
# carries the major flag so the x1.5 multiplier + penalty apply from seed.
# Format: (start_date "M/D/YYYY", name, is_team_event, is_major).
# Purses come from PURSE_ESTIMATES (real major purses live above).
TOURNAMENTS_2026 = [
    ("1/15/2026", "Sony Open in Hawaii", False, False),
    ("1/22/2026", "The American Express", False, False),
    ("1/29/2026", "Farmers Insurance Open", False, False),
    ("2/5/2026", "WM Phoenix Open", False, False),
    ("2/12/2026", "AT&T Pebble Beach Pro-Am", False, False),
    ("2/19/2026", "The Genesis Invitational", False, False),
    ("2/26/2026", "Cognizant Classic", False, False),
    ("3/5/2026", "Arnold Palmer Invitational presented by Mastercard", False, False),
    ("3/12/2026", "THE PLAYERS Championship", False, False),
    ("3/19/2026", "Valspar Championship", False, False),
    ("3/26/2026", "Texas Children's Houston Open", False, False),
    ("4/2/2026", "Valero Texas Open", False, False),
    ("4/9/2026", "Masters Tournament", False, True),
    ("4/16/2026", "RBC Heritage", False, False),
    ("4/23/2026", "Zurich Classic of New Orleans", True, False),
    ("4/30/2026", "Cadillac Championship", False, False),
    ("5/7/2026", "Truist Championship", False, False),
    ("5/14/2026", "PGA Championship", False, True),
    ("5/21/2026", "THE CJ CUP Byron Nelson", False, False),
    ("5/28/2026", "Charles Schwab Challenge", False, False),
    ("6/4/2026", "the Memorial Tournament presented by Workday", False, False),
    ("6/11/2026", "RBC Canadian Open", False, False),
    ("6/18/2026", "U.S. Open", False, True),
    ("6/25/2026", "Travelers Championship", False, False),
    ("7/2/2026", "John Deere Classic", False, False),
    ("7/9/2026", "Genesis Scottish Open", False, False),
    ("7/16/2026", "The Open Championship", False, True),
    ("7/23/2026", "3M Open", False, False),
    ("7/30/2026", "Rocket Classic", False, False),
    ("8/6/2026", "Wyndham Championship", False, False),
    ("8/13/2026", "FedEx St. Jude Championship", False, False),
    ("8/20/2026", "BMW Championship", False, False),
]
