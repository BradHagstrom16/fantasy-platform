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
    featured_game = {
        'name': '2026 FIFA World Cup',
        'slug': 'worldcup',
        'description': 'Pick 9 national teams across 5 tiers. Points accumulate as your teams win and advance through the bracket.',
        'emoji': '⚽',
        'url': url_for('worldcup.index'),
    }

    other_games = [
        {
            'name': "Golf Pick 'Em",
            'slug': 'golf',
            'description': 'Season-long PGA Tour fantasy. Pick one golfer per tournament. Points = prize money.',
            'emoji': '⛳',
            'url': None,
        },
        {
            'name': 'CFB Survivor Pool',
            'slug': 'cfb',
            'description': 'Weekly college football picks against the spread. Two lives. Last survivor wins.',
            'emoji': '🏈',
            'url': None,
        },
    ]
    return render_template(
        'main/index.html',
        featured_game=featured_game,
        other_games=other_games,
    )
