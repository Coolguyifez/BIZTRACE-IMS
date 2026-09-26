from flask import (
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_login import (
    login_required,
    current_user,
)

from app.extensions import db

from app.models import (
    CompanySetting,
    User,
    NotificationAssignment,
)

from app.notifications.service import (
    NOTIFICATION_CATEGORIES,
)

from . import settings_bp


# ============================================================
# HELPERS
# ============================================================

def get_company_settings():
    """
    Get settings for the currently logged-in user's company.

    Company settings are only available to users who belong
    to a company.
    """

    if not current_user.company_id:
        return None

    settings = CompanySetting.query.filter_by(
        company_id=current_user.company_id
    ).first()

    if not settings:

        settings = CompanySetting(
            company_id=current_user.company_id
        )

        db.session.add(settings)
        db.session.commit()

    return settings


def company_access_required():
    """
    Only Company Administrators can manage company settings.
    """

    return current_user.is_company_admin


def get_notification_users():
    """
    Return active users belonging to the current company.

    System Administrators and users from other companies are
    never included.
    """

    if not current_user.company_id:
        return []

    return (
        User.query
        .filter(
            User.company_id
            == current_user.company_id,

            User.is_active.is_(True),
        )
        .order_by(
            User.username.asc()
        )
        .all()
    )


def get_notification_assignment_map():
    """
    Return notification assignments in a form that is easy
    for the Jinja template to consume.

    Example:

        {
            "low_stock:2": True,
            "sale:2": True,
            "payment:3": True,
        }
    """

    if not current_user.company_id:
        return {}

    assignments = (
        NotificationAssignment.query
        .filter_by(
            company_id=current_user.company_id
        )
        .all()
    )

    return {
        f"{assignment.notification_category}:"
        f"{assignment.user_id}":
            bool(assignment.enabled)

        for assignment in assignments
    }


def save_notification_assignments():
    """
    Save the notification category assignments submitted
    from the Settings page.

    Only valid categories and users belonging to the current
    company are accepted.

    Existing assignments that are unchecked are removed.

    New assignments are created only for checked categories.
    """

    company_id = current_user.company_id

    if not company_id:
        return

    # --------------------------------------------------------
    # GET VALID COMPANY USERS
    # --------------------------------------------------------

    notification_users = (
        User.query
        .filter(
            User.company_id == company_id,
            User.is_active.is_(True),
        )
        .all()
    )

    valid_user_ids = {
        user.id
        for user in notification_users
    }

    # --------------------------------------------------------
    # VALID CATEGORIES
    # --------------------------------------------------------

    valid_categories = {
        category
        for category, label
        in NOTIFICATION_CATEGORIES
    }

    # --------------------------------------------------------
    # READ FORM VALUES
    # --------------------------------------------------------

    submitted_assignments = set(
        request.form.getlist(
            "notification_assignment"
        )
    )

    # --------------------------------------------------------
    # NORMALIZE / VALIDATE FORM VALUES
    # --------------------------------------------------------

    selected_assignments = set()

    for value in submitted_assignments:

        if not value:
            continue

        try:

            category, user_id_text = (
                value.split(":", 1)
            )

            category = (
                category
                .strip()
                .lower()
            )

            user_id = int(
                user_id_text
            )

        except (
            ValueError,
            TypeError,
        ):

            continue

        # ----------------------------------------------------
        # VALIDATE CATEGORY
        # ----------------------------------------------------

        if category not in valid_categories:
            continue

        # ----------------------------------------------------
        # VALIDATE USER
        # ----------------------------------------------------

        if user_id not in valid_user_ids:
            continue

        selected_assignments.add(
            (category, user_id)
        )

    # --------------------------------------------------------
    # GET EXISTING ASSIGNMENTS
    # --------------------------------------------------------

    existing_assignments = (
        NotificationAssignment.query
        .filter_by(
            company_id=company_id
        )
        .all()
    )

    existing_map = {
        (
            assignment.notification_category,
            assignment.user_id,
        ): assignment

        for assignment in existing_assignments
    }

    # --------------------------------------------------------
    # CREATE / ENABLE SELECTED ASSIGNMENTS
    # --------------------------------------------------------

    for category, user_id in selected_assignments:

        key = (
            category,
            user_id,
        )

        assignment = (
            existing_map.get(key)
        )

        if assignment:

            assignment.enabled = True

        else:

            assignment = NotificationAssignment(

                company_id=company_id,

                user_id=user_id,

                notification_category=category,

                enabled=True,
            )

            db.session.add(
                assignment
            )

    # --------------------------------------------------------
    # DELETE UNSELECTED ASSIGNMENTS
    # --------------------------------------------------------

    for key, assignment in existing_map.items():

        if key not in selected_assignments:

            db.session.delete(
                assignment
            )


# ============================================================
# MAIN SETTINGS PAGE
# ============================================================

@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():

    # ========================================================
    # ACCESS CONTROL
    # ========================================================

    if not company_access_required():

        flash(
            "You do not have permission to manage company settings.",
            "danger",
        )

        return redirect(
            url_for("dashboard.dashboard")
        )

    # ========================================================
    # COMPANY SETTINGS
    # ========================================================

    settings = get_company_settings()

    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        # ====================================================
        # GENERAL / CURRENCY
        # ====================================================

        settings.currency_code = (
            request.form.get(
                "currency_code",
                "NGN",
            )
            .strip()
            .upper()
        )

        settings.currency_symbol = (
            request.form.get(
                "currency_symbol",
                "₦",
            )
            .strip()
        )

        try:

            decimal_places = int(
                request.form.get(
                    "decimal_places",
                    2,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            decimal_places = 2

        settings.decimal_places = max(
            0,
            min(
                decimal_places,
                4,
            ),
        )

        currency_position = (
            request.form.get(
                "currency_position",
                "before",
            )
        )

        if currency_position not in {
            "before",
            "after",
        }:

            currency_position = "before"

        settings.currency_position = (
            currency_position
        )

        # ====================================================
        # DATE & TIME
        # ====================================================

        settings.timezone = (
            request.form.get(
                "timezone",
                "Africa/Lagos",
            )
            .strip()
            or "Africa/Lagos"
        )

        settings.date_format = (
            request.form.get(
                "date_format",
                "DD/MM/YYYY",
            )
        )

        settings.time_format = (
            request.form.get(
                "time_format",
                "12h",
            )
        )

        settings.week_starts = (
            request.form.get(
                "week_starts",
                "Monday",
            )
        )

        # ====================================================
        # DOCUMENT NUMBERING
        # ====================================================

        settings.invoice_prefix = (
            request.form.get(
                "invoice_prefix",
                "INV",
            )
            .strip()
            .upper()
            or "INV"
        )

        settings.purchase_prefix = (
            request.form.get(
                "purchase_prefix",
                "PUR",
            )
            .strip()
            .upper()
            or "PUR"
        )

        settings.expense_prefix = (
            request.form.get(
                "expense_prefix",
                "EXP",
            )
            .strip()
            .upper()
            or "EXP"
        )

        try:

            number_length = int(
                request.form.get(
                    "number_length",
                    4,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            number_length = 4

        settings.number_length = max(
            2,
            min(
                number_length,
                8,
            ),
        )

        settings.include_date = (
            request.form.get(
                "include_date"
            )
            == "on"
        )

        number_reset = (
            request.form.get(
                "number_reset",
                "daily",
            )
        )

        if number_reset not in {
            "daily",
            "monthly",
            "yearly",
            "never",
        }:

            number_reset = "daily"

        settings.number_reset = (
            number_reset
        )

        # ====================================================
        # INVENTORY
        # ====================================================

        settings.allow_negative_stock = (
            request.form.get(
                "allow_negative_stock"
            )
            == "on"
        )

        settings.reserve_stock = (
            request.form.get(
                "reserve_stock"
            )
            == "on"
        )

        settings.low_stock_notifications = (
            request.form.get(
                "low_stock_notifications"
            )
            == "on"
        )

        settings.stock_adjustment_requires_note = (
            request.form.get(
                "stock_adjustment_requires_note"
            )
            == "on"
        )


        # ====================================================
        # NOTIFICATION ASSIGNMENTS
        # ====================================================

        try:

            save_notification_assignments()

            # ------------------------------------------------
            # SAVE ALL SETTINGS
            # ------------------------------------------------

            db.session.commit()

            flash(
                "Settings saved successfully.",
                "success",
            )

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                "Unable to save company settings: %s",
                exc,
            )

            flash(
                "Unable to save settings. Please try again.",
                "danger",
            )

        return redirect(
            url_for("settings.index")
        )

    # ========================================================
    # GET
    # ========================================================

    notification_users = (
        get_notification_users()
    )

    notification_assignment_map = (
        get_notification_assignment_map()
    )

    return render_template(
        "settings/index.html",

        settings=settings,

        notification_users=
            notification_users,

        notification_categories=
            NOTIFICATION_CATEGORIES,

        notification_assignment_map=
            notification_assignment_map,
    )


# ============================================================
# RESET SETTINGS
# ============================================================

@settings_bp.post("/reset")
@login_required
def reset():

    # ========================================================
    # ACCESS CONTROL
    # ========================================================

    if not company_access_required():

        flash(
            "You do not have permission to manage company settings.",
            "danger",
        )

        return redirect(
            url_for("dashboard.dashboard")
        )

    # ========================================================
    # GET COMPANY SETTINGS
    # ========================================================

    settings = CompanySetting.query.filter_by(
        company_id=current_user.company_id
    ).first()

    # ========================================================
    # CREATE DEFAULT SETTINGS IF MISSING
    # ========================================================

    if not settings:

        settings = CompanySetting(
            company_id=current_user.company_id
        )

        db.session.add(
            settings
        )

    # ========================================================
    # RESET EXISTING SETTINGS
    # ========================================================

    else:

        # ----------------------------------------------------
        # CURRENCY
        # ----------------------------------------------------

        settings.currency_code = "NGN"
        settings.currency_symbol = "₦"
        settings.decimal_places = 2
        settings.currency_position = "before"

        # ----------------------------------------------------
        # DATE & TIME
        # ----------------------------------------------------

        settings.timezone = "Africa/Lagos"
        settings.date_format = "DD/MM/YYYY"
        settings.time_format = "12h"
        settings.week_starts = "Monday"

        # ----------------------------------------------------
        # DOCUMENT NUMBERING
        # ----------------------------------------------------

        settings.invoice_prefix = "INV"
        settings.purchase_prefix = "PUR"
        settings.expense_prefix = "EXP"
        settings.number_length = 4
        settings.include_date = True
        settings.number_reset = "daily"

        # ----------------------------------------------------
        # INVENTORY
        # ----------------------------------------------------

        settings.allow_negative_stock = False
        settings.reserve_stock = True
        settings.low_stock_notifications = True
        settings.stock_adjustment_requires_note = True

        # ----------------------------------------------------
        # SYSTEM
        # ----------------------------------------------------

        settings.maintenance_mode = False
        settings.maintenance_message = None

    # ========================================================
    # SAVE
    # ========================================================

    try:

        db.session.commit()

        flash(
            "Settings restored to their default values.",
            "success",
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "Unable to reset company settings: %s",
            exc,
        )

        flash(
            "Unable to reset settings.",
            "danger",
        )

    return redirect(
        url_for("settings.index")
    )