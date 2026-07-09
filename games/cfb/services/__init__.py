"""
CFB Survivor Pool — Services
================================
Game logic, API integration, automation, and email notifications.
"""
from games.cfb.services.game_logic import (
    calculate_cumulative_spread,
    check_and_process_autopicks,
    get_game_for_team,
    get_used_team_ids,
    process_autopicks,
    process_week_results,
)
from games.cfb.services.score_fetcher import ScoreFetcher
