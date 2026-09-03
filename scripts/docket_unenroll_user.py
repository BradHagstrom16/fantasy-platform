"""Unenroll one user from The Docket (admin, manual — no self-serve unenroll).

Per the per-game enrollment design (Non-Goals,
docs/superpowers/specs/2026-04-17-per-game-enrollment-design.md): "No
user-initiated unenroll. If a user needs out, a platform admin handles it
manually." No route/CLI command does this, by design — this script is that
manual handling, following the scripts/wipe_pre_launch_enrollments.py shape.

Usage (dry run):
    venv/bin/python scripts/docket_unenroll_user.py <username-or-email>

Apply:
    venv/bin/python scripts/docket_unenroll_user.py <username-or-email> --confirm

Behavior:
- Resolves the user case-insensitively by username OR email.
- Deletes their current-season DocketTiebreakerPrediction + DocketPick rows,
  then their DocketEnrollment row. The User account itself is untouched.
- Aborts loudly if any DocketWeekResult rows exist for the user — that means
  a week already graded them, and pulling them out needs deliberate handling
  (standings/purse math for a closed week), not a blind delete.
"""
import argparse
import sys

from sqlalchemy import func, select

from app import create_app
from extensions import db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', help='Username or email of the user to unenroll')
    parser.add_argument(
        '--confirm', action='store_true',
        help='Actually perform the deletes. Without this flag, dry-run only.',
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from games.docket.models import (
            DocketEnrollment,
            DocketPick,
            DocketTiebreakerPrediction,
            DocketWeekResult,
        )
        from games.docket.services.weeks import SEASON_YEAR
        from models.user import User
        from utils.identifier import normalize_identifier

        needle = normalize_identifier(args.identifier)
        user = (
            db.session.scalar(select(User).where(func.lower(User.username) == needle))
            or db.session.scalar(select(User).where(func.lower(User.email) == needle))
        )
        if user is None:
            print(f'ABORT: no user found matching {args.identifier!r}.')
            return 1

        enrollment = DocketEnrollment.query.filter_by(
            user_id=user.id, season_year=SEASON_YEAR
        ).first()
        if enrollment is None:
            print(f'No {SEASON_YEAR} Docket enrollment found for '
                  f'{user.username} (user_id={user.id}). Nothing to do.')
            return 0

        graded_weeks = DocketWeekResult.query.filter_by(user_id=user.id).count()
        if graded_weeks:
            print('ABORT: refusing to unenroll — this user already has '
                  f'{graded_weeks} graded DocketWeekResult row(s). Removing '
                  'them now would silently change closed-week standings/purse '
                  'math; handle this case manually instead.')
            return 1

        pick_count = DocketPick.query.filter_by(user_id=user.id).count()
        prediction_count = DocketTiebreakerPrediction.query.filter_by(
            user_id=user.id
        ).count()

        print('Planning to delete:')
        print(f'  User:                       {user.username} '
              f'(user_id={user.id}, email={user.email})')
        print(f'  DocketEnrollment:           season={enrollment.season_year} '
              f'is_admin={enrollment.is_admin} has_paid={enrollment.has_paid} '
              f'joined={enrollment.created_at}')
        print(f'  DocketPick rows:            {pick_count}')
        print(f'  DocketTiebreakerPrediction: {prediction_count}')
        print('  (User account itself untouched.)')

        if not args.confirm:
            print('\nDry run — pass --confirm to apply.')
            return 0

        try:
            DocketTiebreakerPrediction.query.filter_by(
                user_id=user.id
            ).delete(synchronize_session=False)
            DocketPick.query.filter_by(
                user_id=user.id
            ).delete(synchronize_session=False)
            db.session.delete(enrollment)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            print(f'ERROR: rollback — {exc}')
            return 2

        print('\nDone.')
        return 0


if __name__ == '__main__':
    sys.exit(main())
