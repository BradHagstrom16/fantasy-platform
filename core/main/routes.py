"""
Fantasy Sports Platform - Main Routes
=======================================
Home page and platform-level pages.
"""
from flask import render_template, url_for
from flask_login import current_user

from core.main import main_bp


@main_bp.route('/')
def index():
    """Platform home page — shows available games."""
    games = [
        {
            'name': 'World Cup Fantasy',
            'slug': 'worldcup',
            'description': 'Draft 5 tiers of national teams. Earn points as your picks advance through the tournament.',
            'status': 'Live Now',
            'emoji': '🌍',
            'color': 'primary',
            'url': url_for('worldcup.index'),
        },
        {
            'name': "Golf Pick 'Em",
            'slug': 'golf',
            'description': 'Season-long PGA Tour fantasy. Pick one golfer per tournament. Points = prize money.',
            'status': 'Coming Soon',
            'emoji': '⛳',
            'color': 'success',
            'url': None,
        },
        {
            'name': 'CFB Survivor Pool',
            'slug': 'cfb',
            'description': 'Weekly college football picks against the spread. Two lives. Last survivor wins.',
            'status': 'Coming Soon',
            'emoji': '🏈',
            'color': 'danger',
            'url': None,
        },
    ]
    return render_template('main/index.html', games=games)
