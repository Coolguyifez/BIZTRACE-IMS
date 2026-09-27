from datetime import datetime, timezone, timedelta
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app
)

from flask_login import login_required, current_user

from sqlalchemy import or_

from app.company_admin.decorators import company_permission_required

from app.notifications.service import notify_success

from app.utils.company_settings import (
    format_currency,
    get_company_timezone,
)

from ..extensions import db

from ..models import (
    Payment,
    Sale,
    Customer,
    Expense,
    CashDeposit
)


payments_bp = Blueprint(
    "payments",
    __name__,
    url_prefix="/payments"
)


# =========================================================
# DATETIME HELPERS
# =========================================================

def now_utc():
    """
    Return the current timezone-aware UTC datetime.

    Database timestamps should remain UTC.
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

    SQLite may return naive datetime values even when the
    application originally stored UTC timestamps.
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


def company_day_boundaries():
    """
    Return today's start and end as UTC-aware datetimes,
    based on the current company's configured timezone.
    """

    company_tz = get_company_timezone()

    current_company = datetime.now(
        company_tz
    )

    start_company = current_company.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    end_company = (
        start_company +
        timedelta(days=1)
    )

    start_utc = start_company.astimezone(
        timezone.utc
    )

    end_utc = end_company.astimezone(
        timezone.utc
    )

    return start_utc, end_utc


def company_month_boundaries(year, month):
    """
    Return the beginning and end of a company-local
    calendar month converted to UTC.
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
    Return the beginning and end of a company-local
    calendar year converted to UTC.
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

    Week starts on Sunday to preserve the existing behavior.
    """

    company_tz = get_company_timezone()

    current_company = datetime.now(
        company_tz
    )

    # Python:
    # Monday = 0
    # Sunday = 6
    #
    # Existing application behavior:
    # Sunday = first day of week.

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
# PAYMENTS
# =========================================================

@payments_bp.route("/")
@login_required
@company_permission_required("view_payments")
def payments():

    company_id = current_user.company_id

    # -----------------------------------------------------
    # PAYMENT QUERY
    # -----------------------------------------------------

    query = (
        Payment.query
        .join(
            Sale,
            Payment.sale_id == Sale.id
        )
        .outerjoin(
            Customer,
            Sale.customer_id == Customer.id
        )
        .filter(
            Payment.company_id == company_id,
            Payment.sale_id.isnot(None)
        )
    )

    search = request.args.get(
        "q",
        ""
    ).strip()

    if search:

        query = query.filter(
            or_(
                Payment.reference.ilike(
                    f"%{search}%"
                ),
                Payment.method.ilike(
                    f"%{search}%"
                ),
                Sale.invoice_number.ilike(
                    f"%{search}%"
                ),
                Customer.name.ilike(
                    f"%{search}%"
                )
            )
        )

    # -----------------------------------------------------
    # PERIOD
    # -----------------------------------------------------

    period = request.args.get(
        "period",
        "all"
    )

    current_company = now_company()

    month = request.args.get(
        "month",
        current_company.month,
        type=int
    )

    year = request.args.get(
        "year",
        current_company.year,
        type=int
    )

    # -----------------------------------------------------
    # PERIOD DATES
    # -----------------------------------------------------

    period_start = None
    period_end = None

    if period == "daily":

        period_start, period_end = (
            company_day_boundaries()
        )

    elif period == "weekly":

        period_start, period_end = (
            company_week_boundaries()
        )

    elif period == "monthly":

        if not 1 <= month <= 12:
            month = current_company.month

        if not 2000 <= year <= 2100:
            year = current_company.year

        period_start, period_end = (
            company_month_boundaries(
                year,
                month
            )
        )

    elif period == "yearly":

        if not 2000 <= year <= 2100:
            year = current_company.year

        period_start, period_end = (
            company_year_boundaries(
                year
            )
        )

    # -----------------------------------------------------
    # APPLY PAYMENT PERIOD
    # -----------------------------------------------------

    if period_start and period_end:

        query = query.filter(
            Payment.payment_date >= period_start,
            Payment.payment_date < period_end
        )

    # -----------------------------------------------------
    # PAYMENT RESULTS
    # -----------------------------------------------------

    payments = (
        query
        .order_by(
            Payment.payment_date.desc(),
            Payment.id.desc()
        )
        .all()
    )

    # -----------------------------------------------------
    # PAYMENT TOTALS
    # -----------------------------------------------------

    total_amount = sum(
        (
            payment.amount or 0
            for payment in payments
        ),
        Decimal("0")
    )

    cash_total = sum(
        (
            payment.amount or 0
            for payment in payments
            if payment.method == "Cash"
        ),
        Decimal("0")
    )

    bank_transfer_total = sum(
        (
            payment.amount or 0
            for payment in payments
            if payment.method == "Bank Transfer"
        ),
        Decimal("0")
    )

    pos_total = sum(
        (
            payment.amount or 0
            for payment in payments
            if payment.method == "POS"
        ),
        Decimal("0")
    )

    card_total = sum(
        (
            payment.amount or 0
            for payment in payments
            if payment.method == "Card"
        ),
        Decimal("0")
    )

    # =====================================================
    # TODAY'S PAYMENTS
    # =====================================================

    today_start, today_end = (
        company_day_boundaries()
    )

    today_total = sum(
        (
            payment.amount or 0
            for payment in payments
            if (
                payment.payment_date
                and
                ensure_utc(
                    payment.payment_date
                ) >= today_start
                and
                ensure_utc(
                    payment.payment_date
                ) < today_end
            )
        ),
        Decimal("0")
    )

    # =====================================================
    # EXPENSES
    # =====================================================

    expense_query = (
        Expense.query
        .filter(
            Expense.company_id == company_id
        )
    )

    if period_start and period_end:

        expense_query = expense_query.filter(
            Expense.expense_date >= period_start,
            Expense.expense_date < period_end
        )

    expenses = (
        expense_query
        .all()
    )

    total_expenses = sum(
        (
            expense.amount or 0
            for expense in expenses
        ),
        Decimal("0")
    )

    # -----------------------------------------------------
    # CASH EXPENSES
    # -----------------------------------------------------

    cash_expenses = sum(
        (
            expense.amount or 0
            for expense in expenses
            if (
                expense.payment_method
                and
                expense.payment_method.strip().lower()
                == "cash"
            )
        ),
        Decimal("0")
    )

    # -----------------------------------------------------
    # TODAY'S EXPENSES
    # -----------------------------------------------------

    today_expense_query = (
        Expense.query
        .filter(
            Expense.company_id == company_id,
            Expense.expense_date >= today_start,
            Expense.expense_date < today_end
        )
    )

    today_expenses_list = (
        today_expense_query
        .all()
    )

    today_expenses = sum(
        (
            expense.amount or 0
            for expense in today_expenses_list
        ),
        Decimal("0")
    )

    # -----------------------------------------------------
    # TODAY'S CASH EXPENSES
    # -----------------------------------------------------

    today_cash_expenses = sum(
        (
            expense.amount or 0
            for expense in today_expenses_list
            if (
                expense.payment_method
                and
                expense.payment_method.strip().lower()
                == "cash"
            )
        ),
        Decimal("0")
    )

    # -----------------------------------------------------
    # NET PAYMENTS
    # -----------------------------------------------------

    net_payments = (
        total_amount -
        total_expenses
    )

    # -----------------------------------------------------
    # CASH NET
    # -----------------------------------------------------

    cash_net = (
        cash_total -
        cash_expenses
    )

    # -----------------------------------------------------
    # YEARS
    # -----------------------------------------------------

    years = range(
        current_company.year - 5,
        current_company.year + 1
    )

    # -----------------------------------------------------
    # TEMPLATE
    # -----------------------------------------------------

    return render_template(
        "payments/payments.html",

        payments=payments,

        total_amount=total_amount,
        today_total=today_total,

        cash_total=cash_total,
        bank_transfer_total=bank_transfer_total,
        pos_total=pos_total,
        card_total=card_total,

        total_expenses=total_expenses,
        today_expenses=today_expenses,

        cash_expenses=cash_expenses,
        today_cash_expenses=today_cash_expenses,

        cash_net=cash_net,

        net_payments=net_payments,

        search=search,
        period=period,
        month=month,
        year=year,
        years=years
    )


# =========================================================
# CASH DEPOSIT
# =========================================================

@payments_bp.route(
    "/cash-deposits",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("view_cash_deposits")
def cash_deposits():

    company_id = current_user.company_id

    # =====================================================
    # POST — CREATE CASH DEPOSIT
    # =====================================================

    if request.method == "POST":

        # -------------------------------------------------
        # AMOUNT
        # -------------------------------------------------

        amount_raw = request.form.get(
            "amount",
            ""
        ).strip()

        # -------------------------------------------------
        # BANK
        # -------------------------------------------------

        bank_name = request.form.get(
            "bank_name",
            ""
        ).strip()

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        deposit_date_raw = request.form.get(
            "deposit_date",
            ""
        ).strip()

        # -------------------------------------------------
        # REFERENCE
        # -------------------------------------------------

        reference = request.form.get(
            "reference",
            ""
        ).strip()

        # -------------------------------------------------
        # NOTES
        # -------------------------------------------------

        notes = request.form.get(
            "notes",
            ""
        ).strip()

        # =================================================
        # VALIDATE AMOUNT
        # =================================================

        try:

            amount = Decimal(
                amount_raw
            )

        except Exception:

            flash(
                "Enter a valid deposit amount.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.cash_deposits"
                )
            )

        if amount <= 0:

            flash(
                "Deposit amount must be greater than zero.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.cash_deposits"
                )
            )

        # =================================================
        # VALIDATE BANK
        # =================================================

        if not bank_name:

            flash(
                "Please enter the bank name.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.cash_deposits"
                )
            )

        # =================================================
        # DEPOSIT DATE
        # =================================================

        if deposit_date_raw:

            try:

                local_date = datetime.strptime(
                    deposit_date_raw,
                    "%Y-%m-%d"
                )

                company_tz = get_company_timezone()

                deposit_date_company = (
                    local_date.replace(
                        tzinfo=company_tz
                    )
                )

                deposit_date = (
                    deposit_date_company.astimezone(
                        timezone.utc
                    )
                )

            except ValueError:

                flash(
                    "Invalid deposit date.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "payments.cash_deposits"
                    )
                )

        else:

            deposit_date = now_utc()

        # =================================================
        # CALCULATE TOTAL CASH RECEIVED
        # =================================================

        total_cash_received = (
            db.session.query(
                db.func.coalesce(
                    db.func.sum(
                        Payment.amount
                    ),
                    0
                )
            )
            .filter(
                Payment.company_id == company_id,
                Payment.sale_id.isnot(None),
                Payment.method == "Cash"
            )
            .scalar()
            or Decimal("0")
        )

        total_cash_received = Decimal(
            str(total_cash_received)
        )

        # =================================================
        # CALCULATE TOTAL CASH EXPENSES
        # =================================================
        #
        # IMPORTANT:
        #
        # Only expenses paid using Cash reduce the physical
        # cash available for deposit.
        #
        # Bank Transfer, POS, Card, etc. do NOT reduce it.
        # =================================================

        total_cash_expenses = (
            db.session.query(
                db.func.coalesce(
                    db.func.sum(
                        Expense.amount
                    ),
                    0
                )
            )
            .filter(
                Expense.company_id == company_id,
                db.func.lower(
                    Expense.payment_method
                ) == "cash"
            )
            .scalar()
            or Decimal("0")
        )

        total_cash_expenses = Decimal(
            str(total_cash_expenses)
        )

        # =================================================
        # CALCULATE TOTAL CASH DEPOSITED
        # =================================================

        total_cash_deposited = (
            db.session.query(
                db.func.coalesce(
                    db.func.sum(
                        CashDeposit.amount
                    ),
                    0
                )
            )
            .filter(
                CashDeposit.company_id == company_id
            )
            .scalar()
            or Decimal("0")
        )

        total_cash_deposited = Decimal(
            str(total_cash_deposited)
        )

        # =================================================
        # CASH AVAILABLE
        # =================================================
        #
        # Cash Collected
        #       -
        # Cash Expenses
        #       -
        # Cash Already Deposited
        #
        #       =
        #
        # Cash Available
        # =================================================

        cash_available = (
            total_cash_received
            - total_cash_expenses
            - total_cash_deposited
        )

        # -------------------------------------------------
        # NEVER SHOW NEGATIVE AVAILABLE CASH
        # -------------------------------------------------

        if cash_available < Decimal("0"):

            cash_available = Decimal("0")

        # =================================================
        # PREVENT OVER-DEPOSIT
        # =================================================

        if amount > cash_available:

            flash(
                "Deposit amount cannot exceed "
                f"available cash of "
                f"{format_currency(cash_available)} "
                f"after cash expenses.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.cash_deposits"
                )
            )

        # =================================================
        # CREATE DEPOSIT
        # =================================================

        deposit = CashDeposit(
            company_id=company_id,
            amount=amount,
            bank_name=bank_name,
            deposit_date=deposit_date,
            reference=reference or None,
            notes=notes or None,
            created_by=current_user.id
        )

        db.session.add(
            deposit
        )

        # =================================================
        # COMMIT
        # =================================================

        try:

            db.session.commit()

        except Exception as error:

            db.session.rollback()

            current_app.logger.exception(
                "Cash deposit creation failed: %s",
                error
            )

            flash(
                "The cash deposit could not be recorded.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.cash_deposits"
                )
            )

        # =================================================
        # NOTIFICATION
        # =================================================

        try:

            notify_success(
                company_id=company_id,

                title="Cash Deposit Recorded",

                message=(
                    f"Cash deposit of "
                    f"{format_currency(amount)} "
                    f"was recorded successfully "
                    f"to {bank_name}."
                ),

                notification_category="cash_deposit",

                user_id=current_user.id,

                link=url_for(
                    "payments.cash_deposits"
                ),

                reference_type="CashDeposit",

                reference_id=deposit.id
            )

        except Exception as notification_error:

            current_app.logger.exception(
                "Cash deposit notification failed "
                "for deposit %s: %s",
                deposit.id,
                notification_error
            )

        # =================================================
        # FLASH
        # =================================================

        flash(
            "Cash deposit recorded successfully.",
            "success"
        )

        return redirect(
            url_for(
                "payments.cash_deposits"
            )
        )

    # =====================================================
    # GET
    # =====================================================

    deposits = (
        CashDeposit.query
        .filter(
            CashDeposit.company_id == company_id
        )
        .order_by(
            CashDeposit.deposit_date.desc(),
            CashDeposit.id.desc()
        )
        .all()
    )

    # =====================================================
    # TOTAL CASH RECEIVED
    # =====================================================

    total_cash_received = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(
                    Payment.amount
                ),
                0
            )
        )
        .filter(
            Payment.company_id == company_id,
            Payment.sale_id.isnot(None),
            Payment.method == "Cash"
        )
        .scalar()
        or Decimal("0")
    )

    total_cash_received = Decimal(
        str(total_cash_received)
    )

    # =====================================================
    # TOTAL CASH EXPENSES
    # =====================================================
    #
    # Only expenses paid in CASH are deducted.
    # =====================================================

    total_cash_expenses = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(
                    Expense.amount
                ),
                0
            )
        )
        .filter(
            Expense.company_id == company_id,
            db.func.lower(
                Expense.payment_method
            ) == "cash"
        )
        .scalar()
        or Decimal("0")
    )

    total_cash_expenses = Decimal(
        str(total_cash_expenses)
    )

    # =====================================================
    # TOTAL CASH DEPOSITED
    # =====================================================

    total_cash_deposited = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(
                    CashDeposit.amount
                ),
                0
            )
        )
        .filter(
            CashDeposit.company_id == company_id
        )
        .scalar()
        or Decimal("0")
    )

    total_cash_deposited = Decimal(
        str(total_cash_deposited)
    )

    # =====================================================
    # CASH AVAILABLE
    # =====================================================
    #
    # Cash Collected
    #       -
    # Cash Expenses
    #       -
    # Cash Deposited
    #
    #       =
    #
    # Cash Available
    # =====================================================

    cash_available = (
        total_cash_received
        - total_cash_expenses
        - total_cash_deposited
    )

    if cash_available < Decimal("0"):

        cash_available = Decimal("0")

    # =====================================================
    # TEMPLATE
    # =====================================================

    return render_template(
        "payments/cash_deposits.html",

        deposits=deposits,

        total_cash_received=
        total_cash_received,

        total_cash_expenses=
        total_cash_expenses,

        total_cash_deposited=
        total_cash_deposited,

        cash_available=
        cash_available,

        today=now_company().date()
    )


# =========================================================
# DELETE CASH DEPOSIT
# =========================================================

@payments_bp.route(
    "/cash-deposits/<int:deposit_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_cash_deposits")
def delete_cash_deposit(deposit_id):

    deposit = (
        CashDeposit.query
        .filter(
            CashDeposit.id == deposit_id,
            CashDeposit.company_id ==
            current_user.company_id
        )
        .first_or_404()
    )

    # -----------------------------------------------------
    # SAVE VALUES BEFORE DELETE
    # -----------------------------------------------------

    deposit_id_value = deposit.id

    deposit_amount = Decimal(
        str(
            deposit.amount or 0
        )
    )

    bank_name = deposit.bank_name

    # =====================================================
    # DELETE
    # =====================================================

    try:

        db.session.delete(
            deposit
        )

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        current_app.logger.exception(
            "Cash deposit deletion failed "
            "for deposit %s: %s",
            deposit_id_value,
            error
        )

        flash(
            "Unable to delete the cash deposit.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "payments.cash_deposits"
            )
        )

    # =====================================================
    # NOTIFICATION
    # =====================================================

    try:

        notify_success(
            company_id=current_user.company_id,

            title="Cash Deposit Deleted",

            message=(
                f"Cash deposit of "
                f"{format_currency(deposit_amount)} "
                f"from {bank_name} "
                f"was deleted successfully."
            ),

            notification_category="cash_deposit",

            user_id=current_user.id,

            link=url_for(
                "payments.cash_deposits"
            ),

            reference_type="CashDeposit",

            reference_id=deposit_id_value
        )

    except Exception as notification_error:

        current_app.logger.exception(
            "Cash deposit deletion notification failed "
            "for deposit %s: %s",
            deposit_id_value,
            notification_error
        )

    # =====================================================
    # FLASH
    # =====================================================

    flash(
        "Cash deposit deleted successfully.",
        "success"
    )

    return redirect(
        request.referrer
        or url_for(
            "payments.cash_deposits"
        )
    )
