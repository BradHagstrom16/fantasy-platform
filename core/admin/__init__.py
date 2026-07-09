from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

# Route modules import admin_bp back from this package, so they can only be
# imported after the blueprint exists (standard Flask circular-import pattern).
from core.admin import (  # noqa: E402
    announce,  # noqa: F401
    commish_note,  # noqa: F401
    enrollments,  # noqa: F401
    routes,  # noqa: F401
)
