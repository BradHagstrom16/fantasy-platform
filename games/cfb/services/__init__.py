"""
CFB Survivor Pool — Services
================================
Game logic, API integration, automation, and email notifications.
"""
from games.cfb.services.game_logic import (
    process_week_results,
    process_autopicks,
    check_and_process_autopicks,
    get_used_team_ids,
    get_game_for_team,
    calculate_cumulative_spread,
)
from games.cfb.services.score_fetcher import ScoreFetcher
