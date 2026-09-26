from flask import (
    Flask,
    redirect,
    url_for,
    flash,
    send_from_directory,
    render_template,
    request,
)
from flask_login import current_user, logout_user

from config import Config
from .extensions import db, migrate, login_manager, csrf, mail

import click

from .models import User, Company, SystemSetting

from .utils.company_settings import (
    format_currency,
    format_company_date,
    format_company_time,
    format_company_datetime,
    get_currency_code,
    get_currency_symbol,
    get_decimal_places,
    get_currency_position,
    get_date_format,
    get_time_format,
    get_company_timezone_name,
    company_now,
)


def create_app(config_class=Config):

    app = Flask(__name__)

    # ============================================================
    # LOAD CONFIGURATION
    # ============================================================

    app.config.from_object(config_class)

    # ============================================================
    # DATABASE DEBUG
    # ============================================================

    database_uri = app.config.get(
        "SQLALCHEMY_DATABASE_URI",
        ""
    )

    if database_uri.startswith("sqlite"):
        print("DATABASE: SQLite (Local Development)")
    elif database_uri.startswith("postgresql"):
        print("DATABASE: PostgreSQL")
    else:
        print(
            "DATABASE:",
            database_uri.split("://")[0]
            if "://" in database_uri
            else "Unknown"
        )
    # ============================================================
    # JINJA GLOBALS
    # ============================================================

    app.jinja_env.globals.update(
        format_currency=format_currency,
        format_company_date=format_company_date,
        format_company_time=format_company_time,
        format_company_datetime=format_company_datetime,

        get_currency_code=get_currency_code,
        get_currency_symbol=get_currency_symbol,
        get_decimal_places=get_decimal_places,
        get_currency_position=get_currency_position,

        get_date_format=get_date_format,
        get_time_format=get_time_format,
        get_company_timezone_name=get_company_timezone_name,

        company_now=company_now,
    )


    # ============================================================
    # INITIALIZE EXTENSIONS
    # ============================================================

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)


    # ============================================================
    # REGISTER BLUEPRINTS
    # ============================================================

    from .auth.routes import auth_bp
    from .dashboard.routes import dashboard_bp
    from .products.routes import products_bp
    from .inventory.routes import inventory_bp
    from .sales.routes import sales_bp
    from .purchases.routes import purchases_bp
    from .expenses.routes import expenses_bp
    from .payments.routes import payments_bp
    from .receivables.routes import receivables_bp
    from .payables.routes import payables_bp
    from .system_admin.routes import system_admin_bp
    from app.company_admin import company_admin_bp
    from app.reports import reports_bp
    from .main import main_bp
    from app.notifications import notifications_bp
    from app.settings import settings_bp
    from app.support import support_bp
    from app.search import search_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(receivables_bp)
    app.register_blueprint(payables_bp)
    app.register_blueprint(system_admin_bp)
    app.register_blueprint(company_admin_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(search_bp)

    @app.route("/offline")
    def offline():
        return render_template("offline.html")

    # ============================================================
    # SERVICE WORKER
    # ============================================================

    @app.route("/service-worker.js")
    def service_worker():

        response = send_from_directory(
            app.static_folder,
            "service-worker.js",
            mimetype="application/javascript"
        )

        # Allow the worker to control the entire application.
        response.headers["Service-Worker-Allowed"] = "/"

        # Always allow the browser to check for a new worker.
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    # ============================================================
    # MAINTENANCE PAGE
    # ============================================================

    @app.route("/maintenance")
    def maintenance():

        settings = SystemSetting.query.first()

        message = (
            settings.maintenance_message
            if settings and settings.maintenance_message
            else (
                "The system is currently undergoing maintenance. "
                "Please try again later."
            )
        )

        return render_template(
            "system/maintenance.html",
            maintenance_message=message
        )


    # ============================================================
    # CREATE SYSTEM ADMIN CLI
    # ============================================================

    @app.cli.command("create-system-admin")
    def create_system_admin():
        """Create the first BizFlow System Administrator."""

        from getpass import getpass

        existing_admin = User.query.filter_by(
            role="System Administrator"
        ).first()

        if existing_admin:
            click.echo(
                "A System Administrator already exists."
            )
            return

        click.echo("")
        click.echo(
            "=== BizFlow IMS System Administrator Setup ==="
        )
        click.echo("")

        username = click.prompt(
            "Username",
            type=str
        ).strip()

        email = click.prompt(
            "Email",
            type=str
        ).strip().lower()

        password = getpass(
            "Password: "
        )

        confirm_password = getpass(
            "Confirm password: "
        )

        if not username:
            click.echo(
                "Username cannot be empty."
            )
            return

        if not email:
            click.echo(
                "Email cannot be empty."
            )
            return

        if not password:
            click.echo(
                "Password cannot be empty."
            )
            return

        if password != confirm_password:
            click.echo(
                "Passwords do not match."
            )
            return

        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:
            click.echo(
                "A user with this email already exists."
            )
            return

        admin = User(
            company_id=None,
            username=username,
            email=email,
            role="System Administrator",
            is_active=True
        )

        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        click.echo("")
        click.echo(
            "System Administrator created successfully."
        )
        click.echo(
            f"Username: {username}"
        )
        click.echo(
            f"Email: {email}"
        )
        click.echo("")


    # ============================================================
    # GLOBAL REQUEST ACCESS CONTROL
    # ============================================================

    @app.before_request
    def enforce_company_access():

        # --------------------------------------------------------
        # PWA SERVICE WORKER
        # --------------------------------------------------------
        #
        # The service worker must always be served directly.
        # It must not be redirected to login or maintenance.
        # --------------------------------------------------------

        if request.path == "/service-worker.js":
            return

        # --------------------------------------------------------
        # 1. PUBLIC USERS
        # --------------------------------------------------------

        if not current_user.is_authenticated:
            return


        # --------------------------------------------------------
        # 2. SYSTEM ADMINISTRATOR
        # --------------------------------------------------------
        #
        # SYSTEM ADMINISTRATORS ARE NEVER BLOCKED BY
        # MAINTENANCE MODE.
        #
        # This MUST happen before the maintenance check.
        # --------------------------------------------------------

        if current_user.is_system_admin:
            return


        # --------------------------------------------------------
        # 3. COMPANY ID CHECK
        # --------------------------------------------------------

        if current_user.company_id is None:

            logout_user()

            flash(
                "Your account is not associated with a company.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        # --------------------------------------------------------
        # 4. FIND COMPANY
        # --------------------------------------------------------

        company = db.session.get(
            Company,
            current_user.company_id
        )

        if company is None:

            logout_user()

            flash(
                "Your company account could not be found.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        # --------------------------------------------------------
        # 5. COMPANY ACTIVE CHECK
        # --------------------------------------------------------

        if not company.is_active:

            logout_user()

            flash(
                "Your company account has been deactivated. "
                "Please contact the system administrator.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        # --------------------------------------------------------
        # 6. USER ACTIVE CHECK
        # --------------------------------------------------------

        if not current_user.is_active:

            logout_user()

            flash(
                "Your account has been deactivated.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        # --------------------------------------------------------
        # 7. MAINTENANCE MODE
        # --------------------------------------------------------
        #
        # At this point:
        #
        # - User is authenticated
        # - User is NOT a System Administrator
        # - User belongs to a company
        # - Company exists
        # - Company is active
        # - User is active
        #
        # Therefore maintenance mode only affects
        # Company Administrators and Staff.
        # --------------------------------------------------------

        settings = SystemSetting.query.first()

        if (
            settings
            and settings.maintenance_mode
            and request.endpoint != "maintenance"
        ):

            return redirect(
                url_for("maintenance")
            )


    # ============================================================
    # LOAD MODELS
    # ============================================================

    from . import models


    return app