from datetime import datetime, timezone, timedelta
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)

from flask_login import (
    login_required,
    current_user
)

from app.company_admin.decorators import (
    company_permission_required
)

from app.extensions import db

from app.models import (
    Expense,
    ExpenseCategory
)

from app.notifications.service import (
    notify_success,
    check_financial_alerts
)

from app.utils.company_settings import (
    format_currency,
    get_company_timezone
)

from app.utils.document_numbers import (
    generate_expense_number
)

from .forms import (
    ExpenseForm,
    ExpenseCategoryForm
)


expenses_bp = Blueprint(
    "expenses",
    __name__,
    url_prefix="/expenses"
)


# =========================================================
# DATETIME HELPERS
# =========================================================

def now_utc():
    """
    Return the current timezone-aware UTC datetime.

    Database timestamps remain stored in UTC.
    """
    return datetime.now(timezone.utc)


def now_company():
    """
    Return the current datetime using the current company's
    configured timezone.
    """
    return datetime.now(
        get_company_timezone()
    )


def ensure_utc(value):
    """
    Normalize a datetime to timezone-aware UTC.

    SQLite may return naive datetime values.
    In BizFlow, naive database timestamps are treated as UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def company_date_to_utc(value):
    """
    Convert a company-local date into the beginning of that
    date in UTC.

    Example:

        Company timezone:
            Africa/Lagos

        Local date:
            2026-09-25

        Stored timestamp:
            2026-09-24 23:00:00 UTC
    """

    if value is None:
        return None

    company_tz = get_company_timezone()

    local_datetime = datetime.combine(
        value,
        datetime.min.time()
    ).replace(
        tzinfo=company_tz
    )

    return local_datetime.astimezone(
        timezone.utc
    )


def company_day_boundaries(value=None):
    """
    Return the beginning and end of a company-local calendar
    day, converted to UTC.

    If no date is supplied, today's company-local date is used.
    """

    company_tz = get_company_timezone()

    if value is None:

        current_company = datetime.now(
            company_tz
        )

        local_date = current_company.date()

    else:

        local_date = value

    start_company = datetime.combine(
        local_date,
        datetime.min.time()
    ).replace(
        tzinfo=company_tz
    )

    end_company = (
        start_company +
        timedelta(days=1)
    )

    return (
        start_company.astimezone(
            timezone.utc
        ),
        end_company.astimezone(
            timezone.utc
        )
    )


def company_month_boundaries(year, month):
    """
    Return the beginning and end of a company-local month
    converted to UTC.
    """

    company_tz = get_company_timezone()

    start_company = datetime(
        year,
        month,
        1,
        tzinfo=company_tz
    )

    if month == 12:

        end_company = datetime(
            year + 1,
            1,
            1,
            tzinfo=company_tz
        )

    else:

        end_company = datetime(
            year,
            month + 1,
            1,
            tzinfo=company_tz
        )

    return (
        start_company.astimezone(
            timezone.utc
        ),
        end_company.astimezone(
            timezone.utc
        )
    )


def company_year_boundaries(year):
    """
    Return the beginning and end of a company-local year
    converted to UTC.
    """

    company_tz = get_company_timezone()

    start_company = datetime(
        year,
        1,
        1,
        tzinfo=company_tz
    )

    end_company = datetime(
        year + 1,
        1,
        1,
        tzinfo=company_tz
    )

    return (
        start_company.astimezone(
            timezone.utc
        ),
        end_company.astimezone(
            timezone.utc
        )
    )


def company_week_boundaries():
    """
    Return the beginning and end of the current company-local
    week.

    Sunday remains the first day of the week to preserve
    the existing application behavior.
    """

    company_tz = get_company_timezone()

    current_company = datetime.now(
        company_tz
    )

    days_since_sunday = (
        current_company.weekday() + 1
    ) % 7

    today_start_company = current_company.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    week_start_company = (
        today_start_company -
        timedelta(
            days=days_since_sunday
        )
    )

    week_end_company = (
        week_start_company +
        timedelta(days=7)
    )

    return (
        week_start_company.astimezone(
            timezone.utc
        ),
        week_end_company.astimezone(
            timezone.utc
        )
    )


# =========================================================
# FINANCIAL NOTIFICATION HELPER
# =========================================================

def run_expense_financial_alerts(
    expense,
    user_id=None
):
    """
    Run financial loss checks for the company-local date
    associated with an expense.

    Database timestamps remain UTC while the calendar day
    follows the company's configured timezone.
    """

    expense_date = expense.expense_date

    if hasattr(
        expense_date,
        "astimezone"
    ):

        expense_date = ensure_utc(
            expense_date
        ).astimezone(
            get_company_timezone()
        )

        financial_date = (
            expense_date.date()
        )

    elif hasattr(
        expense_date,
        "date"
    ):

        financial_date = (
            expense_date.date()
        )

    else:

        financial_date = expense_date

    start_datetime, end_datetime = (
        company_day_boundaries(
            financial_date
        )
    )

    return check_financial_alerts(
        company_id=current_user.company_id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        user_id=user_id
    )


# =========================================================
# EXPENSE LIST
# =========================================================

@expenses_bp.route("/")
@login_required
@company_permission_required("view_expenses")
def expenses():

    search = request.args.get(
        "q",
        "",
        type=str
    ).strip()

    period = request.args.get(
        "period",
        "all",
        type=str
    )

    month = request.args.get(
        "month",
        type=int
    )

    year = request.args.get(
        "year",
        type=int
    )

    query = (
        Expense.query
        .filter(
            Expense.company_id ==
            current_user.company_id
        )
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search:

        query = query.filter(
            db.or_(
                Expense.expense_number.ilike(
                    f"%{search}%"
                ),
                Expense.description.ilike(
                    f"%{search}%"
                ),
                Expense.reference.ilike(
                    f"%{search}%"
                )
            )
        )

    # -----------------------------------------------------
    # COMPANY LOCAL DATE
    # -----------------------------------------------------

    current_company = now_company()

    selected_month = (
        month
        or current_company.month
    )

    selected_year = (
        year
        or current_company.year
    )

    # -----------------------------------------------------
    # PERIOD FILTER
    # -----------------------------------------------------

    if period == "daily":

        start_date, end_date = (
            company_day_boundaries()
        )

        query = query.filter(
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date
        )

    elif period == "weekly":

        start_date, end_date = (
            company_week_boundaries()
        )

        query = query.filter(
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date
        )

    elif period == "monthly":

        if not 1 <= selected_month <= 12:

            selected_month = (
                current_company.month
            )

        if not 2000 <= selected_year <= 2100:

            selected_year = (
                current_company.year
            )

        start_date, end_date = (
            company_month_boundaries(
                selected_year,
                selected_month
            )
        )

        query = query.filter(
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date
        )

    elif period == "yearly":

        if not 2000 <= selected_year <= 2100:

            selected_year = (
                current_company.year
            )

        start_date, end_date = (
            company_year_boundaries(
                selected_year
            )
        )

        query = query.filter(
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date
        )

    # -----------------------------------------------------
    # RESULTS
    # -----------------------------------------------------

    expenses_list = (
        query
        .order_by(
            Expense.expense_date.desc(),
            Expense.id.desc()
        )
        .all()
    )

    total_amount = sum(
        (
            Decimal(
                str(expense.amount or 0)
            )
            for expense in expenses_list
        ),
        Decimal("0.00")
    )

    # -----------------------------------------------------
    # YEARS
    # -----------------------------------------------------

    years = range(
        current_company.year - 5,
        current_company.year + 1
    )

    return render_template(
        "expenses/expenses.html",

        expenses=expenses_list,

        total_amount=total_amount,

        search=search,

        period=period,

        month=selected_month,

        year=selected_year,

        years=years
    )


# =========================================================
# NEW EXPENSE
# =========================================================

@expenses_bp.route(
    "/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_expenses")
def new_expense():

    form = ExpenseForm()

    categories = (
        ExpenseCategory.query
        .filter(
            ExpenseCategory.company_id ==
            current_user.company_id
        )
        .order_by(
            ExpenseCategory.name.asc()
        )
        .all()
    )

    form.category_id.choices = [
        (
            category.id,
            category.name
        )
        for category in categories
    ]

    if form.validate_on_submit():

        expense_date = company_date_to_utc(
            form.expense_date.data
        )

        expense = Expense(
            company_id=current_user.company_id,

            category_id=form.category_id.data,

            expense_number=generate_expense_number(),

            description=form.description.data.strip(),

            amount=form.amount.data,

            payment_method=form.payment_method.data,

            expense_date=expense_date,

            reference=(
                form.reference.data.strip()
                if form.reference.data
                else None
            ),

            notes=(
                form.notes.data.strip()
                if form.notes.data
                else None
            ),

            created_by=current_user.id
        )

        db.session.add(
            expense
        )

        # -------------------------------------------------
        # COMMIT EXPENSE
        # -------------------------------------------------

        try:

            db.session.commit()

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                "EXPENSE SAVE ERROR: %s",
                exc
            )

            flash(
                "Unable to save the expense. "
                "Please try again.",
                "danger"
            )

            return render_template(
                "expenses/expense_form.html",
                form=form,
                expense=None
            )

        # =================================================
        # NOTIFICATIONS
        # =================================================

        try:

            # ------------------------------------------------
            # EXPENSE SUCCESS NOTIFICATION
            # ------------------------------------------------
            #
            # DELIVERY CATEGORY:
            #     expense
            #
            # SOUND:
            #     success
            #
            # notify_success() automatically sets the sound
            # to "success".
            #
            # NotificationAssignment controls who receives
            # this notification.
            #
            # User sound preferences only control whether
            # the success sound plays.
            # ------------------------------------------------

            notify_success(
                company_id=current_user.company_id,

                title="Expense Recorded",

                message=(
                    f"Expense "
                    f"{expense.expense_number} "
                    f"was recorded successfully "
                    f"for "
                    f"{format_currency(expense.amount)}."
                ),

                notification_category="expense",

                user_id=current_user.id,

                link=url_for(
                    "expenses.view_expense",
                    expense_id=expense.id
                ),

                reference_type="Expense",

                reference_id=expense.id
            )

            # ------------------------------------------------
            # FINANCIAL ALERTS
            # ------------------------------------------------

            run_expense_financial_alerts(
                expense=expense,
                user_id=current_user.id
            )

        except Exception as notification_error:

            current_app.logger.exception(
                "Notification processing failed "
                "after expense %s: %s",
                expense.expense_number,
                notification_error
            )

        flash(
            "Expense recorded successfully.",
            "success"
        )

        return redirect(
            url_for(
                "expenses.view_expense",
                expense_id=expense.id
            )
        )

    return render_template(
        "expenses/expense_form.html",
        form=form,
        expense=None
    )


# =========================================================
# VIEW EXPENSE
# =========================================================

@expenses_bp.route(
    "/<int:expense_id>"
)
@login_required
@company_permission_required("view_expenses")
def view_expense(
    expense_id
):

    expense = (
        Expense.query
        .filter(
            Expense.id == expense_id,

            Expense.company_id ==
            current_user.company_id
        )
        .first_or_404()
    )

    return render_template(
        "expenses/expense_view.html",
        expense=expense
    )


# =========================================================
# EDIT EXPENSE
# =========================================================

@expenses_bp.route(
    "/<int:expense_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_expenses")
def edit_expense(
    expense_id
):

    expense = (
        Expense.query
        .filter(
            Expense.id == expense_id,

            Expense.company_id ==
            current_user.company_id
        )
        .first_or_404()
    )

    form = ExpenseForm()

    categories = (
        ExpenseCategory.query
        .filter(
            ExpenseCategory.company_id ==
            current_user.company_id
        )
        .order_by(
            ExpenseCategory.name.asc()
        )
        .all()
    )

    form.category_id.choices = [
        (
            category.id,
            category.name
        )
        for category in categories
    ]

    # =====================================================
    # GET
    # =====================================================

    if request.method == "GET":

        form.category_id.data = (
            expense.category_id
        )

        form.description.data = (
            expense.description
        )

        form.amount.data = (
            expense.amount
        )

        form.payment_method.data = (
            expense.payment_method
        )

        # Convert stored UTC timestamp back to the
        # company's local calendar date.

        if expense.expense_date:

            local_expense_date = (
                ensure_utc(
                    expense.expense_date
                )
                .astimezone(
                    get_company_timezone()
                )
            )

            form.expense_date.data = (
                local_expense_date.date()
            )

        form.reference.data = (
            expense.reference
        )

        form.notes.data = (
            expense.notes
        )

    # =====================================================
    # POST
    # =====================================================

    if form.validate_on_submit():

        # -------------------------------------------------
        # SAVE ORIGINAL DATE
        # -------------------------------------------------

        original_expense_date = (
            expense.expense_date
        )

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        expense.category_id = (
            form.category_id.data
        )

        expense.description = (
            form.description.data.strip()
        )

        expense.amount = (
            form.amount.data
        )

        expense.payment_method = (
            form.payment_method.data
        )

        expense.expense_date = (
            company_date_to_utc(
                form.expense_date.data
            )
        )

        expense.reference = (
            form.reference.data.strip()
            if form.reference.data
            else None
        )

        expense.notes = (
            form.notes.data.strip()
            if form.notes.data
            else None
        )

        # -------------------------------------------------
        # COMMIT
        # -------------------------------------------------

        try:

            db.session.commit()

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                "EXPENSE EDIT ERROR: %s",
                exc
            )

            flash(
                "Unable to update the expense. "
                "Please try again.",
                "danger"
            )

            return render_template(
                "expenses/expense_form.html",
                form=form,
                expense=expense
            )

        # =================================================
        # NOTIFICATIONS
        # =================================================

        try:

            # ------------------------------------------------
            # EXPENSE UPDATE NOTIFICATION
            # ------------------------------------------------

            notify_success(
                company_id=current_user.company_id,

                title="Expense Updated",

                message=(
                    f"Expense "
                    f"{expense.expense_number} "
                    "was updated successfully."
                ),

                notification_category="expense",

                user_id=current_user.id,

                link=url_for(
                    "expenses.view_expense",
                    expense_id=expense.id
                ),

                reference_type="Expense",

                reference_id=expense.id
            )

            # ------------------------------------------------
            # CHECK NEW EXPENSE DATE
            # ------------------------------------------------

            run_expense_financial_alerts(
                expense=expense,
                user_id=current_user.id
            )

            # ------------------------------------------------
            # IF DATE CHANGED, ALSO CHECK ORIGINAL DATE
            # ------------------------------------------------

            if (
                original_expense_date
                and expense.expense_date
                and
                ensure_utc(
                    original_expense_date
                ).astimezone(
                    get_company_timezone()
                ).date()
                !=
                ensure_utc(
                    expense.expense_date
                ).astimezone(
                    get_company_timezone()
                ).date()
            ):

                original_financial_date = (
                    ensure_utc(
                        original_expense_date
                    )
                    .astimezone(
                        get_company_timezone()
                    )
                    .date()
                )

                (
                    original_start_datetime,
                    original_end_datetime
                ) = company_day_boundaries(
                    original_financial_date
                )

                check_financial_alerts(
                    company_id=current_user.company_id,

                    start_datetime=(
                        original_start_datetime
                    ),

                    end_datetime=(
                        original_end_datetime
                    ),

                    user_id=current_user.id
                )

        except Exception as notification_error:

            current_app.logger.exception(
                "Notification processing failed "
                "after expense update %s: %s",
                expense.expense_number,
                notification_error
            )

        flash(
            "Expense updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "expenses.view_expense",
                expense_id=expense.id
            )
        )

    return render_template(
        "expenses/expense_form.html",
        form=form,
        expense=expense
    )


# =========================================================
# DELETE EXPENSE
# =========================================================

@expenses_bp.route(
    "/<int:expense_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_expenses")
def delete_expense(
    expense_id
):

    expense = (
        Expense.query
        .filter(
            Expense.id == expense_id,

            Expense.company_id ==
            current_user.company_id
        )
        .first_or_404()
    )

    # -----------------------------------------------------
    # SAVE VALUES BEFORE DELETE
    # -----------------------------------------------------

    expense_number = (
        expense.expense_number
    )

    expense_date = (
        expense.expense_date
    )

    expense_amount = Decimal(
        str(
            expense.amount or 0
        )
    )

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    db.session.delete(
        expense
    )

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "EXPENSE DELETE ERROR: %s",
            exc
        )

        flash(
            "Unable to delete the expense. "
            "Please try again.",
            "danger"
        )

        return redirect(
            url_for(
                "expenses.view_expense",
                expense_id=expense_id
            )
        )

    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    try:

        # ------------------------------------------------
        # EXPENSE DELETE NOTIFICATION
        # ------------------------------------------------
        #
        # Delivery category = expense
        # Sound = success
        #
        # The notification assignment determines who
        # receives this notification.
        # ------------------------------------------------

        notify_success(
            company_id=current_user.company_id,

            title="Expense Deleted",

            message=(
                f"Expense "
                f"{expense_number} "
                f"was deleted successfully. "

                f"{format_currency(expense_amount)} "
                "was removed from expenses."
            ),

            notification_category="expense",

            user_id=current_user.id,

            link=url_for(
                "expenses.expenses"
            ),

            reference_type="Expense",

            reference_id=expense_id
        )

        # ------------------------------------------------
        # FINANCIAL ALERTS
        # ------------------------------------------------

        if expense_date:

            expense_local_date = (
                ensure_utc(
                    expense_date
                )
                .astimezone(
                    get_company_timezone()
                )
                .date()
            )

            (
                start_datetime,
                end_datetime
            ) = company_day_boundaries(
                expense_local_date
            )

            check_financial_alerts(
                company_id=current_user.company_id,

                start_datetime=start_datetime,

                end_datetime=end_datetime,

                user_id=current_user.id
            )

    except Exception as notification_error:

        current_app.logger.exception(
            "Notification processing failed "
            "after expense deletion %s: %s",
            expense_number,
            notification_error
        )

    flash(
        "Expense deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "expenses.expenses"
        )
    )


# =========================================================
# EXPENSE CATEGORIES
# =========================================================

@expenses_bp.route(
    "/categories",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_expenses")
def categories():

    form = ExpenseCategoryForm()

    if form.validate_on_submit():

        category = ExpenseCategory(
            company_id=current_user.company_id,

            name=form.name.data.strip(),

            description=(
                form.description.data.strip()
                if form.description.data
                else None
            )
        )

        db.session.add(
            category
        )

        try:

            db.session.commit()

            flash(
                "Expense category created successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "expenses.categories"
                )
            )

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                "EXPENSE CATEGORY CREATE ERROR: %s",
                exc
            )

            flash(
                "Unable to create the expense category.",
                "danger"
            )

    categories = (
        ExpenseCategory.query
        .filter_by(
            company_id=current_user.company_id
        )
        .order_by(
            ExpenseCategory.name.asc()
        )
        .all()
    )

    return render_template(
        "expenses/expense_categories.html",
        form=form,
        categories=categories
    )


# =========================================================
# DELETE EXPENSE CATEGORY
# =========================================================

@expenses_bp.route(
    "/categories/<int:category_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_expenses")
def delete_category(
    category_id
):

    category = (
        ExpenseCategory.query
        .filter(
            ExpenseCategory.id == category_id,

            ExpenseCategory.company_id ==
            current_user.company_id
        )
        .first_or_404()
    )

    if category.expenses:

        flash(
            "This category cannot be deleted because "
            "it is already used by an expense.",
            "warning"
        )

        return redirect(
            url_for(
                "expenses.categories"
            )
        )

    db.session.delete(
        category
    )

    try:

        db.session.commit()

        flash(
            "Expense category deleted successfully.",
            "success"
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "EXPENSE CATEGORY DELETE ERROR: %s",
            exc
        )

        flash(
            "Unable to delete the expense category.",
            "danger"
        )

    return redirect(
        url_for(
            "expenses.categories"
        )
    )