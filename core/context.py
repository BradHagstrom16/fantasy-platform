"""Platform-wide Jinja context processors."""
from flask_login import current_user

from games.registry import joined_games


def register_context_processors(app):
    """Attach platform-wide context processors to the Flask app."""

    @app.context_processor
    def inject_nav_games():
        try:
            games = joined_games(current_user)
        except Exception:
            # Anonymous / detached contexts — render empty nav rather than 500.
            games = []
        return {'nav_games': games}
