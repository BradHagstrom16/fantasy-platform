"""Platform-wide Jinja context processors."""
import os
import subprocess
from pathlib import Path

from flask import current_app
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from games.registry import joined_games
from models.push import PushSubscription


def member_on_the_wire() -> bool:
    """Does the signed-in member hold any live push subscription, on any
    device? The Wire's distribution nudges (the lounge strip, the room
    nudges, the profile link) are omitted for them (ADR-074, "this member,
    not this device", Brad 2026-10-08): a member who turned it on once is
    never asked again, on any device, until every one of their devices is
    gone. One query, called at most once per page."""
    if not current_user.is_authenticated:
        return False
    return db.session.scalar(
        select(PushSubscription.id)
        .filter_by(user_id=current_user.id).limit(1)) is not None


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

    @app.context_processor
    def inject_on_the_wire():
        # A callable, not a value: the query runs only where a template asks.
        return {'on_the_wire': member_on_the_wire}

    @app.context_processor
    def inject_vapid_public_key():
        # Rendered as data-vapid-key on <body> for push.js. Blank when web push
        # is unconfigured — push.js then never reveals the wire button.
        return {'vapid_public_key': current_app.config.get('VAPID_PUBLIC_KEY', '')}
