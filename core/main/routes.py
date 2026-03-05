"""
Fantasy Sports Platform - Main Routes
=======================================
Home page and platform-level pages.
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp


@main_bp.route('/')
def index():
    """Platform home page — shows available games."""
    games = [
        {
            'name': "Golf Pick 'Em",
            'slug': 'golf',
            'description': 'Season-long PGA Tour fantasy. Pick one golfer per tournament. Points = prize money.',
            'status': 'Coming Soon',
            'emoji': '⛳',
            'color': 'success',
        },
        {
            'name': 'CFB Survivor Pool',
            'slug': 'cfb',
            'description': 'Weekly college football picks against the spread. Two lives. Last survivor wins.',
            'status': 'Coming Soon',
            'emoji': '🏈',
            'color': 'danger',
        },
        {
            'name': 'Masters Fantasy',
            'slug': 'masters',
            'description': 'Build your 10-golfer lineup across 6 tiers. Lowest total score wins.',
            'status': 'Coming Soon',
            'emoji': '🏆',
            'color': 'warning',
        },
    ]
    return render_template('main/index.html', games=games)
