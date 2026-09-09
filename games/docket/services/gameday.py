"""
The Docket's half of the game-day scores pass (ADR-063)
=======================================================
``wants``: is there a game of this sport that is not final, not ruled No
Contest, on an ungraded week (``default_error_tenths IS NULL``, the ADR-047
marker), that kicked off between GAME_COULD_HAVE_ENDED and GAME_DAY_WINDOW
ago? Every Docket datetime is naive UTC (D6), as is ``now_naive()``.

``apply``: for each ungraded week that OWNS a qualifying game — never the
clock-resolved week, which between the Tue 06:00 CT boundary and the 06:15
setup (or after a failed setup) may have no row yet — run the ordinary
score write (``sync_scores`` with the prefetched events; a sport absent
from the dict is never fetched) and then the ordinary grade attempt
(``try_grade_week``; ``not_ready`` is the normal Saturday outcome). That
subsumes the daily CLI's previous-week catch-up. The CLI itself is not
reused: it carries click echo, three SystemExit sites and clock-resolved
week selection, none of which belong in a seam.
"""
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketGame, DocketWeek
from games.docket.services.enrollment import roster_user_ids_as_of
from games.docket.services.grading_pass import try_grade_week
from games.docket.services.importer import SPORTS
from games.docket.services.picks import now_naive
from games.docket.services.scores import sync_scores
from games.gameday import GAME_COULD_HAVE_ENDED, GAME_DAY_WINDOW, GameDayConsumer


def _qualifying(sports, now):
    """Games of ``sports`` that could have ended and are not yet settled,
    on weeks that have not graded."""
    return (
        select(DocketGame)
        .join(DocketWeek, DocketWeek.id == DocketGame.week_id)
        .where(
            DocketGame.sport.in_(list(sports)),
            DocketGame.is_final.is_(False),
            DocketGame.no_contest.is_(False),
            DocketWeek.default_error_tenths.is_(None),
            DocketGame.kickoff <= now - GAME_COULD_HAVE_ENDED,
            DocketGame.kickoff >= now - GAME_DAY_WINDOW,
        )
    )


def wants(sport):
    if sport not in SPORTS:
        return False
    stmt = _qualifying((sport,), now_naive()).limit(1)
    return db.session.scalars(stmt).first() is not None


def _owning_weeks(sports):
    now = now_naive()
    week_ids = select(_qualifying(sports, now).subquery().c.week_id).distinct()
    return db.session.scalars(
        select(DocketWeek).where(DocketWeek.id.in_(week_ids))
        .order_by(DocketWeek.week_number)).all()


def apply(events_by_sport):
    results = {}
    for week in _owning_weeks(events_by_sport):
        summary = sync_scores(week.week_number,
                              events_by_sport=events_by_sport)
        if summary.get('status') == 'error':
            raise RuntimeError(
                f'week {week.week_number}: '
                f'{"; ".join(summary.get("errors", []))}')
        graded = try_grade_week(
            week.id, user_ids=roster_user_ids_as_of(week.deadline_at))
        results[week.week_number] = {'sync': summary, 'grade': graded}
    return results


CONSUMER = GameDayConsumer(slug='docket', wants=wants, apply=apply)
