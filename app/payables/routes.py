from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    request
)

from flask_login import (
    login_required,
    current_user
)

from app.company_admin.decorators import (
    company_permission_required
)

from app.utils.company_settings import (
    get_company_timezone
)

from sqlalchemy import or_

from ..models import (
    Purchase,
    Supplier
)


payables_bp = Blueprint(
    "payables",
    __name__,
    url_prefix="/payables"
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


def company_week_boundaries():
    """
    Return the start and end of the current company-local
    week.

    Sunday is treated as the first day of the week.
    """

    current_company = now_company()

    days_since_sunday = (
        current_company.weekday() + 1
    ) % 7

    today_start = current_company.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    week_start = (
        today_start -
        timedelta(
            days=days_since_sunday
        )
    )

    week_end = (
        week_start +
        timedelta(days=7)
    )

    return week_start, week_end


# =========================================================
# PAYABLES
# =========================================================

@payables_bp.route("/")
@login_required
@company_permission_required("view_payables")
def payables():

    company_id = current_user.company_id

    # =====================================================
    # PURCHASE QUERY
    # =====================================================

    query = (
        Purchase.query
        .outerjoin(
            Supplier,
            Purchase.supplier_id == Supplier.id
        )
        .filter(
            Purchase.company_id == company_id,
            Purchase.balance > 0
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
                Purchase.purchase_number.ilike(
                    f"%{search}%"
                ),
                Supplier.name.ilike(
                    f"%{search}%"
                ),
                Supplier.phone.ilike(
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

    period_start = None
    period_end = None

    # =====================================================
    # DAILY
    # =====================================================

    if period == "daily":

        period_start = current_company.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        period_end = (
            period_start +
            timedelta(days=1)
        )

    # =====================================================
    # WEEKLY
    # =====================================================

    elif period == "weekly":

        (
            period_start,
            period_end
        ) = company_week_boundaries()

    # =====================================================
    # MONTHLY
    # =====================================================

    elif period == "monthly":

        if not 1 <= month <= 12:
            month = current_company.month

        if not 2000 <= year <= 2100:
            year = current_company.year

        period_start = datetime(
            year,
            month,
            1,
            tzinfo=get_company_timezone()
        )

        if month == 12:

            period_end = datetime(
                year + 1,
                1,
                1,
                tzinfo=get_company_timezone()
            )

        else:

            period_end = datetime(
                year,
                month + 1,
                1,
                tzinfo=get_company_timezone()
            )

    # =====================================================
    # YEARLY
    # =====================================================

    elif period == "yearly":

        if not 2000 <= year <= 2100:
            year = current_company.year

        period_start = datetime(
            year,
            1,
            1,
            tzinfo=get_company_timezone()
        )

        period_end = datetime(
            year + 1,
            1,
            1,
            tzinfo=get_company_timezone()
        )

    # =====================================================
    # APPLY PERIOD
    # =====================================================

    if period_start and period_end:

        query = query.filter(
            Purchase.purchase_date >= period_start,
            Purchase.purchase_date < period_end
        )

    # =====================================================
    # PURCHASES
    # =====================================================

    purchases = (
        query
        .order_by(
            Purchase.purchase_date.desc(),
            Purchase.id.desc()
        )
        .all()
    )

    # =====================================================
    # TOTAL PAYABLES
    # =====================================================

    total_payables = sum(
        (
            purchase.balance or 0
            for purchase in purchases
        ),
        0
    )

    # =====================================================
    # TOTAL PURCHASE VALUE
    # =====================================================

    total_purchase_value = sum(
        (
            purchase.total or 0
            for purchase in purchases
        ),
        0
    )

    # =====================================================
    # TOTAL PAID
    # =====================================================

    total_paid = sum(
        (
            purchase.paid_amount or 0
            for purchase in purchases
        ),
        0
    )

    # =====================================================
    # UNPAID
    # =====================================================

    unpaid_total = sum(
        (
            purchase.balance or 0
            for purchase in purchases
            if purchase.payment_status == "Unpaid"
        ),
        0
    )

    # =====================================================
    # PARTIALLY PAID
    # =====================================================

    partial_total = sum(
        (
            purchase.balance or 0
            for purchase in purchases
            if purchase.payment_status == "Partially Paid"
        ),
        0
    )

    # =====================================================
    # YEARS
    # =====================================================

    years = range(
        current_company.year - 5,
        current_company.year + 1
    )

    # =====================================================
    # TEMPLATE
    # =====================================================

    return render_template(
        "payables/payables.html",

        purchases=purchases,

        total_payables=total_payables,

        total_purchase_value=
        total_purchase_value,

        total_paid=total_paid,

        unpaid_total=unpaid_total,

        partial_total=partial_total,

        search=search,

        period=period,

        month=month,

        year=year,

        years=years
    )