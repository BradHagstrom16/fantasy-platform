"""
CFB Survivor's half of the game-day scores pass (ADR-063)
=========================================================
``wants``: is there an unsettled, unscored game on an incomplete week whose
deadline has passed, that kicked off between GAME_COULD_HAVE_ENDED and
GAME_DAY_WINDOW ago? NFL is never wanted.

The passed-deadline term is deliberate: a Thursday or Friday game is not
graded before Saturday 11:00 CT. Grading it early would debit a life on the
standings and reveal the pick before the deadline. Survivor's Thursday
finals land on the first Saturday tick after the deadline; the Docket wants
those games the night they play (its sides reveal at kickoff, ADR-060), so
that spend is the Docket's.

``home_score IS NULL`` stops polling on a tie flagged for manual review
(score_fetcher.apply_scores_to_games writes the scores and no winner);
in-progress events never write CFB scores, so the term is safe.

``apply``: the daily path with its side effects switched off —
``run_scores(prefetched=…, notify=False, retry_open=False)`` — so ADR-061
per-game grading, the recap letter on the tick that settles the last game,
and STUCK detection stay on one code path. ``run_scores`` never raises and
the CFB CLI exits 0 on a week error, so this consumer raises instead: the
game-day unit must fail loudly where the daily unit mails.
"""
from games.cfb.constants import SPORT_KEY
from games.cfb.models import CfbGame, CfbWeek
from games.cfb.utils import deadline_has_passed, get_current_time, make_aware
from games.gameday import GAME_COULD_HAVE_ENDED, GAME_DAY_WINDOW, GameDayConsumer


def wants(sport):
    if sport != SPORT_KEY:
        return False
    now = get_current_time()
    for week in CfbWeek.query.filter_by(is_complete=False).all():
        if not deadline_has_passed(week.deadline):
            continue
        for game in CfbGame.query.filter_by(week_id=week.id).all():
            if (game.game_time is None or game.is_no_contest
                    or game.home_team_won is not None
                    or game.home_score is not None):
                continue
            age = now - make_aware(game.game_time)
            if GAME_COULD_HAVE_ENDED <= age <= GAME_DAY_WINDOW:
                return True
    return False


def apply(events_by_sport):
    from games.cfb.services.automation import run_scores

    events = events_by_sport.get(SPORT_KEY)
    if events is None:
        return {'status': 'skipped', 'details': 'no ncaaf events'}
    outcome = run_scores(prefetched=events, notify=False, retry_open=False)
    failed = [r for r in outcome.get('week_results', [])
              if r.get('status') == 'error']
    if failed:
        raise RuntimeError('; '.join(
            f"week {r.get('week_number')}: {r.get('details')}" for r in failed))
    return outcome


CONSUMER = GameDayConsumer(slug='cfb', wants=wants, apply=apply)
