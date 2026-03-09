"""
Golf Pick 'Em — API Sync Module
=================================
Sync tournament data from SlashGolf API.

Data Flow:
1. sync_tournament_field() - Tue/Wed: Get players + tee times (4 syncs: Tue AM/PM, Wed AM/PM)
2. sync_live_leaderboard() - Thu-Sun 8 PM: Update positions + projected earnings
3. sync_tournament_results() - Monday after tournament: Get actual earnings from API
4. process_tournament_picks() - After results synced: Calculate points

API Endpoints Used:
- /leaderboard - Field, tee times, player status, rounds completed
- /earnings - Prize money per player (after tournament complete)
- /schedule - Season schedule (one-time import)
- /tournament - Tournament details + full field

Email Notifications:
- "Picks Are Open" - Sent when field syncs with >=50 players
- Admin Alert - Sent on Wednesday evening if field still has <50 players
"""

import logging
import os
import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

import pytz
import requests

from extensions import db
from games.golf.models import (
    GolfTournament,
    GolfPlayer,
    GolfTournamentField,
    GolfTournamentResult,
    GolfPick,
    GolfEnrollment,
)
from games.golf.utils import GOLF_LEAGUE_TZ, parse_score_to_par, calculate_projected_earnings
from games.golf.constants import EXCLUDED_TOURNAMENTS, SEASON_CUTOFF_DATE, MIN_FIELD_SIZE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Dedicated API call logger for auditing RapidAPI usage
API_CALL_LOGGER = logging.getLogger("api_calls")
API_CALL_LOGGER.setLevel(logging.INFO)
if not API_CALL_LOGGER.handlers:
    from logging.handlers import RotatingFileHandler
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(log_dir, "api_calls.log"),
        maxBytes=500_000,  # ~500KB per file
        backupCount=3
    )
    handler.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
    API_CALL_LOGGER.addHandler(handler)


class SlashGolfAPI:
    """Client for SlashGolf API."""

    # RapidAPI configuration
    BASE_URL = "https://live-golf-data.p.rapidapi.com"

    def __init__(self, api_key: str, api_host: str = "live-golf-data.p.rapidapi.com", sync_mode: str = "standard"):
        """
        Initialize API client.

        Args:
            api_key: Your RapidAPI key
            api_host: RapidAPI host (default for SlashGolf)
            sync_mode: 'standard' or 'free' tier mode
        """
        self.api_key = api_key
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": api_host
        }
        self.org_id = "1"  # PGA Tour
        self.sync_mode = (sync_mode or "standard").lower()
        self._call_counter = 0

    def _log_api_call(self, endpoint: str, params: Dict, status: int, duration: float, attempt: int) -> None:
        """Record API call details for auditing."""
        self._call_counter += 1
        API_CALL_LOGGER.info(
            "count=%s\tmode=%s\tendpoint=%s\tstatus=%s\tattempt=%s\tduration=%.2fs\tparams=%s",
            self._call_counter,
            self.sync_mode,
            endpoint,
            status,
            attempt,
            duration,
            params,
        )

    def _make_request(self, endpoint: str, params: Dict = None, retries: int = 5) -> Optional[Dict]:
        """Make API request with exponential backoff, jitter, and structured logging."""
        url = f"{self.BASE_URL}/{endpoint}"

        if params is None:
            params = {}
        params["orgId"] = self.org_id

        backoff = 1.5
        for attempt in range(1, retries + 1):
            start_time = time.time()
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=15)

                duration = time.time() - start_time
                self._log_api_call(endpoint, params, response.status_code, duration, attempt)

                if response.status_code == 200:
                    return response.json()

                is_retryable = response.status_code in (429, 500, 502, 503, 504)
                logger.warning(
                    "API error %s on %s params=%s (attempt %s/%s, retryable=%s)",
                    response.status_code,
                    endpoint,
                    params,
                    attempt,
                    retries,
                    is_retryable,
                )

                if not is_retryable:
                    break

            except requests.RequestException as exc:
                logger.exception(
                    "Request failed for %s params=%s (attempt %s/%s)",
                    endpoint,
                    params,
                    attempt,
                    retries,
                )
                duration = time.time() - start_time
                self._log_api_call(endpoint, params, 0, duration, attempt)

            if attempt < retries:
                sleep_for = min(60, backoff * (2 ** (attempt - 1)))
                sleep_for = sleep_for * (1 + random.uniform(-0.25, 0.25))
                time.sleep(max(0.5, sleep_for))

        logger.error("Exhausted retries for endpoint %s params=%s", endpoint, params)
        return None

    def get_schedule(self, year: str) -> Optional[Dict]:
        """Get full season schedule."""
        return self._make_request("schedule", {"year": year})

    def get_tournament(self, tourn_id: str, year: str) -> Optional[Dict]:
        """Get tournament details including field."""
        return self._make_request("tournament", {"tournId": tourn_id, "year": year})

    def get_leaderboard(self, tourn_id: str, year: str) -> Optional[Dict]:
        """Get leaderboard with tee times, status, rounds."""
        return self._make_request("leaderboard", {"tournId": tourn_id, "year": year})

    def get_earnings(self, tourn_id: str, year: str) -> Optional[Dict]:
        """Get earnings/prize money for completed tournament."""
        return self._make_request("earnings", {"tournId": tourn_id, "year": year})


class TournamentSync:
    """Sync tournament data from API to database."""

    def __init__(self, api: SlashGolfAPI, sync_mode: str = "standard", fallback_deadline_hour: int = 7):
        self.api = api
        self.sync_mode = (sync_mode or "standard").lower()
        self.fallback_deadline_hour = fallback_deadline_hour

    @property
    def is_free_mode(self) -> bool:
        return self.sync_mode == "free"

    @staticmethod
    def _get_event_timezone(leaderboard_data: Dict) -> pytz.timezone:
        tz_name = leaderboard_data.get("timeZone") or leaderboard_data.get("timezone") or leaderboard_data.get("tz")
        if tz_name:
            try:
                return pytz.timezone(tz_name)
            except Exception:
                logger.warning("Unknown timezone '%s', falling back to league TZ", tz_name)
        return GOLF_LEAGUE_TZ

    @staticmethod
    def _parse_tee_time_timestamp(tee_time_ts: Optional[Dict]) -> Optional[datetime]:
        """
        Parse teeTimeTimestamp from API (preferred method - timezone-safe).

        The API provides timestamps in MongoDB format: {"$date": {"$numberLong": "1768497660000"}}
        These are Unix timestamps in milliseconds, representing the exact moment in time.
        """
        if not tee_time_ts:
            return None

        try:
            # Handle MongoDB-style timestamp format
            if isinstance(tee_time_ts, dict):
                if '$date' in tee_time_ts:
                    date_val = tee_time_ts['$date']
                    if isinstance(date_val, dict) and '$numberLong' in date_val:
                        ts_ms = int(date_val['$numberLong'])
                    else:
                        ts_ms = int(date_val)
                elif '$numberLong' in tee_time_ts:
                    ts_ms = int(tee_time_ts['$numberLong'])
                else:
                    return None
            else:
                ts_ms = int(tee_time_ts)

            # Convert milliseconds to seconds and create timezone-aware datetime
            ts_sec = ts_ms / 1000
            return datetime.fromtimestamp(ts_sec, tz=pytz.UTC)
        except Exception as e:
            logger.warning("Unable to parse tee time timestamp '%s': %s", tee_time_ts, e)
            return None

    @staticmethod
    def _parse_tee_time(tee_time_str: Optional[str], tournament_date: datetime, event_tz: pytz.timezone) -> Optional[datetime]:
        """
        Parse tee time from string (fallback method - requires timezone context).

        WARNING: This method is less reliable because tee time strings like "7:21am"
        don't include timezone info. Use _parse_tee_time_timestamp when available.
        """
        if not tee_time_str or tee_time_str == "N/A":
            return None

        try:
            if "T" in tee_time_str:
                dt = datetime.fromisoformat(tee_time_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = event_tz.localize(dt)
                return dt

            tee_time_parsed = datetime.strptime(tee_time_str, "%I:%M%p")
            tee_datetime = datetime.combine(tournament_date.date(), tee_time_parsed.time())
            return event_tz.localize(tee_datetime)
        except Exception:
            logger.warning("Unable to parse tee time '%s'", tee_time_str)
            return None

    def _update_pick_deadline_from_leaderboard(self, tournament: GolfTournament, leaderboard_data: Dict) -> Optional[datetime]:
        event_tz = self._get_event_timezone(leaderboard_data)
        earliest = None

        for player_data in leaderboard_data.get("leaderboardRows", []):
            # Prefer timestamp (timezone-safe) over string (ambiguous)
            tee_time = self._parse_tee_time_timestamp(player_data.get("teeTimeTimestamp"))
            if not tee_time:
                # Fallback to string parsing if timestamp not available
                tee_time = (
                    self._parse_tee_time(player_data.get("teeTime"), tournament.start_date, event_tz)
                    or self._parse_tee_time(player_data.get("teeTimeLocal"), tournament.start_date, event_tz)
                )
            if tee_time and (earliest is None or tee_time < earliest):
                earliest = tee_time

        if earliest:
            tournament.pick_deadline = earliest
        return earliest

    def _derive_status(self, tournament: GolfTournament, leaderboard_data: Optional[Dict] = None) -> str:
        status_hint = (leaderboard_data or {}).get("status", "").lower()
        now = datetime.now(GOLF_LEAGUE_TZ)
        start = tournament.start_date if tournament.start_date.tzinfo else GOLF_LEAGUE_TZ.localize(tournament.start_date)
        end = tournament.end_date if tournament.end_date.tzinfo else GOLF_LEAGUE_TZ.localize(tournament.end_date)

        if "complete" in status_hint or "official" in status_hint:
            tournament.status = "complete"
        elif now >= end:
            # Don't auto-set to 'complete' — only API confirmation should do that.
            # Keep as 'active' until sync_tournament_results() verifies completion.
            if tournament.status != 'active':
                tournament.status = 'active'
        elif "progress" in status_hint or "live" in status_hint:
            tournament.status = "active"
        elif now >= start:
            tournament.status = "active"
        else:
            tournament.status = "upcoming"
        return tournament.status

    def _apply_fixed_deadline(self, tournament: GolfTournament) -> datetime:
        """Set a deterministic pick deadline when tee times aren't available."""
        start_localized = tournament.start_date
        if start_localized.tzinfo is None:
            start_localized = GOLF_LEAGUE_TZ.localize(start_localized)

        fixed_deadline = start_localized.replace(
            hour=self.fallback_deadline_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        tournament.pick_deadline = fixed_deadline
        return fixed_deadline

    @staticmethod
    def _parse_api_number(value):
        """Parse MongoDB-style number format from API."""
        if isinstance(value, dict):
            if '$numberInt' in value:
                return int(value['$numberInt'])
            if '$numberLong' in value:
                return int(value['$numberLong'])
            if '$numberDouble' in value:
                return int(float(value['$numberDouble']))
        return int(value) if value else 0

    def sync_schedule(self, year: int, tournament_names: List[str] = None) -> int:
        """
        Update season schedule from API.

        Only updates tournaments that already exist in the database.
        Will NOT create new tournaments — our 32-tournament schedule is locked.
        Skips events in EXCLUDED_TOURNAMENTS and events starting on or after
        SEASON_CUTOFF_DATE.

        Args:
            year: Season year (e.g., 2026)
            tournament_names: Optional list of tournament names to include.
                            If None, processes all non-excluded events.

        Returns:
            Number of tournaments updated
        """
        data = self.api.get_schedule(str(year))
        if not data or "schedule" not in data:
            print("Failed to fetch schedule")
            return 0

        updated = 0

        for event in data["schedule"]:
            name = event.get("name", "")

            # Skip if we have a filter and this tournament isn't in it
            if tournament_names and name not in tournament_names:
                continue

            # Skip excluded tournaments (opposite-field, playoffs finale, special events)
            if name in EXCLUDED_TOURNAMENTS:
                continue

            # Skip events that start on or after the season cutoff date
            try:
                start_ts = int(event["date"]["start"]["$date"]["$numberLong"]) / 1000
                start_date = datetime.fromtimestamp(start_ts, tz=pytz.UTC)
                if start_date >= SEASON_CUTOFF_DATE:
                    continue
            except (KeyError, ValueError, TypeError):
                continue

            # Only update existing tournaments — never create new ones
            existing = GolfTournament.query.filter_by(
                api_tourn_id=event["tournId"],
                season_year=year
            ).first()

            if not existing:
                # Tournament not in our league — skip it
                continue

            # Update existing tournament data (name intentionally NOT overwritten —
            # league names are locked and cleaned of sponsor suffixes)
            api_purse = self._parse_api_number(event.get("purse", 0))
            if api_purse > 0:
                existing.purse = api_purse
            existing.is_team_event = event.get("format") == "team"
            updated += 1

        db.session.commit()
        print(f"Updated {updated} tournaments for {year}")
        return updated

    def sync_tournament_field(self, tournament: GolfTournament, is_wednesday_evening: bool = False) -> Tuple[int, Optional[datetime]]:
        """
        Sync tournament field and get first tee time.
        Call this Tuesday/Wednesday before the tournament.

        Args:
            tournament: GolfTournament object to sync
            is_wednesday_evening: True if this is the Wednesday evening pass (for admin alerts)

        Returns:
            Tuple of (new_players_synced, first_tee_time)
        """
        # Get leaderboard data (has field + tee times)
        data = self.api.get_leaderboard(tournament.api_tourn_id, str(tournament.season_year))

        if not data or "leaderboardRows" not in data:
            logger.error("Failed to fetch leaderboard for %s", tournament.name)
            return 0, None

        new_players_synced = 0
        existing_players = 0
        first_tee_time = None
        event_tz = self._get_event_timezone(data)

        try:
            for player_data in data["leaderboardRows"]:
                if player_data.get("isAmateur", False):
                    continue

                player = GolfPlayer.query.filter_by(
                    api_player_id=player_data["playerId"]
                ).first()

                if not player:
                    player = GolfPlayer(
                        api_player_id=player_data["playerId"],
                        first_name=player_data.get("firstName", ""),
                        last_name=player_data.get("lastName", ""),
                        is_amateur=player_data.get("isAmateur", False)
                    )
                    db.session.add(player)
                    db.session.flush()

                field_entry = GolfTournamentField.query.filter_by(
                    tournament_id=tournament.id,
                    player_id=player.id
                ).first()

                if not field_entry:
                    field_entry = GolfTournamentField(
                        tournament_id=tournament.id,
                        player_id=player.id
                    )
                    db.session.add(field_entry)
                    new_players_synced += 1
                else:
                    existing_players += 1

                # Prefer timestamp (timezone-safe) over string (ambiguous)
                tee_time = self._parse_tee_time_timestamp(player_data.get("teeTimeTimestamp"))
                if not tee_time:
                    # Fallback to string parsing if timestamp not available
                    tee_time = (
                        self._parse_tee_time(player_data.get("teeTime"), tournament.start_date, event_tz)
                        or self._parse_tee_time(player_data.get("teeTimeLocal"), tournament.start_date, event_tz)
                    )
                if tee_time and (first_tee_time is None or tee_time < first_tee_time):
                    first_tee_time = tee_time

            if first_tee_time:
                # Convert to Central Time before storing (SQLite loses timezone info)
                if first_tee_time.tzinfo:
                    first_tee_time_ct = first_tee_time.astimezone(GOLF_LEAGUE_TZ)
                    tournament.pick_deadline = first_tee_time_ct.replace(tzinfo=None)
                else:
                    tournament.pick_deadline = first_tee_time
                logger.info("Set deadline for %s: %s CT", tournament.name, tournament.pick_deadline)

            self._derive_status(tournament, data)

            if not first_tee_time and self.is_free_mode:
                fallback_deadline = self._apply_fixed_deadline(tournament)
                logger.info(
                    "Free tier: using fixed pick deadline %s for %s (tee times unavailable)",
                    fallback_deadline,
                    tournament.name,
                )
            elif not tournament.pick_deadline:
                fallback_deadline = self._apply_fixed_deadline(tournament)
                logger.info(
                    "Applied fallback pick deadline %s for %s",
                    fallback_deadline,
                    tournament.name,
                )
            db.session.commit()

            # Get total field count after commit
            total_field_count = GolfTournamentField.query.filter_by(tournament_id=tournament.id).count()

            # Improved logging message
            if new_players_synced > 0:
                logger.info("Synced %s new players for %s (total field: %s)",
                           new_players_synced, tournament.name, total_field_count)
            else:
                logger.info("Field already synced for %s (total: %s players, no new additions)",
                           tournament.name, total_field_count)

        except Exception:
            db.session.rollback()
            logger.exception("Failed syncing field for %s", tournament.name)
            return 0, None

        # =================================================================
        # EMAIL NOTIFICATIONS (after successful sync)
        # Store tournament_id before any session issues
        # =================================================================
        tournament_id = tournament.id
        field_count = GolfTournamentField.query.filter_by(tournament_id=tournament_id).count()

        # Check if field is sufficient and we haven't sent the "picks open" email yet
        if field_count >= MIN_FIELD_SIZE and not tournament.picks_open_notified:
            try:
                from games.golf.services.reminders import send_picks_open_email, send_admin_field_alert
                # Pass tournament_id instead of tournament object to avoid session issues
                emails_sent = send_picks_open_email(tournament_id)
                if emails_sent > 0:
                    # Re-query tournament to update flag
                    tournament = db.session.get(GolfTournament, tournament_id)
                    tournament.picks_open_notified = True
                    db.session.commit()
                    logger.info("Sent 'picks open' email to %s users for %s", emails_sent, tournament.name)
            except Exception as e:
                logger.error("Failed to send 'picks open' email for tournament %s: %s", tournament_id, e)

        # Check if it's Wednesday evening and field is still insufficient - send admin alert
        if is_wednesday_evening and field_count < MIN_FIELD_SIZE:
            # Re-query tournament to check flag
            tournament = db.session.get(GolfTournament, tournament_id)
            if not tournament.field_alert_sent:
                try:
                    from games.golf.services.reminders import send_admin_field_alert
                    # Pass tournament_id instead of tournament object
                    if send_admin_field_alert(tournament_id, field_count):
                        tournament.field_alert_sent = True
                        db.session.commit()
                        logger.warning("Sent admin alert for tournament %s - only %s players in field",
                                      tournament_id, field_count)
                except Exception as e:
                    logger.error("Failed to send admin alert for tournament %s: %s", tournament_id, e)

        return new_players_synced, first_tee_time

    def sync_tournament_results(self, tournament: GolfTournament) -> int:
        """
        Sync tournament results and ACTUAL earnings after completion.
        Call this Monday after tournament ends.

        Only proceeds if the API reports tournament status as "Complete" or "Official".
        Sets tournament.results_finalized = True on success.

        Args:
            tournament: GolfTournament object to sync

        Returns:
            Number of results synced (0 if not ready or failed)
        """
        # First check if tournament is actually complete via API
        leaderboard_data = self.api.get_leaderboard(tournament.api_tourn_id, str(tournament.season_year))

        if not leaderboard_data:
            logger.error("Failed to fetch leaderboard for %s", tournament.name)
            return 0

        api_status = leaderboard_data.get("status", "").lower()
        if api_status not in ("complete", "official"):
            logger.info(
                "Tournament %s not ready for finalization (API status: %s)",
                tournament.name,
                leaderboard_data.get("status", "unknown")
            )
            return 0

        # Now fetch actual earnings
        earnings_data = self.api.get_earnings(tournament.api_tourn_id, str(tournament.season_year))

        if not earnings_data or "leaderboard" not in earnings_data:
            logger.error("Failed to fetch earnings for %s", tournament.name)
            return 0

        # Build lookup from leaderboard for status/rounds/score info
        leaderboard_lookup = {}
        if "leaderboardRows" in leaderboard_data:
            for p in leaderboard_data["leaderboardRows"]:
                leaderboard_lookup[p["playerId"]] = p

        results_synced = 0

        try:
            for player_data in earnings_data["leaderboard"]:
                player_id = player_data["playerId"]

                player = GolfPlayer.query.filter_by(api_player_id=player_id).first()
                if not player:
                    continue

                lb_info = leaderboard_lookup.get(player_id, {})
                rounds_completed = len(lb_info.get("rounds", []))
                status = lb_info.get("status", "complete")

                result = GolfTournamentResult.query.filter_by(
                    tournament_id=tournament.id,
                    player_id=player.id
                ).first()

                if not result:
                    result = GolfTournamentResult(
                        tournament_id=tournament.id,
                        player_id=player.id
                    )
                    db.session.add(result)

                # Parse actual earnings from API
                result.earnings = self._parse_api_number(player_data.get("earnings", 0))

                result.status = status
                result.rounds_completed = rounds_completed
                result.final_position = lb_info.get("position", "")

                # Parse score to par from leaderboard "total" field
                result.score_to_par = parse_score_to_par(lb_info.get("total"))

                results_synced += 1

            tournament.status = "complete"
            tournament.results_finalized = True
            db.session.commit()

            logger.info("Finalized %s results for %s (actual earnings from API)", results_synced, tournament.name)
        except Exception:
            db.session.rollback()
            logger.exception("Failed syncing results for %s", tournament.name)
            return 0
        return results_synced

    def process_tournament_picks(self, tournament: GolfTournament) -> int:
        """
        Process all picks for a completed tournament.
        Calculates points and updates enrollment totals.

        Args:
            tournament: Completed tournament to process

        Returns:
            Number of picks processed
        """
        if tournament.status != "complete":
            logger.warning("Tournament %s is not complete", tournament.name)
            return 0

        picks = GolfPick.query.filter_by(tournament_id=tournament.id).all()
        processed = 0
        skipped = 0

        for pick in picks:
            try:
                # Clean up old resolution state (handles re-processing scenarios)
                pick.clear_resolution(tournament.season_year)
                resolved = pick.resolve_pick()
                if not resolved:
                    skipped += 1
                    continue

                enrollment = GolfEnrollment.query.filter_by(
                    user_id=pick.user_id,
                    season_year=tournament.season_year
                ).first()
                if enrollment:
                    enrollment.calculate_total_points()

                processed += 1
            except Exception as exc:  # noqa: BLE001 - continue to next pick
                logger.warning(
                    "Skipped pick %s for %s: %s",
                    pick.id,
                    tournament.id,
                    exc,
                )

        db.session.commit()

        logger.info(
            "Processed %s picks for %s (skipped %s)",
            processed,
            tournament.name,
            skipped,
        )

        return processed

    def check_withdrawals(self, tournament: GolfTournament, force: bool = False) -> List[Dict]:
        """
        Check for withdrawals during a tournament.
        Useful for monitoring mid-tournament.

        Args:
            tournament: Active tournament to check
            force: If True, bypass free tier restriction (used by live-with-wd)

        Returns:
            List of withdrawal info dicts
        """
        if self.is_free_mode and not force:
            logger.info("Free tier: skipping withdrawal check for %s", tournament.name)
            return []

        data = self.api.get_leaderboard(tournament.api_tourn_id, str(tournament.season_year))

        if not data or "leaderboardRows" not in data:
            return []

        withdrawals = []

        try:
            for player_data in data["leaderboardRows"]:
                if player_data.get("status") != "wd":
                    continue

                rounds = player_data.get("rounds", [])
                rounds_completed = len(rounds)

                player = GolfPlayer.query.filter_by(api_player_id=player_data["playerId"]).first()
                if not player:
                    continue

                result = GolfTournamentResult.query.filter_by(
                    tournament_id=tournament.id,
                    player_id=player.id
                ).first()

                if not result:
                    result = GolfTournamentResult(
                        tournament_id=tournament.id,
                        player_id=player.id
                    )
                    db.session.add(result)

                result.status = "wd"
                result.rounds_completed = rounds_completed
                result.final_position = player_data.get("position", "")
                result.score_to_par = parse_score_to_par(player_data.get("total"))

                withdrawals.append({
                    "player_id": player_data["playerId"],
                    "name": f"{player_data.get('firstName', '')} {player_data.get('lastName', '')}",
                    "rounds_completed": rounds_completed,
                    "wd_before_r2": rounds_completed < 2
                })

            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed checking withdrawals for %s", tournament.name)

        return withdrawals

    def sync_live_leaderboard(self, tournament: GolfTournament) -> int:
        """
        Update live leaderboard data and PROJECTED earnings for an active tournament.
        Call this Thu-Sun at 8 PM CT after each round.

        Calculates projected earnings based on current position and tournament purse
        using standard PGA Tour payout percentages.

        Args:
            tournament: Active tournament to sync

        Returns:
            Number of players updated
        """
        data = self.api.get_leaderboard(tournament.api_tourn_id, str(tournament.season_year))
        if not data or "leaderboardRows" not in data:
            logger.error("Failed to fetch leaderboard for %s", tournament.name)
            return 0

        updated = 0
        leaderboard_rows = data.get("leaderboardRows", [])

        # Collect all positions for tie calculation
        all_positions = [p.get("position", "") for p in leaderboard_rows]

        try:
            self._derive_status(tournament, data)

            for player_data in leaderboard_rows:
                player = GolfPlayer.query.filter_by(api_player_id=player_data.get("playerId")).first()
                if not player:
                    continue

                result = GolfTournamentResult.query.filter_by(
                    tournament_id=tournament.id,
                    player_id=player.id
                ).first()

                if not result:
                    result = GolfTournamentResult(
                        tournament_id=tournament.id,
                        player_id=player.id
                    )
                    db.session.add(result)

                result.status = player_data.get("status", result.status or "active")
                result.rounds_completed = len(player_data.get("rounds", []))
                result.final_position = player_data.get("position", result.final_position)

                # Parse score to par from "total" field
                result.score_to_par = parse_score_to_par(player_data.get("total"))

                # Calculate projected earnings based on current position
                position = player_data.get("position", "")
                projected_earnings = calculate_projected_earnings(
                    position_str=position,
                    purse=tournament.purse,
                    all_positions=all_positions
                )
                result.earnings = projected_earnings

                updated += 1

            db.session.commit()
            logger.info(
                "Updated live leaderboard for %s (%s entries, projected earnings calculated)",
                tournament.name,
                updated
            )
        except Exception:
            db.session.rollback()
            logger.exception("Failed updating live leaderboard for %s", tournament.name)
            return 0

        return updated


def get_upcoming_tournament(days_ahead: int = 7) -> Optional[GolfTournament]:
    """Get the next upcoming tournament within specified days."""
    now = datetime.now(GOLF_LEAGUE_TZ)
    cutoff = now + timedelta(days=days_ahead)

    return GolfTournament.query.filter(
        GolfTournament.status == "upcoming",
        GolfTournament.start_date <= cutoff,
        GolfTournament.start_date >= now
    ).order_by(GolfTournament.start_date).first()


def get_just_completed_tournament() -> Optional[GolfTournament]:
    """Get tournament that just completed (ended within last 24 hours)."""
    now = datetime.now(GOLF_LEAGUE_TZ)
    yesterday = now - timedelta(days=1)

    return GolfTournament.query.filter(
        GolfTournament.status == "active",
        GolfTournament.end_date <= now,
        GolfTournament.end_date >= yesterday
    ).first()


def _refresh_statuses(tournaments):
    now = datetime.now(GOLF_LEAGUE_TZ)
    changed = False
    for tournament in tournaments:
        previous = tournament.status
        tournament.update_status_from_time(now)
        if tournament.status != previous:
            changed = True
    if changed:
        db.session.commit()


def get_upcoming_tournaments_window(days_ahead: int = 10) -> List[GolfTournament]:
    now = datetime.now(GOLF_LEAGUE_TZ)
    cutoff = now + timedelta(days=days_ahead)
    tournaments = GolfTournament.query.filter(
        GolfTournament.start_date <= cutoff,
        GolfTournament.end_date >= now,
        GolfTournament.status != "complete",
    ).order_by(GolfTournament.start_date).all()
    _refresh_statuses(tournaments)
    return tournaments


def get_active_tournaments() -> List[GolfTournament]:
    """Return all tournaments currently in 'active' status.

    Queries by status directly — the authoritative field maintained by
    update_status_from_time(). Avoids brittle end_date window math that
    breaks when end_date is stored as midnight UTC rather than end-of-day.
    """
    return GolfTournament.query.filter(
        GolfTournament.status == "active"
    ).order_by(GolfTournament.start_date).all()


def get_recently_completed_tournaments(days_back: int = 2) -> List[GolfTournament]:
    now = datetime.now(GOLF_LEAGUE_TZ)
    since = now - timedelta(days=days_back)
    tournaments = GolfTournament.query.filter(
        GolfTournament.end_date >= since,
        GolfTournament.end_date <= now + timedelta(hours=12),
    ).order_by(GolfTournament.end_date.desc()).all()
    _refresh_statuses(tournaments)
    return tournaments


def get_tournaments_pending_finalization() -> List[GolfTournament]:
    """Get tournaments that are complete but haven't had earnings finalized from API."""
    return GolfTournament.query.filter(
        GolfTournament.status == "complete",
        GolfTournament.results_finalized == False
    ).order_by(GolfTournament.end_date.desc()).all()
