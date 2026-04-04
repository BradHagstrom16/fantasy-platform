"""
World Cup Fantasy Pool — Match Schedule
==========================================
All 104 matches for the 2026 FIFA World Cup.
Matches 1-72: group stage (with teams assigned).
Matches 73-104: knockout stage (teams null, filled as bracket resolves).

All kickoff times are UTC (ISO 8601). During summer EDT, ET = UTC-4.
"""

MATCH_SCHEDULE = [
    # =========================================================================
    # GROUP STAGE — Matchday 1 (Matches 1–24)
    # =========================================================================
    {"match_number": 1,  "stage": "group", "group_letter": "A", "home_fifa_code": "MEX", "away_fifa_code": "RSA", "kickoff_utc": "2026-06-11T19:00:00", "venue": "Estadio Azteca",            "city": "Mexico City"},
    {"match_number": 2,  "stage": "group", "group_letter": "A", "home_fifa_code": "KOR", "away_fifa_code": "CZE", "kickoff_utc": "2026-06-12T02:00:00", "venue": "Estadio Akron",             "city": "Guadalajara"},
    {"match_number": 3,  "stage": "group", "group_letter": "B", "home_fifa_code": "CAN", "away_fifa_code": "BIH", "kickoff_utc": "2026-06-12T19:00:00", "venue": "BMO Field",                 "city": "Toronto"},
    {"match_number": 4,  "stage": "group", "group_letter": "D", "home_fifa_code": "USA", "away_fifa_code": "PAR", "kickoff_utc": "2026-06-13T01:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 5,  "stage": "group", "group_letter": "B", "home_fifa_code": "QAT", "away_fifa_code": "SUI", "kickoff_utc": "2026-06-13T19:00:00", "venue": "Levi's Stadium",            "city": "San Francisco"},
    {"match_number": 6,  "stage": "group", "group_letter": "C", "home_fifa_code": "BRA", "away_fifa_code": "MAR", "kickoff_utc": "2026-06-13T22:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 7,  "stage": "group", "group_letter": "C", "home_fifa_code": "HAI", "away_fifa_code": "SCO", "kickoff_utc": "2026-06-14T01:00:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 8,  "stage": "group", "group_letter": "D", "home_fifa_code": "AUS", "away_fifa_code": "TUR", "kickoff_utc": "2026-06-14T04:00:00", "venue": "BC Place",                  "city": "Vancouver"},
    {"match_number": 9,  "stage": "group", "group_letter": "E", "home_fifa_code": "GER", "away_fifa_code": "CUW", "kickoff_utc": "2026-06-14T17:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 10, "stage": "group", "group_letter": "F", "home_fifa_code": "NED", "away_fifa_code": "JPN", "kickoff_utc": "2026-06-14T20:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 11, "stage": "group", "group_letter": "E", "home_fifa_code": "CIV", "away_fifa_code": "ECU", "kickoff_utc": "2026-06-14T23:00:00", "venue": "Lincoln Financial Field",   "city": "Philadelphia"},
    {"match_number": 12, "stage": "group", "group_letter": "F", "home_fifa_code": "SWE", "away_fifa_code": "TUN", "kickoff_utc": "2026-06-15T02:00:00", "venue": "Estadio BBVA",              "city": "Monterrey"},
    {"match_number": 13, "stage": "group", "group_letter": "H", "home_fifa_code": "ESP", "away_fifa_code": "CPV", "kickoff_utc": "2026-06-15T16:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 14, "stage": "group", "group_letter": "G", "home_fifa_code": "BEL", "away_fifa_code": "EGY", "kickoff_utc": "2026-06-15T19:00:00", "venue": "Lumen Field",               "city": "Seattle"},
    {"match_number": 15, "stage": "group", "group_letter": "H", "home_fifa_code": "KSA", "away_fifa_code": "URU", "kickoff_utc": "2026-06-15T22:00:00", "venue": "Hard Rock Stadium",         "city": "Miami"},
    {"match_number": 16, "stage": "group", "group_letter": "G", "home_fifa_code": "IRN", "away_fifa_code": "NZL", "kickoff_utc": "2026-06-16T01:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 17, "stage": "group", "group_letter": "I", "home_fifa_code": "FRA", "away_fifa_code": "SEN", "kickoff_utc": "2026-06-16T19:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 18, "stage": "group", "group_letter": "I", "home_fifa_code": "IRQ", "away_fifa_code": "NOR", "kickoff_utc": "2026-06-16T22:00:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 19, "stage": "group", "group_letter": "J", "home_fifa_code": "ARG", "away_fifa_code": "ALG", "kickoff_utc": "2026-06-17T01:00:00", "venue": "Arrowhead Stadium",         "city": "Kansas City"},
    {"match_number": 20, "stage": "group", "group_letter": "J", "home_fifa_code": "AUT", "away_fifa_code": "JOR", "kickoff_utc": "2026-06-17T04:00:00", "venue": "Levi's Stadium",            "city": "San Francisco"},
    {"match_number": 21, "stage": "group", "group_letter": "K", "home_fifa_code": "POR", "away_fifa_code": "COD", "kickoff_utc": "2026-06-17T17:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 22, "stage": "group", "group_letter": "L", "home_fifa_code": "ENG", "away_fifa_code": "CRO", "kickoff_utc": "2026-06-17T20:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 23, "stage": "group", "group_letter": "L", "home_fifa_code": "GHA", "away_fifa_code": "PAN", "kickoff_utc": "2026-06-17T23:00:00", "venue": "BMO Field",                 "city": "Toronto"},
    {"match_number": 24, "stage": "group", "group_letter": "K", "home_fifa_code": "UZB", "away_fifa_code": "COL", "kickoff_utc": "2026-06-18T02:00:00", "venue": "Estadio Azteca",            "city": "Mexico City"},

    # =========================================================================
    # GROUP STAGE — Matchday 2 (Matches 25–48)
    # =========================================================================
    {"match_number": 25, "stage": "group", "group_letter": "A", "home_fifa_code": "CZE", "away_fifa_code": "RSA", "kickoff_utc": "2026-06-18T16:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 26, "stage": "group", "group_letter": "B", "home_fifa_code": "SUI", "away_fifa_code": "BIH", "kickoff_utc": "2026-06-18T19:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 27, "stage": "group", "group_letter": "B", "home_fifa_code": "CAN", "away_fifa_code": "QAT", "kickoff_utc": "2026-06-18T22:00:00", "venue": "BC Place",                  "city": "Vancouver"},
    {"match_number": 28, "stage": "group", "group_letter": "A", "home_fifa_code": "MEX", "away_fifa_code": "KOR", "kickoff_utc": "2026-06-19T01:00:00", "venue": "Estadio Akron",             "city": "Guadalajara"},
    {"match_number": 29, "stage": "group", "group_letter": "D", "home_fifa_code": "USA", "away_fifa_code": "AUS", "kickoff_utc": "2026-06-19T19:00:00", "venue": "Lumen Field",               "city": "Seattle"},
    {"match_number": 30, "stage": "group", "group_letter": "C", "home_fifa_code": "SCO", "away_fifa_code": "MAR", "kickoff_utc": "2026-06-19T22:00:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 31, "stage": "group", "group_letter": "C", "home_fifa_code": "BRA", "away_fifa_code": "HAI", "kickoff_utc": "2026-06-20T01:00:00", "venue": "Lincoln Financial Field",   "city": "Philadelphia"},
    {"match_number": 32, "stage": "group", "group_letter": "D", "home_fifa_code": "TUR", "away_fifa_code": "PAR", "kickoff_utc": "2026-06-20T04:00:00", "venue": "Levi's Stadium",            "city": "San Francisco"},
    {"match_number": 33, "stage": "group", "group_letter": "F", "home_fifa_code": "NED", "away_fifa_code": "SWE", "kickoff_utc": "2026-06-20T17:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 34, "stage": "group", "group_letter": "E", "home_fifa_code": "GER", "away_fifa_code": "CIV", "kickoff_utc": "2026-06-20T20:00:00", "venue": "BMO Field",                 "city": "Toronto"},
    {"match_number": 35, "stage": "group", "group_letter": "E", "home_fifa_code": "ECU", "away_fifa_code": "CUW", "kickoff_utc": "2026-06-21T00:00:00", "venue": "Arrowhead Stadium",         "city": "Kansas City"},
    {"match_number": 36, "stage": "group", "group_letter": "F", "home_fifa_code": "TUN", "away_fifa_code": "JPN", "kickoff_utc": "2026-06-21T04:00:00", "venue": "Estadio BBVA",              "city": "Monterrey"},
    {"match_number": 37, "stage": "group", "group_letter": "H", "home_fifa_code": "ESP", "away_fifa_code": "KSA", "kickoff_utc": "2026-06-21T16:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 38, "stage": "group", "group_letter": "G", "home_fifa_code": "BEL", "away_fifa_code": "IRN", "kickoff_utc": "2026-06-21T19:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 39, "stage": "group", "group_letter": "H", "home_fifa_code": "URU", "away_fifa_code": "CPV", "kickoff_utc": "2026-06-21T22:00:00", "venue": "Hard Rock Stadium",         "city": "Miami"},
    {"match_number": 40, "stage": "group", "group_letter": "G", "home_fifa_code": "NZL", "away_fifa_code": "EGY", "kickoff_utc": "2026-06-22T01:00:00", "venue": "BC Place",                  "city": "Vancouver"},
    {"match_number": 41, "stage": "group", "group_letter": "J", "home_fifa_code": "ARG", "away_fifa_code": "AUT", "kickoff_utc": "2026-06-22T17:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 42, "stage": "group", "group_letter": "I", "home_fifa_code": "FRA", "away_fifa_code": "IRQ", "kickoff_utc": "2026-06-22T21:00:00", "venue": "Lincoln Financial Field",   "city": "Philadelphia"},
    {"match_number": 43, "stage": "group", "group_letter": "I", "home_fifa_code": "NOR", "away_fifa_code": "SEN", "kickoff_utc": "2026-06-23T00:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 44, "stage": "group", "group_letter": "J", "home_fifa_code": "JOR", "away_fifa_code": "ALG", "kickoff_utc": "2026-06-23T03:00:00", "venue": "Levi's Stadium",            "city": "San Francisco"},
    {"match_number": 45, "stage": "group", "group_letter": "K", "home_fifa_code": "POR", "away_fifa_code": "UZB", "kickoff_utc": "2026-06-23T17:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 46, "stage": "group", "group_letter": "L", "home_fifa_code": "ENG", "away_fifa_code": "GHA", "kickoff_utc": "2026-06-23T20:00:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 47, "stage": "group", "group_letter": "L", "home_fifa_code": "PAN", "away_fifa_code": "CRO", "kickoff_utc": "2026-06-23T23:00:00", "venue": "BMO Field",                 "city": "Toronto"},
    {"match_number": 48, "stage": "group", "group_letter": "K", "home_fifa_code": "COL", "away_fifa_code": "COD", "kickoff_utc": "2026-06-24T02:00:00", "venue": "Estadio Akron",             "city": "Guadalajara"},

    # =========================================================================
    # GROUP STAGE — Matchday 3 (Matches 49–72, simultaneous within groups)
    # =========================================================================
    {"match_number": 49, "stage": "group", "group_letter": "B", "home_fifa_code": "SUI", "away_fifa_code": "CAN", "kickoff_utc": "2026-06-24T19:00:00", "venue": "BC Place",                  "city": "Vancouver"},
    {"match_number": 50, "stage": "group", "group_letter": "B", "home_fifa_code": "BIH", "away_fifa_code": "QAT", "kickoff_utc": "2026-06-24T19:00:00", "venue": "Lumen Field",               "city": "Seattle"},
    {"match_number": 51, "stage": "group", "group_letter": "C", "home_fifa_code": "SCO", "away_fifa_code": "BRA", "kickoff_utc": "2026-06-24T22:00:00", "venue": "Hard Rock Stadium",         "city": "Miami"},
    {"match_number": 52, "stage": "group", "group_letter": "C", "home_fifa_code": "MAR", "away_fifa_code": "HAI", "kickoff_utc": "2026-06-24T22:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 53, "stage": "group", "group_letter": "A", "home_fifa_code": "CZE", "away_fifa_code": "MEX", "kickoff_utc": "2026-06-25T01:00:00", "venue": "Estadio Azteca",            "city": "Mexico City"},
    {"match_number": 54, "stage": "group", "group_letter": "A", "home_fifa_code": "RSA", "away_fifa_code": "KOR", "kickoff_utc": "2026-06-25T01:00:00", "venue": "Estadio BBVA",              "city": "Monterrey"},
    {"match_number": 55, "stage": "group", "group_letter": "E", "home_fifa_code": "ECU", "away_fifa_code": "GER", "kickoff_utc": "2026-06-25T20:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 56, "stage": "group", "group_letter": "E", "home_fifa_code": "CUW", "away_fifa_code": "CIV", "kickoff_utc": "2026-06-25T20:00:00", "venue": "Lincoln Financial Field",   "city": "Philadelphia"},
    {"match_number": 57, "stage": "group", "group_letter": "F", "home_fifa_code": "JPN", "away_fifa_code": "SWE", "kickoff_utc": "2026-06-25T23:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 58, "stage": "group", "group_letter": "F", "home_fifa_code": "TUN", "away_fifa_code": "NED", "kickoff_utc": "2026-06-25T23:00:00", "venue": "Arrowhead Stadium",         "city": "Kansas City"},
    {"match_number": 59, "stage": "group", "group_letter": "D", "home_fifa_code": "TUR", "away_fifa_code": "USA", "kickoff_utc": "2026-06-26T02:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 60, "stage": "group", "group_letter": "D", "home_fifa_code": "PAR", "away_fifa_code": "AUS", "kickoff_utc": "2026-06-26T02:00:00", "venue": "Levi's Stadium",            "city": "San Francisco"},
    {"match_number": 61, "stage": "group", "group_letter": "I", "home_fifa_code": "NOR", "away_fifa_code": "FRA", "kickoff_utc": "2026-06-26T19:00:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 62, "stage": "group", "group_letter": "I", "home_fifa_code": "SEN", "away_fifa_code": "IRQ", "kickoff_utc": "2026-06-26T19:00:00", "venue": "BMO Field",                 "city": "Toronto"},
    {"match_number": 63, "stage": "group", "group_letter": "H", "home_fifa_code": "CPV", "away_fifa_code": "KSA", "kickoff_utc": "2026-06-27T00:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 64, "stage": "group", "group_letter": "H", "home_fifa_code": "URU", "away_fifa_code": "ESP", "kickoff_utc": "2026-06-27T00:00:00", "venue": "Estadio Akron",             "city": "Guadalajara"},
    {"match_number": 65, "stage": "group", "group_letter": "G", "home_fifa_code": "EGY", "away_fifa_code": "IRN", "kickoff_utc": "2026-06-27T03:00:00", "venue": "Lumen Field",               "city": "Seattle"},
    {"match_number": 66, "stage": "group", "group_letter": "G", "home_fifa_code": "NZL", "away_fifa_code": "BEL", "kickoff_utc": "2026-06-27T03:00:00", "venue": "BC Place",                  "city": "Vancouver"},
    {"match_number": 67, "stage": "group", "group_letter": "L", "home_fifa_code": "PAN", "away_fifa_code": "ENG", "kickoff_utc": "2026-06-27T21:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 68, "stage": "group", "group_letter": "L", "home_fifa_code": "CRO", "away_fifa_code": "GHA", "kickoff_utc": "2026-06-27T21:00:00", "venue": "Lincoln Financial Field",   "city": "Philadelphia"},
    {"match_number": 69, "stage": "group", "group_letter": "K", "home_fifa_code": "COL", "away_fifa_code": "POR", "kickoff_utc": "2026-06-27T23:30:00", "venue": "Hard Rock Stadium",         "city": "Miami"},
    {"match_number": 70, "stage": "group", "group_letter": "K", "home_fifa_code": "COD", "away_fifa_code": "UZB", "kickoff_utc": "2026-06-27T23:30:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 71, "stage": "group", "group_letter": "J", "home_fifa_code": "ALG", "away_fifa_code": "AUT", "kickoff_utc": "2026-06-28T02:00:00", "venue": "Arrowhead Stadium",         "city": "Kansas City"},
    {"match_number": 72, "stage": "group", "group_letter": "J", "home_fifa_code": "JOR", "away_fifa_code": "ARG", "kickoff_utc": "2026-06-28T02:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},

    # =========================================================================
    # KNOCKOUT STAGE — Round of 32 (Matches 73–88)
    # =========================================================================
    {"match_number": 73,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-06-28T19:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 74,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-06-29T20:30:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 75,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-06-30T01:00:00", "venue": "Estadio BBVA",              "city": "Monterrey"},
    {"match_number": 76,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-06-29T17:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 77,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-06-30T21:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 78,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-06-30T17:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 79,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-01T01:00:00", "venue": "Estadio Azteca",            "city": "Mexico City"},
    {"match_number": 80,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-01T16:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 81,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-02T00:00:00", "venue": "Levi's Stadium",            "city": "San Francisco"},
    {"match_number": 82,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-01T20:00:00", "venue": "Lumen Field",               "city": "Seattle"},
    {"match_number": 83,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-02T23:00:00", "venue": "BMO Field",                 "city": "Toronto"},
    {"match_number": 84,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-02T19:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 85,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-03T03:00:00", "venue": "BC Place",                  "city": "Vancouver"},
    {"match_number": 86,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-03T22:00:00", "venue": "Hard Rock Stadium",         "city": "Miami"},
    {"match_number": 87,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-04T01:30:00", "venue": "Arrowhead Stadium",         "city": "Kansas City"},
    {"match_number": 88,  "stage": "R32", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-03T18:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},

    # =========================================================================
    # KNOCKOUT STAGE — Round of 16 (Matches 89–96)
    # =========================================================================
    {"match_number": 89,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-04T21:00:00", "venue": "Lincoln Financial Field",   "city": "Philadelphia"},
    {"match_number": 90,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-04T17:00:00", "venue": "NRG Stadium",               "city": "Houston"},
    {"match_number": 91,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-05T20:00:00", "venue": "MetLife Stadium",           "city": "New York/New Jersey"},
    {"match_number": 92,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-06T00:00:00", "venue": "Estadio Azteca",            "city": "Mexico City"},
    {"match_number": 93,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-06T19:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 94,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-07T00:00:00", "venue": "Lumen Field",               "city": "Seattle"},
    {"match_number": 95,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-07T16:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},
    {"match_number": 96,  "stage": "R16", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-07T20:00:00", "venue": "BC Place",                  "city": "Vancouver"},

    # =========================================================================
    # KNOCKOUT STAGE — Quarterfinals (Matches 97–100)
    # =========================================================================
    {"match_number": 97,  "stage": "QF", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-09T20:00:00", "venue": "Gillette Stadium",          "city": "Boston"},
    {"match_number": 98,  "stage": "QF", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-10T19:00:00", "venue": "SoFi Stadium",              "city": "Los Angeles"},
    {"match_number": 99,  "stage": "QF", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-11T21:00:00", "venue": "Hard Rock Stadium",         "city": "Miami"},
    {"match_number": 100, "stage": "QF", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-12T01:00:00", "venue": "Arrowhead Stadium",         "city": "Kansas City"},

    # =========================================================================
    # KNOCKOUT STAGE — Semifinals (Matches 101–102)
    # =========================================================================
    {"match_number": 101, "stage": "SF", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-14T19:00:00", "venue": "AT&T Stadium",              "city": "Dallas"},
    {"match_number": 102, "stage": "SF", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-15T19:00:00", "venue": "Mercedes-Benz Stadium",     "city": "Atlanta"},

    # =========================================================================
    # KNOCKOUT STAGE — Third Place & Final (Matches 103–104)
    # =========================================================================
    {"match_number": 103, "stage": "third_place", "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-18T21:00:00", "venue": "Hard Rock Stadium",  "city": "Miami"},
    {"match_number": 104, "stage": "final",       "group_letter": None, "home_fifa_code": None, "away_fifa_code": None, "kickoff_utc": "2026-07-19T19:00:00", "venue": "MetLife Stadium",    "city": "New York/New Jersey"},
]
