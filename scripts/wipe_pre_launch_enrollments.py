"""
Wipe pre-launch CFB + Golf enrollment data.

Usage (dry run):
    venv/bin/python scripts/wipe_pre_launch_enrollments.py

Apply:
    venv/bin/python scripts/wipe_pre_launch_enrollments.py --confirm

Behavior:
- Deletes ALL CfbEnrollment + dependent CfbPick rows.
- Deletes ALL GolfEnrollment + dependent GolfPick + GolfSeasonPlayerUsage rows.
- Leaves WorldCupEnrollment untouched (World Cup is live).
- Leaves User accounts untouched.
- Aborts loudly if any CfbGame, CfbWeek, or GolfTournament in the current
  season is marked complete — that would indicate real play happened,
  not test data.
"""
import argparse
import sys

from app import create_app
from extensions import db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--confirm', action='store_true',
        help='Actually perform the deletes. Without this flag, dry-run only.',
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from games.cfb.models import CfbEnrollment, CfbPick, CfbGame, CfbWeek
        from games.golf.models import (
            GolfEnrollment, GolfPick, GolfSeasonPlayerUsage, GolfTournament,
        )

        cfb_season = app.config.get('CFB_SEASON_YEAR', 2026)
        golf_season = app.config.get('SEASON_YEAR', 2026)

        # Safety: refuse to run if the current season has seen real play.
        cfb_complete_weeks = CfbWeek.query.filter_by(is_complete=True).count()
        cfb_complete_games = CfbGame.query.filter(
            CfbGame.home_team_won.isnot(None)
        ).count()
        golf_complete_tournaments = GolfTournament.query.filter_by(
            season_year=golf_season, status='complete',
        ).count()

        if cfb_complete_weeks or cfb_complete_games or golf_complete_tournaments:
            print('ABORT: Refusing to wipe — real play appears to have occurred:')
            print(f'  CFB completed weeks: {cfb_complete_weeks}')
            print(f'  CFB games with recorded outcome: {cfb_complete_games}')
            print(f'  Golf completed tournaments: {golf_complete_tournaments}')
            return 1

        cfb_pick_count = CfbPick.query.count()
        cfb_enr_count = CfbEnrollment.query.count()
        golf_pick_count = GolfPick.query.count()
        golf_usage_count = GolfSeasonPlayerUsage.query.count()
        golf_enr_count = GolfEnrollment.query.count()

        print(f'Planning to delete:')
        print(f'  CfbPick rows:               {cfb_pick_count}')
        print(f'  CfbEnrollment rows:         {cfb_enr_count}')
        print(f'  GolfPick rows:              {golf_pick_count}')
        print(f'  GolfSeasonPlayerUsage rows: {golf_usage_count}')
        print(f'  GolfEnrollment rows:        {golf_enr_count}')
        print(f'  (WorldCupEnrollment, Users untouched.)')

        if not args.confirm:
            print('\nDry run — pass --confirm to apply.')
            return 0

        try:
            CfbPick.query.delete(synchronize_session=False)
            CfbEnrollment.query.delete(synchronize_session=False)
            GolfPick.query.delete(synchronize_session=False)
            GolfSeasonPlayerUsage.query.delete(synchronize_session=False)
            GolfEnrollment.query.delete(synchronize_session=False)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            print(f'ERROR: rollback — {exc}')
            return 2

        print('\nDone.')
        return 0


if __name__ == '__main__':
    sys.exit(main())
