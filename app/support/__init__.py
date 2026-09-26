from flask import Blueprint

support_bp = Blueprint(
    "support",
    __name__,
    url_prefix="/support"
)

from app.support import routes