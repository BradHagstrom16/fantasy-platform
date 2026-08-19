"""Platform-wide Jinja context processors."""
import os
import subprocess
from pathlib import Path

from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from games.registry import joined_games


def _compute_asset_version() -> str:
    """Resolve a cache-bust token appended to every CSS/JS asset URL.

    Resolution order:
      1. `ASSET_VERSION` env var (explicit override for tests, CI, non-git
         deploys — empty / unset means fall through).
      2. `git rev-parse --short HEAD` run in the project root.
      3. Literal `'dev'` fallback so templates never render `?v=` alone.

    The result is captured once at app-factory init and read from a closure
    in `inject_asset_version`; Gunicorn workers boot fresh on each
    `systemctl restart fantasy-platform`, so a deploy rolls the value
    forward without per-request overhead.

    Why: nginx serves `/static/` with `Cache-Control: public, immutable`
    plus a 30-day TTL — Cloudflare's edge then honors that and caches the
    bytes for up to 30 days, which silently swallows post-deploy CSS/JS
    changes (PR #18 fallout). Content-versioned URLs (`style.css?v=<sha>`)
    flip the policy from "trust me" to "the URL itself names the bytes" —
    new deploy = new URL = fresh fetch at every edge. The immutable
    header is now correct because the bytes at each versioned URL really
    are immutable.
    """
    env = os.environ.get('ASSET_VERSION', '').strip()
    if env:
        return env
    project_root = Path(__file__).resolve().parent.parent
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=project_root,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip().decode('ascii')
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return 'dev'
    return sha or 'dev'


def register_context_processors(app):
    """Attach platform-wide context processors to the Flask app."""
    asset_version = _compute_asset_version()

    @app.context_processor
    def inject_nav_games():
        try:
            games = joined_games(current_user)
        except SQLAlchemyError:
            # DB session may be in a bad state when the navbar renders during
            # 500-page handling — degrade to empty nav rather than re-500.
            games = []
        # Navbar split (design review 2026-08-18): the top-bar switcher
        # carries active games only; a completed game moves to the account
        # dropdown's Archive section for its members. joined_games itself
        # still returns completed entries — the archive-reachability
        # contract lives at the registry seam (test_registry_seam), and
        # this split is navbar presentation only.
        return {
            'nav_games': [g for g in games if g.status != 'completed'],
            'nav_archived': [g for g in games if g.status == 'completed'],
        }

    @app.context_processor
    def inject_asset_version():
        return {'asset_version': asset_version}
