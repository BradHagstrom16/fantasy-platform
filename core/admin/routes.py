"""
Fantasy Sports Platform - Admin Routes
========================================
Platform-level admin: user management, overview.
"""
from functools import wraps

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models.user import User
from games.golf.models import GolfEnrollment
from games.cfb.models import CfbEnrollment
from games.worldcup.models import WorldCupEnrollment
from core.admin import admin_bp


def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def dashboard():
    total_users = User.query.count()

    games = [
        {
            'name': 'World Cup Fantasy',
            'emoji': '🌍',
            'slug': 'worldcup',
            'admin_url': url_for('worldcup.admin_dashboard'),
            'payments_url': url_for('worldcup.admin_payments'),
            'enrolled': WorldCupEnrollment.query.count(),
            'paid': WorldCupEnrollment.query.filter_by(has_paid=True).count(),
        },
        {
            'name': "Golf Pick 'Em",
            'emoji': '⛳',
            'slug': 'golf',
            'admin_url': url_for('golf.admin_dashboard'),
            'payments_url': url_for('golf.admin_payments'),
            'enrolled': GolfEnrollment.query.count(),
            'paid': GolfEnrollment.query.filter_by(has_paid=True).count(),
        },
        {
            'name': 'CFB Survivor Pool',
            'emoji': '🏈',
            'slug': 'cfb',
            'admin_url': url_for('cfb.admin_dashboard'),
            'payments_url': url_for('cfb.admin_payments'),
            'enrolled': CfbEnrollment.query.count(),
            'paid': CfbEnrollment.query.filter_by(has_paid=True).count(),
        },
    ]

    active_games = sum(1 for g in games if g['enrolled'] > 0)
    paid_users = sum(g['paid'] for g in games)

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        games=games,
        active_games=active_games,
        paid_users=paid_users,
    )


@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash('You cannot change your own admin status.', 'error')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        status = 'admin' if user.is_admin else 'regular user'
        flash(f'{user.get_display_name()} is now a {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    temp_password = 'changeme123'
    user.set_password(temp_password)
    db.session.commit()
    flash(f'Password for {user.get_display_name()} reset to: {temp_password}', 'warning')
    return redirect(url_for('admin.users'))
