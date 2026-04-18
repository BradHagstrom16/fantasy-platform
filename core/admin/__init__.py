from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

from core.admin import routes  # noqa: E402, F401
from core.admin import enrollments  # noqa: E402, F401
