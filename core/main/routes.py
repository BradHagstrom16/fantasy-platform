"""
Fantasy Sports Platform - Main Routes
=======================================
Home page and platform-level pages. Registry-driven.
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from games.registry import (
    joined_games, available_games, coming_soon_games, featured_games,
)


@main_bp.route('/')
def index():
    """Platform home page. Sections driven by games.registry."""
    if current_user.is_authenticated:
        return render_template(
            'main/index.html',
            mode='logged_in',
            joined=joined_games(current_user),
            available=available_games(current_user),
            coming_soon=coming_soon_games(),
            featured=featured_games(current_user),
        )
    return render_template(
        'main/index.html',
        mode='logged_out',
        joined=[],
        available=available_games(current_user),
        coming_soon=coming_soon_games(),
        featured=featured_games(current_user),
    )
