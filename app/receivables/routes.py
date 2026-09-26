from datetime import datetime, timezone, timedelta
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    request
)

from flask_login import (
    login_required,
    current_user
)

from sqlalchemy import or_

from app.company_admin.decorators import (
    company_permission_required
)

from app.utils.company_settings import (
    get_company_timezone
)

from ..models import (
    Sale,
    Customer
)


receivables_bp = Blueprint(
    "receivables",
    __name__,
    url_prefix="/receivables"
)


# =========================================================
# DATETIME HELPERS
# =========================================================

def now_company():
    """
    Return the current datetime using the current company's
    configured timezone.
    """
    return datetime.now(
        get_company_timezone()
    )


def company_day_boundaries():
    """
    Return today's beginning and end as UTC-aware datetimes.

    The calendar day is determined using the company's
    configured timezone.
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
    Return the beginning and end of the current week.

    The application uses Sunday as the first day of the week.
    """

    company_tz = get_company_timezone()

    current_company = datetime.now(
        company_tz
    )

    # Python:
    # Monday = 0
    # Sunday = 6
    #
    # Convert to Sunday-based week.
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


# =========================================================
# RECEIVABLES
# =========================================================

@receivables_bp.route("/")
@login_required
@company_permission_required("view_receivables")
def receivables():

    company_id = current_user.company_id

    # =====================================================
    # BASE QUERY
    # =====================================================

    query = (
        Sale.query
        .outerjoin(
            Customer,
            Sale.customer_id == Customer.id
        )
        .filter(
            Sale.company_id == company_id,
            Sale.balance > 0
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search = request.args.get(
        "q",
        ""
    ).strip()

    if search:

        query = query.filter(
            or_(
                Sale.invoice_number.ilike(
                    f"%{search}%"
                ),
                Customer.name.ilike(
                    f"%{search}%"
                ),
                Customer.phone.ilike(
                    f"%{search}%"
                )
            )
        )

    # =====================================================
    # PERIOD
    # =====================================================

    period = request.args.get(
        "period",
        "all"
    )

    now = now_company()

    month = request.args.get(
        "month",
        now.month,
        type=int
    )

    year = request.args.get(
        "year",
        now.year,
        type=int
    )

    period_start = None
    period_end = None

    # =====================================================
    # DAILY
    # =====================================================

    if period == "daily":

        period_start, period_end = (
            company_day_boundaries()
        )

    # =====================================================
    # WEEKLY
    # =====================================================

    elif period == "weekly":

        period_start, period_end = (
            company_week_boundaries()
        )

    # =====================================================
    # MONTHLY
    # =====================================================

    elif period == "monthly":

        if not 1 <= month <= 12:
            month = now.month

        if not 2000 <= year <= 2100:
            year = now.year

        period_start, period_end = (
            company_month_boundaries(
                year,
                month
            )
        )

    # =====================================================
    # YEARLY
    # =====================================================

    elif period == "yearly":

        if not 2000 <= year <= 2100:
            year = now.year

        period_start, period_end = (
            company_year_boundaries(
                year
            )
        )

    # =====================================================
    # APPLY PERIOD
    # =====================================================

    if period_start and period_end:

        query = query.filter(
            Sale.sale_date >= period_start,
            Sale.sale_date < period_end
        )

    # =====================================================
    # SALES
    # =====================================================

    sales = (
        query
        .order_by(
            Sale.sale_date.desc(),
            Sale.id.desc()
        )
        .all()
    )

    # =====================================================
    # TOTAL RECEIVABLES
    # =====================================================

    total_receivables = sum(
        (
            sale.balance or 0
            for sale in sales
        ),
        Decimal("0")
    )

    # =====================================================
    # TOTAL INVOICE VALUE
    # =====================================================

    total_invoice_value = sum(
        (
            sale.total or 0
            for sale in sales
        ),
        Decimal("0")
    )

    # =====================================================
    # TOTAL PAID
    # =====================================================

    total_paid = sum(
        (
            sale.paid_amount or 0
            for sale in sales
        ),
        Decimal("0")
    )

    # =====================================================
    # UNPAID
    # =====================================================

    unpaid_total = sum(
        (
            sale.balance or 0
            for sale in sales
            if sale.payment_status == "Unpaid"
        ),
        Decimal("0")
    )

    # =====================================================
    # PARTIALLY PAID
    # =====================================================

    partial_total = sum(
        (
            sale.balance or 0
            for sale in sales
            if sale.payment_status == "Partially Paid"
        ),
        Decimal("0")
    )

    # =====================================================
    # YEARS
    # =====================================================

    years = range(
        now.year - 5,
        now.year + 1
    )

    # =====================================================
    # TEMPLATE
    # =====================================================

    return render_template(
        "receivables/receivables.html",

        sales=sales,

        total_receivables=
        total_receivables,

        total_invoice_value=
        total_invoice_value,

        total_paid=
        total_paid,

        unpaid_total=
        unpaid_total,

        partial_total=
        partial_total,

        search=search,

        period=period,

        month=month,

        year=year,

        years=years
    )