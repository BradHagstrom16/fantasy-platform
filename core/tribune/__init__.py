"""The Tribune: every sent Club Letter, on the record (core/tribune).

A sent announcement (models.content.Announcement) is an issue. The desk
(core/admin/announce.py) stores the page rendering at send; this blueprint
lists the issues and prints one. Members only.
"""
from flask import Blueprint

tribune_bp = Blueprint('tribune', __name__, url_prefix='/tribune',
                       template_folder='templates')

from core.tribune import routes  # noqa: E402, F401
