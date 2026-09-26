from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from app.company_admin.decorators import company_permission_required
from app.extensions import db
from app.models import (
    Sale,
    Purchase,
    Expense,
    Payment,
    Product,
)
from app.utils.company_settings import (
    company_now,
    get_company_timezone,
)


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


# =============================================================
# DATE / TIME HELPERS
# =============================================================

def company_day_boundaries(target_date=None):
    """
    Return the start and end of a calendar day in the
    current company's timezone, converted to UTC for
    database comparisons.

    Database timestamps remain UTC.
    Dashboard calendar calculations follow the company's
    configured timezone.
    """

    company_timezone = get_company_timezone()

    if target_date is None:
        target_date = company_now().date()

    local_start = datetime.combine(
        target_date,
        datetime.min.time(),
        tzinfo=company_timezone
    )

    local_end = local_start + timedelta(days=1)

    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


def company_month_boundaries(year, month):
    """
    Return the start and end of a company-local month,
    converted to UTC.
    """

    company_timezone = get_company_timezone()

    local_start = datetime(
        year,
        month,
        1,
        tzinfo=company_timezone
    )

    if month == 12:
        local_end = datetime(
            year + 1,
            1,
            1,
            tzinfo=company_timezone
        )
    else:
        local_end = datetime(
            year,
            month + 1,
            1,
            tzinfo=company_timezone
        )

    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


def company_year_boundaries(year):
    """
    Return the start and end of a company-local year,
    converted to UTC.
    """

    company_timezone = get_company_timezone()

    local_start = datetime(
        year,
        1,
        1,
        tzinfo=company_timezone
    )

    local_end = datetime(
        year + 1,
        1,
        1,
        tzinfo=company_timezone
    )

    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


# =============================================================
# DASHBOARD
# =============================================================

@dashboard_bp.route("/dashboard")
@login_required
@company_permission_required("view_dashboard")
def dashboard():

    # =========================================================
    # COMPANY
    # =========================================================

    company_id = current_user.company_id

    # System Administrator does not belong to a company.
    if company_id is None:
        return render_template(
            "dashboard.html",
            user=current_user
        )

    # =========================================================
    # COMPANY DATE / TIME
    # =========================================================

    # Current date/time in the company's configured timezone.
    now_company = company_now()

    today = now_company.date()

    # Current company-local day converted to UTC.
    start_of_today, tomorrow = company_day_boundaries(today)

    # Current company-local month converted to UTC.
    start_of_month, start_of_next_month = company_month_boundaries(
        today.year,
        today.month
    )


    # =========================================================
    # SALES
    # =========================================================

    total_sales = (
        db.session.query(
            func.coalesce(
                func.sum(Sale.total),
                0
            )
        )
        .filter(
            Sale.company_id == company_id,
            Sale.sale_date >= start_of_month,
            Sale.sale_date < start_of_next_month
        )
        .scalar()
        or 0
    )

    today_sales = (
        db.session.query(
            func.coalesce(
                func.sum(Sale.total),
                0
            )
        )
        .filter(
            Sale.company_id == company_id,
            Sale.sale_date >= start_of_today,
            Sale.sale_date < tomorrow
        )
        .scalar()
        or 0
    )

    total_sales_count = (
        Sale.query
        .filter(
            Sale.company_id == company_id,
            Sale.sale_date >= start_of_month,
            Sale.sale_date < start_of_next_month
        )
        .count()
    )


    # =========================================================
    # PURCHASES
    # =========================================================

    total_purchases = (
        db.session.query(
            func.coalesce(
                func.sum(Purchase.total),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,
            Purchase.purchase_date >= start_of_month,
            Purchase.purchase_date < start_of_next_month
        )
        .scalar()
        or 0
    )

    today_purchases = (
        db.session.query(
            func.coalesce(
                func.sum(Purchase.total),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,
            Purchase.purchase_date >= start_of_today,
            Purchase.purchase_date < tomorrow
        )
        .scalar()
        or 0
    )


    # =========================================================
    # EXPENSES
    # =========================================================

    total_expenses = (
        db.session.query(
            func.coalesce(
                func.sum(Expense.amount),
                0
            )
        )
        .filter(
            Expense.company_id == company_id,
            Expense.expense_date >= start_of_month,
            Expense.expense_date < start_of_next_month
        )
        .scalar()
        or 0
    )

    today_expenses = (
        db.session.query(
            func.coalesce(
                func.sum(Expense.amount),
                0
            )
        )
        .filter(
            Expense.company_id == company_id,
            Expense.expense_date >= start_of_today,
            Expense.expense_date < tomorrow
        )
        .scalar()
        or 0
    )


    # =========================================================
    # RECEIVABLES
    # =========================================================

    receivables = (
        db.session.query(
            func.coalesce(
                func.sum(Sale.balance),
                0
            )
        )
        .filter(
            Sale.company_id == company_id,
            Sale.balance > 0
        )
        .scalar()
        or 0
    )


    # =========================================================
    # PAYABLES
    # =========================================================

    payables = (
        db.session.query(
            func.coalesce(
                func.sum(Purchase.balance),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,
            Purchase.balance > 0
        )
        .scalar()
        or 0
    )


    # =========================================================
    # INVENTORY
    # =========================================================

    products = (
        Product.query
        .filter(
            Product.company_id == company_id,
            Product.is_active.is_(True)
        )
        .all()
    )

    product_count = len(products)

    low_stock_products = [
        product
        for product in products
        if product.is_low_stock
    ]

    low_stock_count = len(low_stock_products)

    inventory_value = sum(
        (
            product.quantity or Decimal("0")
        ) * (
            product.purchase_price or Decimal("0")
        )
        for product in products
    )

    inventory_retail_value = sum(
        (
            product.quantity or Decimal("0")
        ) * (
            product.selling_price or Decimal("0")
        )
        for product in products
    )


    # =========================================================
    # SIMPLE PROFIT
    # =========================================================

    # Historical COGS is not currently available because
    # SaleItem does not store a purchase-cost snapshot.
    #
    # Therefore, this dashboard uses:
    #
    # Net Result = Sales - Expenses
    #
    # This is NOT a full accounting profit calculation.

    gross_profit = (
        Decimal(str(total_sales))
        - Decimal("0")
    )

    net_result = (
        Decimal(str(total_sales))
        - Decimal(str(total_expenses))
    )


    # =========================================================
    # RECENT SALES
    # =========================================================

    recent_sales = (
        Sale.query
        .filter(
            Sale.company_id == company_id
        )
        .order_by(
            Sale.sale_date.desc()
        )
        .limit(6)
        .all()
    )


    # =========================================================
    # RECENT PURCHASES
    # =========================================================

    recent_purchases = (
        Purchase.query
        .filter(
            Purchase.company_id == company_id
        )
        .order_by(
            Purchase.purchase_date.desc()
        )
        .limit(6)
        .all()
    )


    # =========================================================
    # RECENT PAYMENTS
    # =========================================================

    recent_payments = (
        Payment.query
        .filter(
            Payment.company_id == company_id
        )
        .order_by(
            Payment.payment_date.desc()
        )
        .limit(6)
        .all()
    )


    # =========================================================
    # SALES & PURCHASES CHART DATA
    # =========================================================

    chart_data = {

        "daily": {
            "labels": [],
            "sales": [],
            "purchases": []
        },

        "weekly": {
            "labels": [],
            "sales": [],
            "purchases": []
        },

        "monthly": {
            "labels": [],
            "sales": [],
            "purchases": []
        },

        "yearly": {
            "labels": [],
            "sales": [],
            "purchases": []
        }
    }


    # =========================================================
    # DAILY — LAST 7 DAYS
    # =========================================================

    for offset in range(6, -1, -1):

        chart_date = (
            today
            - timedelta(days=offset)
        )

        chart_start, chart_end = company_day_boundaries(
            chart_date
        )

        sales_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Sale.total),
                    0
                )
            )
            .filter(
                Sale.company_id == company_id,
                Sale.sale_date >= chart_start,
                Sale.sale_date < chart_end
            )
            .scalar()
            or 0
        )

        purchase_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Purchase.total),
                    0
                )
            )
            .filter(
                Purchase.company_id == company_id,
                Purchase.purchase_date >= chart_start,
                Purchase.purchase_date < chart_end
            )
            .scalar()
            or 0
        )

        chart_data["daily"]["labels"].append(
            chart_date.strftime("%a")
        )

        chart_data["daily"]["sales"].append(
            float(sales_amount)
        )

        chart_data["daily"]["purchases"].append(
            float(purchase_amount)
        )


    # =========================================================
    # WEEKLY — LAST 8 WEEKS
    # =========================================================

    # Monday is the first day of the company calendar week.
    current_week_start = (
        today
        - timedelta(days=today.weekday())
    )

    for offset in range(7, -1, -1):

        week_start_date = (
            current_week_start
            - timedelta(weeks=offset)
        )

        week_end_date = (
            week_start_date
            + timedelta(days=7)
        )

        week_start, _ = company_day_boundaries(
            week_start_date
        )

        week_end, _ = company_day_boundaries(
            week_end_date
        )

        sales_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Sale.total),
                    0
                )
            )
            .filter(
                Sale.company_id == company_id,
                Sale.sale_date >= week_start,
                Sale.sale_date < week_end
            )
            .scalar()
            or 0
        )

        purchase_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Purchase.total),
                    0
                )
            )
            .filter(
                Purchase.company_id == company_id,
                Purchase.purchase_date >= week_start,
                Purchase.purchase_date < week_end
            )
            .scalar()
            or 0
        )

        chart_data["weekly"]["labels"].append(
            week_start_date.strftime("%d %b")
        )

        chart_data["weekly"]["sales"].append(
            float(sales_amount)
        )

        chart_data["weekly"]["purchases"].append(
            float(purchase_amount)
        )


    # =========================================================
    # MONTHLY — LAST 12 MONTHS
    # =========================================================

    for offset in range(11, -1, -1):

        month_index = (
            today.year * 12
            + (today.month - 1)
            - offset
        )

        year = month_index // 12
        month = (month_index % 12) + 1

        month_start, month_end = company_month_boundaries(
            year,
            month
        )

        sales_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Sale.total),
                    0
                )
            )
            .filter(
                Sale.company_id == company_id,
                Sale.sale_date >= month_start,
                Sale.sale_date < month_end
            )
            .scalar()
            or 0
        )

        purchase_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Purchase.total),
                    0
                )
            )
            .filter(
                Purchase.company_id == company_id,
                Purchase.purchase_date >= month_start,
                Purchase.purchase_date < month_end
            )
            .scalar()
            or 0
        )

        # Label is generated from the company-local calendar.
        chart_label = datetime(
            year,
            month,
            1
        ).strftime("%b %Y")

        chart_data["monthly"]["labels"].append(
            chart_label
        )

        chart_data["monthly"]["sales"].append(
            float(sales_amount)
        )

        chart_data["monthly"]["purchases"].append(
            float(purchase_amount)
        )


    # =========================================================
    # YEARLY — LAST 5 YEARS
    # =========================================================

    for offset in range(4, -1, -1):

        year = today.year - offset

        year_start, year_end = company_year_boundaries(
            year
        )

        sales_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Sale.total),
                    0
                )
            )
            .filter(
                Sale.company_id == company_id,
                Sale.sale_date >= year_start,
                Sale.sale_date < year_end
            )
            .scalar()
            or 0
        )

        purchase_amount = (
            db.session.query(
                func.coalesce(
                    func.sum(Purchase.total),
                    0
                )
            )
            .filter(
                Purchase.company_id == company_id,
                Purchase.purchase_date >= year_start,
                Purchase.purchase_date < year_end
            )
            .scalar()
            or 0
        )

        chart_data["yearly"]["labels"].append(
            str(year)
        )

        chart_data["yearly"]["sales"].append(
            float(sales_amount)
        )

        chart_data["yearly"]["purchases"].append(
            float(purchase_amount)
        )


    # =========================================================
    # PAYMENT SUMMARY
    # =========================================================
    #
    # Payments Received = money actually received
    # from customers for sales during the current month.
    #
    # Supplier payments are excluded because they are
    # money going out and belong to Payables / Purchases.
    # =========================================================

    monthly_payments = (
        db.session.query(
            func.coalesce(
                func.sum(Payment.amount),
                0
            )
        )
        .filter(
            Payment.company_id == company_id,

            # Only customer/sale payments
            Payment.sale_id.isnot(None),

            # Current company-local month
            Payment.payment_date >= start_of_month,
            Payment.payment_date < start_of_next_month
        )
        .scalar()
        or 0
    )


    # =========================================================
    # RENDER
    # =========================================================

    return render_template(
        "dashboard.html",

        user=current_user,

        # -----------------------------------------------------
        # Summary
        # -----------------------------------------------------

        today_sales=today_sales,
        total_sales=total_sales,
        total_sales_count=total_sales_count,

        today_purchases=today_purchases,
        total_purchases=total_purchases,

        today_expenses=today_expenses,
        total_expenses=total_expenses,

        receivables=receivables,
        payables=payables,

        monthly_payments=monthly_payments,

        # -----------------------------------------------------
        # Inventory
        # -----------------------------------------------------

        product_count=product_count,
        low_stock_count=low_stock_count,
        low_stock_products=low_stock_products[:5],

        inventory_value=inventory_value,
        inventory_retail_value=inventory_retail_value,

        # -----------------------------------------------------
        # Profit
        # -----------------------------------------------------

        net_result=net_result,

        # -----------------------------------------------------
        # Activity
        # -----------------------------------------------------

        recent_sales=recent_sales,
        recent_purchases=recent_purchases,
        recent_payments=recent_payments,

        # -----------------------------------------------------
        # Charts
        # -----------------------------------------------------

        chart_data=chart_data
    )