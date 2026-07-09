"""Platform admin: add a user to a game's current-season enrollment."""
from flask import flash, redirect, render_template, request, url_for

from core.admin import admin_bp
from core.admin.routes import admin_required
from extensions import db
from games.registry import GAMES, get_entry
from models.user import User


@admin_bp.route('/enrollments', methods=['GET', 'POST'])
@admin_required
def enrollments():
    """List users + open games; on POST, call the selected game's admin_enroll."""
    open_entries = [e for e in GAMES if e.status == 'open']
    users = User.query.order_by(User.username).all()

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)
        slug = (request.form.get('game_slug') or '').strip()

        if not user_id or not slug:
            flash('Both user and game are required.', 'error')
            return redirect(url_for('admin.enrollments'))

        try:
            entry = get_entry(slug)
        except KeyError:
            flash('Unknown game.', 'error')
            return redirect(url_for('admin.enrollments'))

        if entry.status != 'open':
            flash(f'{entry.display_name} is not accepting new enrollments.', 'error')
            return redirect(url_for('admin.enrollments'))

        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(url_for('admin.enrollments'))

        existing = entry.get_enrollment(user_id)
        if existing is not None:
            flash(
                f'{user.get_display_name()} is already enrolled in '
                f'{entry.display_name}.',
                'info',
            )
            return redirect(url_for('admin.enrollments'))

        entry.admin_enroll(user_id)
        flash(
            f'Enrolled {user.get_display_name()} in {entry.display_name}.',
            'success',
        )
        return redirect(url_for('admin.enrollments'))

    return render_template(
        'admin/enrollments.html',
        open_entries=open_entries,
        users=users,
    )
