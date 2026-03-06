"""
Golf Pick 'Em — Constants
============================
League-specific constants for tournament filtering, purse estimates,
and season configuration.
"""
from datetime import datetime

import pytz

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
SEASON_CUTOFF_DATE = datetime(2026, 8, 24, tzinfo=pytz.UTC)

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
    'Masters Tournament': None,
    'RBC Heritage': 20_000_000,
    'Zurich Classic of New Orleans': 9_500_000,
    'Cadillac Championship': 20_000_000,
    'Truist Championship': 20_000_000,
    'PGA Championship': None,
    'THE CJ CUP Byron Nelson': 10_300_000,
    'Charles Schwab Challenge': 9_900_000,
    'the Memorial Tournament presented by Workday': 20_000_000,
    'RBC Canadian Open': 9_800_000,
    'U.S. Open': None,
    'Travelers Championship': 20_000_000,
    'John Deere Classic': 8_800_000,
    'Genesis Scottish Open': 9_000_000,
    'The Open Championship': None,
    '3M Open': 8_800_000,
    'Rocket Classic': 10_000_000,
    'Wyndham Championship': 8_500_000,
    'FedEx St. Jude Championship': 20_000_000,
    'BMW Championship': 20_000_000,
}
DEFAULT_PURSE = 10_000_000

# Minimum field size for "picks open" notification
MIN_FIELD_SIZE = 50
