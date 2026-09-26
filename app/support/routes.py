from flask import render_template
from flask_login import login_required

from app.support import support_bp


@support_bp.route("/")
@login_required
def index():
    return render_template("support/index.html")