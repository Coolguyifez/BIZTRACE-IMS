# app/main/routes.py

from flask import render_template, redirect, url_for
from flask_login import current_user

from app.main import main_bp


@main_bp.route("/")
def index():

    if current_user.is_authenticated:

        if current_user.is_system_admin:
            return redirect(
                url_for("system_admin.dashboard")
            )

        return redirect(
            url_for("dashboard.dashboard")
        )

    return render_template(
        "auth/welcome.html"
    )