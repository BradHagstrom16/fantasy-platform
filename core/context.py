"""Platform-wide Jinja context processors."""
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from games.registry import joined_games


def register_context_processors(app):
    """Attach platform-wide context processors to the Flask app."""

    @app.context_processor
    def inject_nav_games():
        try:
            games = joined_games(current_user)
        except SQLAlchemyError:
            # DB session may be in a bad state when the navbar renders during
            # 500-page handling — degrade to empty nav rather than re-500.
            games = []
        return {'nav_games': games}
