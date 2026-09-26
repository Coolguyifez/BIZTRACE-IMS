from flask import Blueprint

company_admin_bp = Blueprint(
    "company_admin",
    __name__,
    url_prefix="/company-admin"
)

from app.company_admin import routes