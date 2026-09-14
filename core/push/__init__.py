from flask import Blueprint

# No url_prefix: this blueprint serves both /push/* (subscribe/unsubscribe/test)
# AND root paths the browser fetches by fixed name — /sw.js, /manifest.webmanifest,
# /app — so a blanket prefix would be wrong.
push_bp = Blueprint('push', __name__, template_folder='templates')

from core.push import routes  # noqa: E402, F401
