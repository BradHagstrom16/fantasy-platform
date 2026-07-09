from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

from core.admin import (
    announce,  # noqa: E402, F401
    commish_note,  # noqa: E402, F401
    enrollments,  # noqa: E402, F401
    routes,  # noqa: E402, F401
)
