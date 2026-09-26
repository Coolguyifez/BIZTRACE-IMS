from flask import Blueprint

search_bp = Blueprint(
    "search",
    __name__,
    url_prefix="/search"
)

from app.search import routes