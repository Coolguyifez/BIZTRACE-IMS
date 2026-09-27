from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from flask import render_template, request
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import (
    User,
    Customer,
    Sale,
    SaleItem,
    Purchase,
    Expense,
    Payment,
    Product,
    CashDeposit
)
from app.reports import reports_bp
from app.company_admin.decorators import company_permission_required
from app.utils.company_settings import (
    get_current_company_settings,
    format_currency,
    get_company_timezone,
)


# =========================================================
# HELPERS
# =========================================================

def parse_date(value):
    """
    Parse a YYYY-MM-DD date safely.
    """
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return None


def money(value):
    """
    Convert database numeric values to Decimal.
    """
    if value is None:
        return Decimal("0")

    return Decimal(str(value))


# =========================================================
# REPORT DASHBOARD
# =========================================================

@reports_bp.route("/")
@company_permission_required("view_reports")
def report_dashboard():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    # Always use the current company's timezone when
    # determining today's date.
    today = datetime.now(
        company_timezone
    ).date()

    # Current company ID
    company_id = current_user.company_id

    # =====================================================
    # DATE FILTER
    # =====================================================

    start_date_string = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date_string = request.args.get(
        "end_date",
        ""
    ).strip()

    start_date = parse_date(
        start_date_string
    )

    end_date = parse_date(
        end_date_string
    )

    # =====================================================
    # DEFAULT DATE RANGE
    # Current month
    # =====================================================

    if not start_date and not end_date:

        start_date = today.replace(
            day=1
        )

        end_date = today

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    elif start_date and not end_date:

        end_date = today

        end_date_string = (
            end_date.isoformat()
        )

    elif end_date and not start_date:

        start_date = end_date.replace(
            day=1
        )

        start_date_string = (
            start_date.isoformat()
        )

    # =====================================================
    # PREVENT REVERSED DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    # =====================================================
    # REPORT DATE/TIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # SALES
    # =====================================================

    sales_query = Sale.query.filter(
        Sale.company_id == company_id,

        Sale.sale_date >= start_datetime,

        Sale.sale_date <= end_datetime
    )

    total_sales = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            )
        ).scalar()
    )

    total_sales_count = (
        sales_query.count()
    )

    total_sales_paid = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.paid_amount
                ),
                0
            )
        ).scalar()
    )

    total_receivables = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.balance
                ),
                0
            )
        ).scalar()
    )

    # =====================================================
    # PURCHASES
    # =====================================================

    purchases_query = Purchase.query.filter(
        Purchase.company_id == company_id,

        Purchase.purchase_date >= start_datetime,

        Purchase.purchase_date <= end_datetime
    )

    total_purchases = money(
        purchases_query.with_entities(
            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            )
        ).scalar()
    )

    total_purchase_count = (
        purchases_query.count()
    )

    total_purchase_paid = money(
        purchases_query.with_entities(
            func.coalesce(
                func.sum(
                    Purchase.paid_amount
                ),
                0
            )
        ).scalar()
    )

    total_payables = money(
        purchases_query.with_entities(
            func.coalesce(
                func.sum(
                    Purchase.balance
                ),
                0
            )
        ).scalar()
    )

    # =====================================================
    # EXPENSES
    # =====================================================

    expenses_query = Expense.query.filter(
        Expense.company_id == company_id,

        Expense.expense_date >= start_datetime,

        Expense.expense_date <= end_datetime
    )

    total_expenses = money(
        expenses_query.with_entities(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            )
        ).scalar()
    )

    total_expense_count = (
        expenses_query.count()
    )

    # =====================================================
    # PAYMENTS
    # =====================================================

    payments_query = Payment.query.filter(
        Payment.company_id == company_id,

        Payment.payment_date >= start_datetime,

        Payment.payment_date <= end_datetime
    )

    total_payments = money(
        payments_query.with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        ).scalar()
    )

    total_payment_count = (
        payments_query.count()
    )

    # =====================================================
    # COST OF GOODS SOLD (COGS)
    #
    # COGS =
    # Quantity Sold × Product Purchase Price
    #
    # Purchases are NOT deducted directly from sales.
    # Only the cost of products actually sold is included.
    # =====================================================

    total_cost_of_goods_sold = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    SaleItem.quantity
                    * Product.purchase_price
                ),
                0
            )
        )
        .join(
            Sale,
            Sale.id == SaleItem.sale_id
        )
        .join(
            Product,
            Product.id == SaleItem.product_id
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .scalar()
    )

    # =====================================================
    # GROSS PROFIT
    #
    # Gross Profit =
    # Total Sales - Cost of Goods Sold
    # =====================================================

    gross_profit = (
        total_sales
        - total_cost_of_goods_sold
    )

    # =====================================================
    # NET PROFIT
    #
    # Net Profit =
    # Gross Profit - Operating Expenses
    #
    # Purchases are NOT deducted here because inventory
    # purchases are represented through COGS when sold.
    # =====================================================

    net_profit = (
        gross_profit
        - total_expenses
    )

    # =====================================================
    # SALES PAYMENT STATUS
    # =====================================================

    sales_paid_count = sales_query.filter(
        Sale.payment_status == "Paid"
    ).count()

    sales_partial_count = sales_query.filter(
        Sale.payment_status == "Partially Paid"
    ).count()

    sales_unpaid_count = sales_query.filter(
        Sale.payment_status == "Unpaid"
    ).count()

    # =====================================================
    # PURCHASE PAYMENT STATUS
    # =====================================================

    purchases_paid_count = purchases_query.filter(
        Purchase.payment_status == "Paid"
    ).count()

    purchases_partial_count = purchases_query.filter(
        Purchase.payment_status == "Partially Paid"
    ).count()

    purchases_unpaid_count = purchases_query.filter(
        Purchase.payment_status == "Unpaid"
    ).count()

    # =====================================================
    # RECENT SALES
    # =====================================================

    recent_sales = (
        sales_query
        .order_by(
            Sale.sale_date.desc()
        )
        .limit(5)
        .all()
    )

    # =====================================================
    # RECENT PURCHASES
    # =====================================================

    recent_purchases = (
        purchases_query
        .order_by(
            Purchase.purchase_date.desc()
        )
        .limit(5)
        .all()
    )

    # =====================================================
    # RECENT EXPENSES
    # =====================================================

    recent_expenses = (
        expenses_query
        .order_by(
            Expense.expense_date.desc()
        )
        .limit(5)
        .all()
    )

    # =====================================================
    # DAILY SALES SUMMARY
    # =====================================================

    daily_sales = (
        db.session.query(
            func.date(
                Sale.sale_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            ).label("total")
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            func.date(
                Sale.sale_date
            )
        )
        .order_by(
            func.date(
                Sale.sale_date
            )
        )
        .all()
    )

    # =====================================================
    # DAILY PURCHASE SUMMARY
    # =====================================================

    daily_purchases = (
        db.session.query(
            func.date(
                Purchase.purchase_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            ).label("total")
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .group_by(
            func.date(
                Purchase.purchase_date
            )
        )
        .order_by(
            func.date(
                Purchase.purchase_date
            )
        )
        .all()
    )

    # =====================================================
    # EXPENSE BY CATEGORY
    # =====================================================

    expense_categories = (
        db.session.query(
            Expense.category_id,

            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            ).label("total")
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .group_by(
            Expense.category_id
        )
        .all()
    )

    # =====================================================
    # REPORT DASHBOARD
    # =====================================================

    return render_template(
        "reports/report.html",

        # -------------------------------------------------
        # DATE RANGE
        # -------------------------------------------------

        start_date=start_date_string,

        end_date=end_date_string,

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # SALES
        # -------------------------------------------------

        total_sales=total_sales,

        total_sales_count=total_sales_count,

        total_sales_paid=total_sales_paid,

        total_receivables=total_receivables,

        # -------------------------------------------------
        # PURCHASES
        # -------------------------------------------------

        total_purchases=total_purchases,

        total_purchase_count=total_purchase_count,

        total_purchase_paid=total_purchase_paid,

        total_payables=total_payables,

        # -------------------------------------------------
        # EXPENSES
        # -------------------------------------------------

        total_expenses=total_expenses,

        total_expense_count=total_expense_count,

        # -------------------------------------------------
        # PAYMENTS
        # -------------------------------------------------

        total_payments=total_payments,

        total_payment_count=total_payment_count,

        # -------------------------------------------------
        # PROFITABILITY
        # -------------------------------------------------

        total_cost_of_goods_sold=(
            total_cost_of_goods_sold
        ),

        gross_profit=gross_profit,

        net_profit=net_profit,

        # -------------------------------------------------
        # SALES PAYMENT STATUS
        # -------------------------------------------------

        sales_paid_count=sales_paid_count,

        sales_partial_count=sales_partial_count,

        sales_unpaid_count=sales_unpaid_count,

        # -------------------------------------------------
        # PURCHASE PAYMENT STATUS
        # -------------------------------------------------

        purchases_paid_count=purchases_paid_count,

        purchases_partial_count=purchases_partial_count,

        purchases_unpaid_count=purchases_unpaid_count,

        # -------------------------------------------------
        # RECENT RECORDS
        # -------------------------------------------------

        recent_sales=recent_sales,

        recent_purchases=recent_purchases,

        recent_expenses=recent_expenses,

        # -------------------------------------------------
        # CHART DATA
        # -------------------------------------------------

        daily_sales=daily_sales,

        daily_purchases=daily_purchases,

        expense_categories=expense_categories
    )

# =========================================================
# SALES REPORT
# =========================================================

@reports_bp.route("/sales")
@company_permission_required("view_reports")
def sales_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's timezone for "today"
    today = datetime.now(
        company_timezone
    ).date()

    # =====================================================
    # DATE FILTER
    # =====================================================

    start_date_string = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date_string = request.args.get(
        "end_date",
        ""
    ).strip()

    start_date = parse_date(
        start_date_string
    )

    end_date = parse_date(
        end_date_string
    )

    # =====================================================
    # DEFAULT DATE RANGE
    # Current month
    # =====================================================

    if not start_date and not end_date:

        start_date = today.replace(
            day=1
        )

        end_date = today

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    elif start_date and not end_date:

        end_date = today

        end_date_string = (
            end_date.isoformat()
        )

    elif end_date and not start_date:

        start_date = end_date.replace(
            day=1
        )

        start_date_string = (
            start_date.isoformat()
        )

    # =====================================================
    # PREVENT REVERSED DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    # =====================================================
    # REPORT DATE/TIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # SALES QUERY
    # =====================================================

    sales_query = Sale.query.filter(
        Sale.company_id == company_id,

        Sale.sale_date >= start_datetime,

        Sale.sale_date <= end_datetime
    )

    # =====================================================
    # GET ALL SALES
    # Used by export table
    # =====================================================

    sales = (
        sales_query
        .order_by(
            Sale.sale_date.asc()
        )
        .all()
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    total_sales = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            )
        ).scalar()
    )

    total_paid = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.paid_amount
                ),
                0
            )
        ).scalar()
    )

    total_balance = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.balance
                ),
                0
            )
        ).scalar()
    )

    total_transactions = (
        sales_query.count()
    )

    average_sale = (
        total_sales / total_transactions
        if total_transactions
        else Decimal("0")
    )

    # =====================================================
    # PAYMENT STATUS
    # =====================================================

    paid_count = sales_query.filter(
        Sale.payment_status == "Paid"
    ).count()

    partial_count = sales_query.filter(
        Sale.payment_status == "Partially Paid"
    ).count()

    unpaid_count = sales_query.filter(
        Sale.payment_status == "Unpaid"
    ).count()

    # =====================================================
    # PAYMENT STATUS CHART
    # =====================================================

    payment_status_chart = [
        {
            "status": "Paid",
            "total": paid_count
        },
        {
            "status": "Partially Paid",
            "total": partial_count
        },
        {
            "status": "Unpaid",
            "total": unpaid_count
        }
    ]

    # =====================================================
    # DAILY SALES
    # =====================================================

    daily_sales_rows = (
        db.session.query(
            func.date(
                Sale.sale_date
            ).label(
                "sale_day"
            ),

            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            ).label(
                "total"
            )
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            func.date(
                Sale.sale_date
            )
        )
        .order_by(
            func.date(
                Sale.sale_date
            )
        )
        .all()
    )

    daily_sales = [
        {
            "date": str(
                row.sale_day
            ),

            "total": float(
                row.total or 0
            )
        }

        for row in daily_sales_rows
    ]

    # =====================================================
    # TOP PRODUCTS BY SALES VALUE
    # =====================================================

    top_product_rows = (
        db.session.query(
            Product.name.label(
                "product_name"
            ),

            func.coalesce(
                func.sum(
                    SaleItem.quantity
                ),
                0
            ).label(
                "quantity"
            ),

            func.coalesce(
                func.sum(
                    SaleItem.total
                ),
                0
            ).label(
                "total"
            )
        )
        .join(
            SaleItem,
            SaleItem.product_id == Product.id
        )
        .join(
            Sale,
            Sale.id == SaleItem.sale_id
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            Product.id,
            Product.name
        )
        .order_by(
            func.sum(
                SaleItem.total
            ).desc()
        )
        .limit(10)
        .all()
    )

    top_products = [
        {
            "name": row.product_name,

            "quantity": float(
                row.quantity or 0
            ),

            "total": float(
                row.total or 0
            )
        }

        for row in top_product_rows
    ]

    # =====================================================
    # TOP PRODUCTS BY QUANTITY SOLD
    # =====================================================

    top_product_quantity_rows = (
        db.session.query(
            Product.name.label(
                "product_name"
            ),

            func.coalesce(
                func.sum(
                    SaleItem.quantity
                ),
                0
            ).label(
                "quantity"
            ),

            func.coalesce(
                func.sum(
                    SaleItem.total
                ),
                0
            ).label(
                "total"
            )
        )
        .join(
            SaleItem,
            SaleItem.product_id == Product.id
        )
        .join(
            Sale,
            Sale.id == SaleItem.sale_id
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            Product.id,
            Product.name
        )
        .order_by(
            func.sum(
                SaleItem.quantity
            ).desc()
        )
        .limit(10)
        .all()
    )

    top_products_by_quantity = [
        {
            "name": row.product_name,

            "quantity": float(
                row.quantity or 0
            ),

            "total": float(
                row.total or 0
            )
        }

        for row in top_product_quantity_rows
    ]

    # =====================================================
    # EXPORT TABLE
    # =====================================================

    export_rows = []

    for sale in sales:

        # -------------------------------------------------
        # CUSTOMER
        # -------------------------------------------------

        customer_name = (
            "Walk-in Customer"
        )

        if sale.customer:

            customer_name = (
                sale.customer.name
            )

        # -------------------------------------------------
        # PAYMENT STATUS
        # -------------------------------------------------

        payment_status = (
            sale.payment_status
            or "Unpaid"
        )

        # -------------------------------------------------
        # REMARK
        # -------------------------------------------------

        if payment_status == "Paid":

            remark = "Fully paid"

        elif payment_status == "Partially Paid":

            remark = "Payment outstanding"

        elif payment_status == "Unpaid":

            remark = "Payment required"

        else:

            remark = payment_status

        # -------------------------------------------------
        # EXPORT ROW
        # -------------------------------------------------

        export_rows.append(
            {
                "invoice_number": (
                    sale.invoice_number
                ),

                "date": sale.sale_date,

                "customer": customer_name,

                "subtotal": money(
                    sale.subtotal
                ),

                "discount": money(
                    sale.discount
                ),

                "tax": money(
                    sale.tax
                ),

                "total": money(
                    sale.total
                ),

                "paid": money(
                    sale.paid_amount
                ),

                "balance": money(
                    sale.balance
                ),

                "payment_status": (
                    payment_status
                ),

                "remark": remark
            }
        )

    # =====================================================
    # SALES REPORT
    # =====================================================

    return render_template(
        "reports/sales_report.html",

        # -------------------------------------------------
        # DATE RANGE
        # -------------------------------------------------

        start_date=start_date_string,

        end_date=end_date_string,

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        total_sales=total_sales,

        total_paid=total_paid,

        total_balance=total_balance,

        total_transactions=total_transactions,

        average_sale=average_sale,

        # -------------------------------------------------
        # PAYMENT STATUS
        # -------------------------------------------------

        paid_count=paid_count,

        partial_count=partial_count,

        unpaid_count=unpaid_count,

        payment_status_chart=payment_status_chart,

        # -------------------------------------------------
        # CHART DATA
        # -------------------------------------------------

        daily_sales=daily_sales,

        top_products=top_products,

        top_products_by_quantity=(
            top_products_by_quantity
        ),

        # -------------------------------------------------
        # EXPORT DATA
        # -------------------------------------------------

        export_rows=export_rows
    )


# =========================================================
# PAYMENT REPORT
# =========================================================

@reports_bp.route("/payments")
@company_permission_required("view_reports")
def payment_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone
    today = datetime.now(
        company_timezone
    ).date()

    # =====================================================
    # DATE FILTER
    # =====================================================

    start_date_string = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date_string = request.args.get(
        "end_date",
        ""
    ).strip()

    start_date = parse_date(
        start_date_string
    )

    end_date = parse_date(
        end_date_string
    )

    # =====================================================
    # DEFAULT DATE RANGE
    # Current month
    # =====================================================

    if not start_date and not end_date:

        start_date = today.replace(
            day=1
        )

        end_date = today

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    elif start_date and not end_date:

        end_date = today

        end_date_string = (
            end_date.isoformat()
        )

    elif end_date and not start_date:

        start_date = end_date.replace(
            day=1
        )

        start_date_string = (
            start_date.isoformat()
        )

    # =====================================================
    # CORRECT REVERSED DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    # =====================================================
    # DATETIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # SALES PAYMENT QUERY
    #
    # Only payments connected to a Sale are included.
    #
    # Purchase payments are excluded:
    #
    # Payment.sale_id IS NOT NULL
    # =====================================================

    payments_query = Payment.query.filter(
        Payment.company_id == company_id,

        Payment.sale_id.isnot(None),

        Payment.payment_date >= start_datetime,

        Payment.payment_date <= end_datetime
    )

    payments = (
        payments_query
        .order_by(
            Payment.payment_date.asc(),
            Payment.id.asc()
        )
        .all()
    )

    # =====================================================
    # TOTAL PAYMENTS
    # =====================================================

    total_payments = money(
        payments_query.with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        ).scalar()
    )

    total_payment_count = (
        payments_query.count()
    )

    # =====================================================
    # CASH TOTAL
    # =====================================================

    cash_total = money(
        payments_query
        .filter(
            func.lower(
                func.trim(
                    Payment.method
                )
            ) == "cash"
        )
        .with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # POS TOTAL
    # =====================================================

    pos_total = money(
        payments_query
        .filter(
            func.lower(
                func.trim(
                    Payment.method
                )
            ) == "pos"
        )
        .with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # BANK TRANSFER TOTAL
    # =====================================================

    bank_transfer_total = money(
        payments_query
        .filter(
            func.lower(
                func.trim(
                    Payment.method
                )
            ).in_([
                "bank transfer",
                "bank_transfer",
                "transfer"
            ])
        )
        .with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # OTHER PAYMENT METHODS
    # =====================================================

    known_methods = [
        "cash",
        "pos",
        "bank transfer",
        "bank_transfer",
        "transfer"
    ]

    other_payment_total = money(
        payments_query
        .filter(
            ~func.lower(
                func.trim(
                    Payment.method
                )
            ).in_(known_methods)
        )
        .with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # PAYMENT METHOD CHART
    #
    # SALES PAYMENTS ONLY
    # =====================================================

    payment_method_rows = (
        db.session.query(
            Payment.method.label(
                "method"
            ),

            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            ).label(
                "total"
            )
        )
        .filter(
            Payment.company_id == company_id,

            Payment.sale_id.isnot(None),

            Payment.payment_date >= start_datetime,

            Payment.payment_date <= end_datetime
        )
        .group_by(
            Payment.method
        )
        .order_by(
            func.sum(
                Payment.amount
            ).desc()
        )
        .all()
    )

    payment_method_chart = [
        {
            "method": row.method or "Other",

            "total": float(
                row.total or 0
            )
        }
        for row in payment_method_rows
    ]

    # =====================================================
    # POS BANK BREAKDOWN
    #
    # SALES POS PAYMENTS ONLY
    # =====================================================

    pos_bank_rows = (
        db.session.query(
            Payment.bank_name.label(
                "bank_name"
            ),

            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            ).label(
                "total"
            )
        )
        .filter(
            Payment.company_id == company_id,

            Payment.sale_id.isnot(None),

            Payment.payment_date >= start_datetime,

            Payment.payment_date <= end_datetime,

            func.lower(
                func.trim(
                    Payment.method
                )
            ) == "pos"
        )
        .group_by(
            Payment.bank_name
        )
        .order_by(
            func.sum(
                Payment.amount
            ).desc()
        )
        .all()
    )

    pos_bank_breakdown = [
        {
            "bank": (
                row.bank_name
                or "Bank Not Specified"
            ),

            "total": float(
                row.total or 0
            )
        }
        for row in pos_bank_rows
    ]

    # =====================================================
    # BANK TRANSFER BANK BREAKDOWN
    #
    # SALES BANK TRANSFERS ONLY
    # =====================================================

    transfer_bank_rows = (
        db.session.query(
            Payment.bank_name.label(
                "bank_name"
            ),

            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            ).label(
                "total"
            )
        )
        .filter(
            Payment.company_id == company_id,

            Payment.sale_id.isnot(None),

            Payment.payment_date >= start_datetime,

            Payment.payment_date <= end_datetime,

            func.lower(
                func.trim(
                    Payment.method
                )
            ).in_([
                "bank transfer",
                "bank_transfer",
                "transfer"
            ])
        )
        .group_by(
            Payment.bank_name
        )
        .order_by(
            func.sum(
                Payment.amount
            ).desc()
        )
        .all()
    )

    transfer_bank_breakdown = [
        {
            "bank": (
                row.bank_name
                or "Bank Not Specified"
            ),

            "total": float(
                row.total or 0
            )
        }
        for row in transfer_bank_rows
    ]

    # =====================================================
    # COMBINED BANK BREAKDOWN
    #
    # POS and Bank Transfer remain separate.
    #
    # Example:
    #
    # POS
    #   Zenith Bank       ₦500,000
    #
    # Bank Transfer
    #   Zenith Bank       ₦700,000
    #
    # They are NOT combined.
    # =====================================================

    bank_breakdown = []

    for row in pos_bank_breakdown:

        bank_breakdown.append(
            {
                "method": "POS",

                "bank": row["bank"],

                "total": row["total"]
            }
        )

    for row in transfer_bank_breakdown:

        bank_breakdown.append(
            {
                "method": "Bank Transfer",

                "bank": row["bank"],

                "total": row["total"]
            }
        )

    # =====================================================
    # EXPORT ROWS
    #
    # SALES PAYMENTS ONLY
    # =====================================================

    export_rows = []

    for payment in payments:

        # -------------------------------------------------
        # Related sales invoice
        # -------------------------------------------------

        related_transaction = "—"

        if payment.sale:

            related_transaction = (
                payment.sale.invoice_number
            )

        # -------------------------------------------------
        # Payment information
        # -------------------------------------------------

        method = (
            payment.method
            or "Other"
        )

        bank_name = (
            payment.bank_name
            or "—"
        )

        account_name = (
            payment.account_name
            or "—"
        )

        account_number = (
            payment.account_number
            or "—"
        )

        reference = (
            payment.reference
            or "—"
        )

        # -------------------------------------------------
        # Remark intentionally blank
        # -------------------------------------------------

        export_rows.append(
            {
                "date": payment.payment_date,

                "reference": reference,

                "method": method,

                "bank_name": bank_name,

                "account_name": account_name,

                "account_number": account_number,

                "amount": money(
                    payment.amount
                ),

                "related_transaction":
                    related_transaction,

                "remark": ""
            }
        )

    # =====================================================
    # RENDER PAYMENT REPORT
    # =====================================================

    return render_template(
        "reports/payment_report.html",

        # -------------------------------------------------
        # DATE RANGE
        # -------------------------------------------------

        start_date=start_date_string,

        end_date=end_date_string,

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        total_payments=total_payments,

        total_payment_count=total_payment_count,

        cash_total=cash_total,

        pos_total=pos_total,

        bank_transfer_total=bank_transfer_total,

        other_payment_total=other_payment_total,

        # -------------------------------------------------
        # PAYMENT METHOD CHART
        # -------------------------------------------------

        payment_method_chart=payment_method_chart,

        # -------------------------------------------------
        # POS BANK BREAKDOWN
        # -------------------------------------------------

        pos_bank_breakdown=pos_bank_breakdown,

        # -------------------------------------------------
        # BANK TRANSFER BREAKDOWN
        # -------------------------------------------------

        transfer_bank_breakdown=transfer_bank_breakdown,

        # -------------------------------------------------
        # COMBINED BANK BREAKDOWN
        # -------------------------------------------------

        bank_breakdown=bank_breakdown,

        # -------------------------------------------------
        # EXPORT TABLE
        # -------------------------------------------------

        export_rows=export_rows
    )

# =========================================================
# RECEIVABLES REPORT
# =========================================================

@reports_bp.route("/receivables")
@company_permission_required("view_reports")
def receivables_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone when determining
    # today's date.
    today = datetime.now(
        company_timezone
    ).date()

    # =====================================================
    # DATE FILTER
    # =====================================================

    start_date_string = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date_string = request.args.get(
        "end_date",
        ""
    ).strip()

    start_date = parse_date(
        start_date_string
    )

    end_date = parse_date(
        end_date_string
    )

    # =====================================================
    # DEFAULT DATE RANGE
    # Current month
    # =====================================================

    if not start_date and not end_date:

        start_date = today.replace(
            day=1
        )

        end_date = today

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    elif start_date and not end_date:

        end_date = today

        end_date_string = (
            end_date.isoformat()
        )

    elif end_date and not start_date:

        start_date = end_date.replace(
            day=1
        )

        start_date_string = (
            start_date.isoformat()
        )

    # =====================================================
    # CORRECT REVERSED DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

        start_date_string = (
            start_date.isoformat()
        )

        end_date_string = (
            end_date.isoformat()
        )

    # =====================================================
    # DATETIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # SALES QUERY
    #
    # Only sales belonging to the current company
    # and within the selected date range.
    # =====================================================

    sales_query = Sale.query.filter(
        Sale.company_id == company_id,

        Sale.sale_date >= start_datetime,

        Sale.sale_date <= end_datetime
    )

    sales = (
        sales_query
        .order_by(
            Sale.sale_date.asc(),
            Sale.id.asc()
        )
        .all()
    )

    # =====================================================
    # TOTAL SALES / INVOICE AMOUNT
    # =====================================================

    total_invoice_amount = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            )
        ).scalar()
    )

    # =====================================================
    # TOTAL PAID
    # =====================================================

    total_paid = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.paid_amount
                ),
                0
            )
        ).scalar()
    )

    # =====================================================
    # TOTAL RECEIVABLES
    # =====================================================

    total_receivables = money(
        sales_query.with_entities(
            func.coalesce(
                func.sum(
                    Sale.balance
                ),
                0
            )
        ).scalar()
    )

    # =====================================================
    # OUTSTANDING INVOICES
    # =====================================================

    outstanding_sales = [
        sale
        for sale in sales
        if money(
            sale.balance
        ) > Decimal("0")
    ]

    outstanding_invoice_count = len(
        outstanding_sales
    )

    # =====================================================
    # CUSTOMERS OWING
    # =====================================================

    customer_ids_owing = set()

    for sale in outstanding_sales:

        if sale.customer_id:

            customer_ids_owing.add(
                sale.customer_id
            )

    customers_owing_count = len(
        customer_ids_owing
    )

    # =====================================================
    # PARTIALLY PAID
    # =====================================================

    partially_paid_sales = [
        sale
        for sale in sales
        if (
            money(
                sale.paid_amount
            ) > Decimal("0")

            and

            money(
                sale.balance
            ) > Decimal("0")
        )
    ]

    partially_paid_amount = sum(
        (
            money(
                sale.balance
            )
            for sale in partially_paid_sales
        ),
        Decimal("0")
    )

    partially_paid_count = len(
        partially_paid_sales
    )

    # =====================================================
    # OVERDUE
    #
    # Sale currently has no due_date field.
    #
    # Therefore an outstanding invoice dated before
    # today's company-local date is treated as overdue.
    # =====================================================

    overdue_sales = [
        sale
        for sale in outstanding_sales
        if sale.sale_date.date() < today
    ]

    overdue_amount = sum(
        (
            money(
                sale.balance
            )
            for sale in overdue_sales
        ),
        Decimal("0")
    )

    overdue_invoice_count = len(
        overdue_sales
    )

    # =====================================================
    # CURRENT OUTSTANDING
    #
    # Outstanding invoices dated today.
    # =====================================================

    current_outstanding_sales = [
        sale
        for sale in outstanding_sales
        if sale.sale_date.date() >= today
    ]

    current_outstanding_amount = sum(
        (
            money(
                sale.balance
            )
            for sale in current_outstanding_sales
        ),
        Decimal("0")
    )

    # =====================================================
    # PAYMENT STATUS SUMMARY
    # =====================================================

    paid_sales = [
        sale
        for sale in sales
        if money(
            sale.balance
        ) <= Decimal("0")
    ]

    unpaid_sales = [
        sale
        for sale in sales
        if (
            money(
                sale.paid_amount
            ) <= Decimal("0")

            and

            money(
                sale.balance
            ) > Decimal("0")
        )
    ]

    paid_count = len(
        paid_sales
    )

    unpaid_count = len(
        unpaid_sales
    )

    # =====================================================
    # CUSTOMER RECEIVABLE BREAKDOWN
    #
    # Outstanding balance grouped by customer.
    # =====================================================

    customer_totals = {}

    for sale in outstanding_sales:

        balance = money(
            sale.balance
        )

        if balance <= Decimal("0"):
            continue

        customer_id = sale.customer_id

        # -------------------------------------------------
        # Named customer
        # -------------------------------------------------

        if customer_id:

            customer_name = (
                sale.customer.name
                if sale.customer
                else "Unknown Customer"
            )

            key = str(
                customer_id
            )

        # -------------------------------------------------
        # Walk-in customer
        # -------------------------------------------------

        else:

            customer_name = (
                "Walk-in Customer"
            )

            key = "walk-in"

        # -------------------------------------------------
        # Initialize customer
        # -------------------------------------------------

        if key not in customer_totals:

            customer_totals[key] = {
                "customer": customer_name,
                "total": Decimal("0"),
                "invoice_count": 0
            }

        # -------------------------------------------------
        # Add outstanding balance
        # -------------------------------------------------

        customer_totals[key]["total"] += (
            balance
        )

        customer_totals[key]["invoice_count"] += 1

    # =====================================================
    # SORT CUSTOMER BREAKDOWN
    # Highest outstanding balance first.
    # =====================================================

    customer_breakdown = sorted(
        customer_totals.values(),
        key=lambda item: item["total"],
        reverse=True
    )

    # =====================================================
    # CUSTOMER CHART
    # =====================================================

    customer_chart = [
        {
            "customer": item["customer"],
            "total": float(
                item["total"]
            )
        }
        for item in customer_breakdown[:10]
    ]

    # =====================================================
    # PAYMENT STATUS CHART
    # =====================================================

    payment_status_chart = [
        {
            "status": "Paid",
            "total": float(
                total_paid
            )
        },
        {
            "status": "Outstanding",
            "total": float(
                total_receivables
            )
        }
    ]

    # =====================================================
    # AGING SUMMARY
    #
    # Since Sale has no due_date, aging is based on
    # sale_date.
    # =====================================================

    aging_0_30 = Decimal("0")

    aging_31_60 = Decimal("0")

    aging_61_90 = Decimal("0")

    aging_91_plus = Decimal("0")

    for sale in outstanding_sales:

        balance = money(
            sale.balance
        )

        sale_day = sale.sale_date.date()

        days_outstanding = (
            today - sale_day
        ).days

        # -------------------------------------------------
        # 0–30 days
        # -------------------------------------------------

        if days_outstanding <= 30:

            aging_0_30 += balance

        # -------------------------------------------------
        # 31–60 days
        # -------------------------------------------------

        elif days_outstanding <= 60:

            aging_31_60 += balance

        # -------------------------------------------------
        # 61–90 days
        # -------------------------------------------------

        elif days_outstanding <= 90:

            aging_61_90 += balance

        # -------------------------------------------------
        # 91+ days
        # -------------------------------------------------

        else:

            aging_91_plus += balance

    # =====================================================
    # AGING CHART
    # =====================================================

    aging_chart = [
        {
            "label": "0–30 Days",
            "total": float(
                aging_0_30
            )
        },
        {
            "label": "31–60 Days",
            "total": float(
                aging_31_60
            )
        },
        {
            "label": "61–90 Days",
            "total": float(
                aging_61_90
            )
        },
        {
            "label": "91+ Days",
            "total": float(
                aging_91_plus
            )
        }
    ]

    # =====================================================
    # EXPORT ROWS
    # =====================================================

    export_rows = []

    for sale in sales:

        total = money(
            sale.total
        )

        paid = money(
            sale.paid_amount
        )

        balance = money(
            sale.balance
        )

        # -------------------------------------------------
        # CUSTOMER
        # -------------------------------------------------

        if sale.customer:

            customer_name = (
                sale.customer.name
            )

        else:

            customer_name = (
                "Walk-in Customer"
            )

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        if balance <= Decimal("0"):

            status = "Paid"

        elif paid > Decimal("0"):

            status = "Partially Paid"

        else:

            status = "Unpaid"

        # -------------------------------------------------
        # OVERDUE STATUS
        # -------------------------------------------------

        if (
            balance > Decimal("0")
            and sale.sale_date.date() < today
        ):

            status = "Overdue"

        # -------------------------------------------------
        # EXPORT ROW
        # -------------------------------------------------

        export_rows.append(
            {
                "date": sale.sale_date,

                "invoice": sale.invoice_number,

                "customer": customer_name,

                "total": total,

                "paid": paid,

                "balance": balance,

                "status": status
            }
        )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "reports/receivables_report.html",

        # -------------------------------------------------
        # DATE RANGE
        # -------------------------------------------------

        start_date=start_date_string,

        end_date=end_date_string,

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        total_invoice_amount=(
            total_invoice_amount
        ),

        total_paid=total_paid,

        total_receivables=(
            total_receivables
        ),

        customers_owing_count=(
            customers_owing_count
        ),

        outstanding_invoice_count=(
            outstanding_invoice_count
        ),

        overdue_amount=(
            overdue_amount
        ),

        overdue_invoice_count=(
            overdue_invoice_count
        ),

        partially_paid_amount=(
            partially_paid_amount
        ),

        partially_paid_count=(
            partially_paid_count
        ),

        current_outstanding_amount=(
            current_outstanding_amount
        ),

        paid_count=paid_count,

        unpaid_count=unpaid_count,

        # -------------------------------------------------
        # CUSTOMER BREAKDOWN
        # -------------------------------------------------

        customer_breakdown=(
            customer_breakdown
        ),

        customer_chart=customer_chart,

        # -------------------------------------------------
        # PAYMENT STATUS
        # -------------------------------------------------

        payment_status_chart=(
            payment_status_chart
        ),

        # -------------------------------------------------
        # AGING
        # -------------------------------------------------

        aging_0_30=aging_0_30,

        aging_31_60=aging_31_60,

        aging_61_90=aging_61_90,

        aging_91_plus=aging_91_plus,

        aging_chart=aging_chart,

        # -------------------------------------------------
        # EXPORT
        # -------------------------------------------------

        export_rows=export_rows
    )


@reports_bp.route("/payables")
@company_permission_required("view_reports")
def payables_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone
    today = datetime.now(
        company_timezone
    ).date()

    # =====================================================
    # DATE FILTER
    # =====================================================

    default_start = today.replace(
        day=1
    )

    start_date = (
        parse_date(
            request.args.get("start_date")
        )
        or default_start
    )

    end_date = (
        parse_date(
            request.args.get("end_date")
        )
        or today
    )

    # =====================================================
    # PREVENT INVALID DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # =====================================================
    # DATE/TIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # BASE PURCHASE QUERY
    # =====================================================

    purchase_query = Purchase.query.filter(
        Purchase.company_id == company_id,

        Purchase.purchase_date >= start_datetime,

        Purchase.purchase_date <= end_datetime
    )

    purchases = (
        purchase_query
        .order_by(
            Purchase.purchase_date.desc()
        )
        .all()
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    total_purchases = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .scalar()
    )

    total_paid = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Purchase.paid_amount
                ),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .scalar()
    )

    total_payables = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Purchase.balance
                ),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .scalar()
    )

    total_purchase_count = (
        purchase_query.count()
    )

    # =====================================================
    # SUPPLIER BREAKDOWN
    # =====================================================

    supplier_data = {}

    for purchase in purchases:

        if purchase.supplier:

            supplier_name = (
                purchase.supplier.name
            )

        else:

            supplier_name = "No Supplier"

        if supplier_name not in supplier_data:

            supplier_data[supplier_name] = {
                "supplier": supplier_name,
                "total": Decimal("0"),
                "paid": Decimal("0"),
                "balance": Decimal("0")
            }

        supplier_data[supplier_name]["total"] += (
            money(
                purchase.total
            )
        )

        supplier_data[supplier_name]["paid"] += (
            money(
                purchase.paid_amount
            )
        )

        supplier_data[supplier_name]["balance"] += (
            money(
                purchase.balance
            )
        )

    supplier_breakdown = sorted(
        supplier_data.values(),
        key=lambda row: row["balance"],
        reverse=True
    )

    # =====================================================
    # SUPPLIERS WITH OUTSTANDING PAYABLES
    # =====================================================

    supplier_count = sum(
        1
        for row in supplier_breakdown
        if row["balance"] > Decimal("0")
    )

    # =====================================================
    # PAYMENT STATUS CHART
    # =====================================================

    payment_status_rows = (
        db.session.query(
            Purchase.payment_status.label(
                "status"
            ),

            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            ).label(
                "total"
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .group_by(
            Purchase.payment_status
        )
        .all()
    )

    payment_status_chart = [
        {
            "status": (
                row.status
                or "Unknown"
            ),

            "total": float(
                money(
                    row.total
                )
            )
        }

        for row in payment_status_rows
    ]

    # =====================================================
    # AGING ANALYSIS
    #
    # Purchase has no payment due date.
    # purchase_date is therefore used as the aging date.
    #
    # Only outstanding balances are included.
    # =====================================================

    aging_0_30 = Decimal("0")

    aging_31_60 = Decimal("0")

    aging_61_90 = Decimal("0")

    aging_91_plus = Decimal("0")

    # =====================================================
    # EXPORT ROWS
    # =====================================================

    export_rows = []

    for purchase in purchases:

        total = money(
            purchase.total
        )

        paid = money(
            purchase.paid_amount
        )

        balance = money(
            purchase.balance
        )

        # =================================================
        # DETERMINE AGING
        # =================================================

        if balance <= Decimal("0"):

            aging = "Paid"

        else:

            if purchase.purchase_date:

                purchase_date = (
                    purchase.purchase_date.date()
                    if hasattr(
                        purchase.purchase_date,
                        "date"
                    )
                    else purchase.purchase_date
                )

                age_days = max(
                    (
                        today
                        - purchase_date
                    ).days,
                    0
                )

            else:

                age_days = 0

            if age_days <= 30:

                aging = "0–30 Days"

                aging_0_30 += balance

            elif age_days <= 60:

                aging = "31–60 Days"

                aging_31_60 += balance

            elif age_days <= 90:

                aging = "61–90 Days"

                aging_61_90 += balance

            else:

                aging = "91+ Days"

                aging_91_plus += balance

        # =================================================
        # SUPPLIER
        # =================================================

        supplier_name = (
            purchase.supplier.name
            if purchase.supplier
            else "No Supplier"
        )

        # =================================================
        # EXPORT ROW
        # =================================================

        export_rows.append(
            {
                "date": purchase.purchase_date,

                "purchase_number": (
                    purchase.purchase_number
                ),

                "supplier": supplier_name,

                "total": total,

                "paid": paid,

                "balance": balance,

                "payment_status": (
                    purchase.payment_status
                    or "Unknown"
                ),

                "aging": aging
            }
        )

    # =====================================================
    # AGING CHART
    # =====================================================

    aging_chart = [
        {
            "label": "0–30 Days",
            "total": float(
                aging_0_30
            )
        },

        {
            "label": "31–60 Days",
            "total": float(
                aging_31_60
            )
        },

        {
            "label": "61–90 Days",
            "total": float(
                aging_61_90
            )
        },

        {
            "label": "91+ Days",
            "total": float(
                aging_91_plus
            )
        }
    ]

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "reports/payables_report.html",

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        total_purchases=total_purchases,

        total_purchase_count=(
            total_purchase_count
        ),

        total_paid=total_paid,

        total_payables=total_payables,

        supplier_count=supplier_count,

        # -------------------------------------------------
        # CHARTS
        # -------------------------------------------------

        payment_status_chart=(
            payment_status_chart
        ),

        aging_chart=aging_chart,

        # -------------------------------------------------
        # AGING
        # -------------------------------------------------

        aging_0_30=aging_0_30,

        aging_31_60=aging_31_60,

        aging_61_90=aging_61_90,

        aging_91_plus=aging_91_plus,

        # -------------------------------------------------
        # TABLES
        # -------------------------------------------------

        supplier_breakdown=(
            supplier_breakdown
        ),

        export_rows=export_rows
    )

# =========================================================
# PROFIT & LOSS REPORT
# =========================================================

@reports_bp.route("/profit-loss")
@company_permission_required("view_reports")
def profit_loss_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone
    today = datetime.now(
        company_timezone
    ).date()

    # =====================================================
    # DATE FILTER
    # =====================================================

    default_start = today.replace(
        day=1
    )

    start_date_string = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date_string = request.args.get(
        "end_date",
        ""
    ).strip()

    start_date = (
        parse_date(start_date_string)
        or default_start
    )

    end_date = (
        parse_date(end_date_string)
        or today
    )

    # =====================================================
    # PREVENT REVERSED DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # =====================================================
    # DATE/TIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # SALES / REVENUE
    # =====================================================

    total_sales = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            )
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .scalar()
    )

    total_sales_count = (
        Sale.query
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .count()
    )

    # =====================================================
    # COST OF GOODS SOLD
    #
    # COGS =
    # Quantity Sold × Product Purchase Price
    #
    # Purchases are NOT deducted directly from sales.
    # =====================================================

    total_cogs = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    SaleItem.quantity
                    * Product.purchase_price
                ),
                0
            )
        )
        .join(
            Sale,
            Sale.id == SaleItem.sale_id
        )
        .join(
            Product,
            Product.id == SaleItem.product_id
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .scalar()
    )

    # =====================================================
    # GROSS PROFIT
    #
    # Gross Profit =
    # Sales - COGS
    # =====================================================

    gross_profit = (
        total_sales
        - total_cogs
    )

    # =====================================================
    # GROSS PROFIT MARGIN
    #
    # Gross Margin =
    # Gross Profit / Sales × 100
    # =====================================================

    gross_profit_margin = (
        (
            gross_profit
            / total_sales
        )
        * Decimal("100")
        if total_sales > 0
        else Decimal("0")
    )

    # =====================================================
    # OPERATING EXPENSES
    # =====================================================

    total_expenses = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            )
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .scalar()
    )

    total_expense_count = (
        Expense.query
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .count()
    )

    # =====================================================
    # NET PROFIT
    #
    # Net Profit =
    # Gross Profit - Operating Expenses
    # =====================================================

    net_profit = (
        gross_profit
        - total_expenses
    )

    # =====================================================
    # NET PROFIT MARGIN
    #
    # Net Margin =
    # Net Profit / Sales × 100
    # =====================================================

    net_profit_margin = (
        (
            net_profit
            / total_sales
        )
        * Decimal("100")
        if total_sales > 0
        else Decimal("0")
    )

    # =====================================================
    # PROFITABILITY STATUS
    # =====================================================

    if net_profit > 0:

        profit_status = "Profit"

    elif net_profit < 0:

        profit_status = "Loss"

    else:

        profit_status = "Break-even"

    # =====================================================
    # SALES / COGS / EXPENSES CHART
    #
    # Keep chart values numeric.
    # Currency formatting should happen in JavaScript.
    # =====================================================

    financial_chart = [
        {
            "label": "Sales",
            "total": float(total_sales)
        },
        {
            "label": "COGS",
            "total": float(total_cogs)
        },
        {
            "label": "Expenses",
            "total": float(total_expenses)
        }
    ]

    # =====================================================
    # DAILY PROFIT TREND
    # =====================================================

    daily_sales = (
        db.session.query(
            func.date(
                Sale.sale_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            ).label("total")
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            func.date(
                Sale.sale_date
            )
        )
        .order_by(
            func.date(
                Sale.sale_date
            )
        )
        .all()
    )

    # =====================================================
    # DAILY COGS
    # =====================================================

    daily_cogs = (
        db.session.query(
            func.date(
                Sale.sale_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    SaleItem.quantity
                    * Product.purchase_price
                ),
                0
            ).label("total")
        )
        .join(
            Sale,
            Sale.id == SaleItem.sale_id
        )
        .join(
            Product,
            Product.id == SaleItem.product_id
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            func.date(
                Sale.sale_date
            )
        )
        .order_by(
            func.date(
                Sale.sale_date
            )
        )
        .all()
    )

    # =====================================================
    # DAILY EXPENSES
    # =====================================================

    daily_expenses = (
        db.session.query(
            func.date(
                Expense.expense_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            ).label("total")
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .group_by(
            func.date(
                Expense.expense_date
            )
        )
        .order_by(
            func.date(
                Expense.expense_date
            )
        )
        .all()
    )

    # =====================================================
    # CREATE DAILY MAPS
    # =====================================================

    sales_map = {
        str(row.date): money(
            row.total
        )
        for row in daily_sales
    }

    cogs_map = {
        str(row.date): money(
            row.total
        )
        for row in daily_cogs
    }

    expenses_map = {
        str(row.date): money(
            row.total
        )
        for row in daily_expenses
    }

    # =====================================================
    # BUILD DAILY PROFIT TREND
    # =====================================================

    daily_profit_trend = []

    activity_dates = (
        set(sales_map.keys())
        | set(cogs_map.keys())
        | set(expenses_map.keys())
    )

    for date_key in sorted(
        activity_dates
    ):

        sales = sales_map.get(
            date_key,
            Decimal("0")
        )

        cogs = cogs_map.get(
            date_key,
            Decimal("0")
        )

        expenses = expenses_map.get(
            date_key,
            Decimal("0")
        )

        # ---------------------------------------------
        # Daily gross profit
        # ---------------------------------------------

        gross = (
            sales
            - cogs
        )

        # ---------------------------------------------
        # Daily net profit
        # ---------------------------------------------

        net = (
            gross
            - expenses
        )

        # ---------------------------------------------
        # Display date
        # ---------------------------------------------

        try:

            display_date = datetime.strptime(
                date_key,
                "%Y-%m-%d"
            ).strftime(
                "%d %b"
            )

        except ValueError:

            display_date = date_key

        daily_profit_trend.append(
            {
                "date": display_date,

                "sales": float(
                    sales
                ),

                "cogs": float(
                    cogs
                ),

                "expenses": float(
                    expenses
                ),

                "gross_profit": float(
                    gross
                ),

                "net_profit": float(
                    net
                )
            }
        )

    # =====================================================
    # PROFIT & LOSS EXPORT
    #
    # Keep amounts as Decimal.
    # Currency formatting should happen in the export
    # layer or report template.
    # =====================================================

    export_rows = [
        {
            "description": "Total Sales",
            "amount": total_sales
        },
        {
            "description": "Cost of Goods Sold",
            "amount": total_cogs
        },
        {
            "description": "Gross Profit",
            "amount": gross_profit
        },
        {
            "description": "Operating Expenses",
            "amount": total_expenses
        },
        {
            "description": "Net Profit",
            "amount": net_profit
        }
    ]

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "reports/profit_loss_report.html",

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        company_id=company_id,

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # -------------------------------------------------
        # SALES
        # -------------------------------------------------

        total_sales=total_sales,

        total_sales_count=total_sales_count,

        # -------------------------------------------------
        # COGS
        # -------------------------------------------------

        total_cogs=total_cogs,

        # -------------------------------------------------
        # GROSS PROFIT
        # -------------------------------------------------

        gross_profit=gross_profit,

        gross_profit_margin=gross_profit_margin,

        # -------------------------------------------------
        # EXPENSES
        # -------------------------------------------------

        total_expenses=total_expenses,

        total_expense_count=total_expense_count,

        # -------------------------------------------------
        # NET PROFIT
        # -------------------------------------------------

        net_profit=net_profit,

        net_profit_margin=net_profit_margin,

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        profit_status=profit_status,

        # -------------------------------------------------
        # CHARTS
        # -------------------------------------------------

        financial_chart=financial_chart,

        daily_profit_trend=daily_profit_trend,

        # -------------------------------------------------
        # EXPORT
        # -------------------------------------------------

        export_rows=export_rows
    )


@reports_bp.route("/purchases")
@company_permission_required("view_reports")
def purchase_report():

    # =========================================================
    # CURRENT COMPANY SETTINGS
    # =========================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone
    today = datetime.now(
        company_timezone
    ).date()

    default_start = today.replace(
        day=1
    )

    # =========================================================
    # DATE FILTER
    # =========================================================

    start_date = (
        parse_date(
            request.args.get("start_date")
        )
        or default_start
    )

    end_date = (
        parse_date(
            request.args.get("end_date")
        )
        or today
    )

    # =========================================================
    # PREVENT REVERSED DATE RANGE
    # =========================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # =========================================================
    # REPORT DATE/TIME RANGE
    # =========================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =========================================================
    # PURCHASE QUERY
    # =========================================================

    purchase_query = Purchase.query.filter(
        Purchase.company_id == company_id,

        Purchase.purchase_date >= start_datetime,

        Purchase.purchase_date <= end_datetime
    )

    purchases = (
        purchase_query
        .order_by(
            Purchase.purchase_date.desc()
        )
        .all()
    )

    # =========================================================
    # TOTAL PURCHASES
    # =========================================================

    total_purchases = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .scalar()
    )

    # =========================================================
    # TOTAL PAID
    # =========================================================

    total_paid = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Purchase.paid_amount
                ),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .scalar()
    )

    # =========================================================
    # TOTAL PAYABLES
    # =========================================================

    total_payables = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Purchase.balance
                ),
                0
            )
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .scalar()
    )

    # =========================================================
    # PURCHASE COUNT
    # =========================================================

    total_purchase_count = (
        purchase_query.count()
    )

    # =========================================================
    # PAYMENT STATUS
    # =========================================================

    payment_status_rows = (
        db.session.query(
            Purchase.payment_status.label(
                "status"
            ),

            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            ).label("total")
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .group_by(
            Purchase.payment_status
        )
        .all()
    )

    payment_status_chart = [
        {
            "status": (
                row.status
                or "Unknown"
            ),

            "total": float(
                money(row.total)
            )
        }

        for row in payment_status_rows
    ]

    # =========================================================
    # DAILY PURCHASE TREND
    # =========================================================

    daily_purchase_rows = (
        db.session.query(
            func.date(
                Purchase.purchase_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    Purchase.total
                ),
                0
            ).label("total")
        )
        .filter(
            Purchase.company_id == company_id,

            Purchase.purchase_date >= start_datetime,

            Purchase.purchase_date <= end_datetime
        )
        .group_by(
            func.date(
                Purchase.purchase_date
            )
        )
        .order_by(
            func.date(
                Purchase.purchase_date
            )
        )
        .all()
    )

    daily_purchase_trend = [
        {
            "date": (
                row.date.strftime("%d %b")
                if hasattr(
                    row.date,
                    "strftime"
                )
                else str(row.date)
            ),

            "total": float(
                money(row.total)
            )
        }

        for row in daily_purchase_rows
    ]

    # =========================================================
    # SUPPLIER BREAKDOWN
    # =========================================================

    supplier_data = {}

    for purchase in purchases:

        supplier_name = (
            purchase.supplier.name
            if purchase.supplier
            else "No Supplier"
        )

        if supplier_name not in supplier_data:

            supplier_data[supplier_name] = {

                "supplier":
                    supplier_name,

                "count":
                    0,

                "total":
                    Decimal("0"),

                "paid":
                    Decimal("0"),

                "balance":
                    Decimal("0")
            }

        row = supplier_data[
            supplier_name
        ]

        row["count"] += 1

        row["total"] += money(
            purchase.total
        )

        row["paid"] += money(
            purchase.paid_amount
        )

        row["balance"] += money(
            purchase.balance
        )

    supplier_breakdown = sorted(
        supplier_data.values(),

        key=lambda row:
            row["total"],

        reverse=True
    )

    # =========================================================
    # OUTSTANDING SUPPLIERS COUNT
    # =========================================================

    outstanding_supplier_count = sum(
        1

        for row in supplier_breakdown

        if row["balance"] > Decimal("0")
    )

    # =========================================================
    # EXPORT ROWS
    # =========================================================

    export_rows = []

    for purchase in purchases:

        supplier_name = (
            purchase.supplier.name
            if purchase.supplier
            else "No Supplier"
        )

        export_rows.append(
            {
                "date":
                    purchase.purchase_date,

                "purchase_number":
                    purchase.purchase_number,

                "supplier":
                    supplier_name,

                "subtotal":
                    money(
                        purchase.subtotal
                    ),

                "discount":
                    money(
                        purchase.discount
                    ),

                "tax":
                    money(
                        purchase.tax
                    ),

                "total":
                    money(
                        purchase.total
                    ),

                "paid":
                    money(
                        purchase.paid_amount
                    ),

                "balance":
                    money(
                        purchase.balance
                    ),

                "payment_status":
                    (
                        purchase.payment_status
                        or "Unknown"
                    )
            }
        )

    # =========================================================
    # RENDER
    # =========================================================

    return render_template(
        "reports/purchase_report.html",

        # -----------------------------------------------------
        # DATE RANGE
        # -----------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # -----------------------------------------------------
        # COMPANY SETTINGS
        # -----------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -----------------------------------------------------
        # PURCHASE TOTALS
        # -----------------------------------------------------

        total_purchases=
            total_purchases,

        total_purchase_count=
            total_purchase_count,

        total_paid=
            total_paid,

        total_payables=
            total_payables,

        # -----------------------------------------------------
        # SUPPLIERS
        # -----------------------------------------------------

        outstanding_supplier_count=
            outstanding_supplier_count,

        supplier_breakdown=
            supplier_breakdown,

        # -----------------------------------------------------
        # CHART DATA
        # -----------------------------------------------------

        payment_status_chart=
            payment_status_chart,

        daily_purchase_trend=
            daily_purchase_trend,

        # -----------------------------------------------------
        # EXPORT DATA
        # -----------------------------------------------------

        export_rows=
            export_rows
    )

@reports_bp.route("/expenses")
@company_permission_required("view_reports")
def expense_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()
    company_timezone = get_company_timezone()

    # Current company
    company_id = current_user.company_id

    # Use the company's configured timezone
    today = datetime.now(
        company_timezone
    ).date()

    default_start = today.replace(
        day=1
    )

    # =====================================================
    # DATE FILTER
    # =====================================================

    start_date = (
        parse_date(
            request.args.get("start_date")
        )
        or default_start
    )

    end_date = (
        parse_date(
            request.args.get("end_date")
        )
        or today
    )

    # =====================================================
    # PREVENT REVERSED DATE RANGE
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # =====================================================
    # DATE/TIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # EXPENSE QUERY
    # =====================================================

    expense_query = Expense.query.filter(
        Expense.company_id == company_id,

        Expense.expense_date >= start_datetime,

        Expense.expense_date <= end_datetime
    )

    expenses = (
        expense_query
        .order_by(
            Expense.expense_date.desc()
        )
        .all()
    )

    # =====================================================
    # TOTAL EXPENSES
    # =====================================================

    total_expenses = money(
        db.session.query(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            )
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .scalar()
    )

    total_expense_count = (
        expense_query.count()
    )

    # =====================================================
    # AVERAGE EXPENSE
    #
    # Keep calculations as Decimal.
    # =====================================================

    expense_count_decimal = Decimal(
        str(total_expense_count)
    )

    average_expense = (
        total_expenses
        / expense_count_decimal
        if total_expense_count > 0
        else Decimal("0")
    )

    # =====================================================
    # PAYMENT METHOD BREAKDOWN
    # =====================================================

    payment_method_rows = (
        db.session.query(
            Expense.payment_method.label(
                "method"
            ),

            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            ).label("total")
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .group_by(
            Expense.payment_method
        )
        .all()
    )

    payment_method_chart = []

    for row in payment_method_rows:

        amount = money(
            row.total
        )

        percentage = (
            (
                amount
                / total_expenses
            )
            * Decimal("100")
            if total_expenses > Decimal("0")
            else Decimal("0")
        )

        payment_method_chart.append(
            {
                "method": (
                    row.method
                    or "Unknown"
                ),

                # Chart.js needs JSON-compatible numbers
                "total": float(amount),

                "percentage": float(
                    percentage
                )
            }
        )

    # =====================================================
    # CATEGORY BREAKDOWN
    # =====================================================

    category_data = {}

    for expense in expenses:

        category_name = (
            expense.category.name
            if expense.category
            else "Uncategorized"
        )

        if category_name not in category_data:

            category_data[category_name] = {
                "category": category_name,

                "count": 0,

                "total": Decimal("0")
            }

        category_data[
            category_name
        ]["count"] += 1

        category_data[
            category_name
        ]["total"] += money(
            expense.amount
        )

    # =====================================================
    # SORT CATEGORY BREAKDOWN
    # =====================================================

    category_breakdown = sorted(
        category_data.values(),

        key=lambda row: row["total"],

        reverse=True
    )

    # =====================================================
    # CATEGORY PERCENTAGES
    # =====================================================

    for row in category_breakdown:

        if total_expenses > Decimal("0"):

            row["percentage"] = (
                row["total"]
                / total_expenses
                * Decimal("100")
            )

        else:

            row["percentage"] = Decimal("0")

    # =====================================================
    # CATEGORY CHART
    #
    # Convert Decimal to float ONLY for Chart.js.
    # =====================================================

    category_chart = [
        {
            "category": row["category"],

            "total": float(
                row["total"]
            )
        }

        for row in category_breakdown
    ]

    # =====================================================
    # DAILY EXPENSE TREND
    #
    # Only dates with actual expenses.
    # =====================================================

    daily_expense_rows = (
        db.session.query(
            func.date(
                Expense.expense_date
            ).label("date"),

            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            ).label("total")
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .group_by(
            func.date(
                Expense.expense_date
            )
        )
        .order_by(
            func.date(
                Expense.expense_date
            )
        )
        .all()
    )

    daily_expense_trend = []

    for row in daily_expense_rows:

        if hasattr(
            row.date,
            "strftime"
        ):

            date_label = row.date.strftime(
                "%d %b"
            )

        else:

            date_label = str(
                row.date
            )

        daily_expense_trend.append(
            {
                "date": date_label,

                "total": float(
                    money(row.total)
                )
            }
        )

    # =====================================================
    # LARGEST CATEGORY
    # =====================================================

    if category_breakdown:

        largest_category = (
            category_breakdown[0]
        )

        largest_category_name = (
            largest_category["category"]
        )

        largest_category_amount = (
            largest_category["total"]
        )

    else:

        largest_category_name = "None"

        largest_category_amount = (
            Decimal("0")
        )

    # =====================================================
    # LARGEST EXPENSE
    # =====================================================

    if expenses:

        largest_expense = max(
            expenses,

            key=lambda expense: money(
                expense.amount
            )
        )

        largest_expense_amount = money(
            largest_expense.amount
        )

        largest_expense_description = (
            largest_expense.description
            or largest_expense.expense_number
            or "Expense"
        )

    else:

        largest_expense_amount = (
            Decimal("0")
        )

        largest_expense_description = (
            "None"
        )

    # =====================================================
    # EXPORT ROWS
    # =====================================================

    export_rows = []

    for expense in expenses:

        category_name = (
            expense.category.name
            if expense.category
            else "Uncategorized"
        )

        export_rows.append(
            {
                "date": expense.expense_date,

                "expense_number": (
                    expense.expense_number
                ),

                "category": category_name,

                "description": (
                    expense.description
                    or ""
                ),

                "payment_method": (
                    expense.payment_method
                    or "Unknown"
                ),

                "amount": money(
                    expense.amount
                )
            }
        )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "reports/expense_report.html",

        # -------------------------------------------------
        # DATE RANGE
        # -------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # EXPENSE TOTALS
        # -------------------------------------------------

        total_expenses=total_expenses,

        total_expense_count=(
            total_expense_count
        ),

        average_expense=average_expense,

        # -------------------------------------------------
        # PAYMENT METHOD
        # -------------------------------------------------

        payment_method_chart=(
            payment_method_chart
        ),

        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        category_breakdown=(
            category_breakdown
        ),

        category_chart=category_chart,

        # -------------------------------------------------
        # DAILY TREND
        # -------------------------------------------------

        daily_expense_trend=(
            daily_expense_trend
        ),

        # -------------------------------------------------
        # LARGEST CATEGORY
        # -------------------------------------------------

        largest_category_name=(
            largest_category_name
        ),

        largest_category_amount=(
            largest_category_amount
        ),

        # -------------------------------------------------
        # LARGEST EXPENSE
        # -------------------------------------------------

        largest_expense_amount=(
            largest_expense_amount
        ),

        largest_expense_description=(
            largest_expense_description
        ),

        # -------------------------------------------------
        # EXPORT
        # -------------------------------------------------

        export_rows=export_rows
    )

@reports_bp.route("/inventory")
@company_permission_required("view_reports")
def inventory_report():

    # ============================================================
    # CURRENT COMPANY SETTINGS
    # ============================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone
    report_date = datetime.now(
        company_timezone
    ).date()

    # ============================================================
    # CURRENT COMPANY INVENTORY
    # ============================================================

    products = (
        Product.query
        .filter(
            Product.company_id == company_id,
            Product.is_active.is_(True)
        )
        .order_by(
            Product.name.asc()
        )
        .all()
    )

    # ============================================================
    # SUMMARY TOTALS
    # ============================================================

    total_products = len(products)

    total_quantity = sum(
        (
            money(product.quantity)
            for product in products
        ),
        Decimal("0")
    )

    total_stock_value = sum(
        (
            money(product.quantity)
            * money(product.purchase_price)
            for product in products
        ),
        Decimal("0")
    )

    total_selling_value = sum(
        (
            money(product.quantity)
            * money(product.selling_price)
            for product in products
        ),
        Decimal("0")
    )

    # ============================================================
    # STOCK STATUS
    # ============================================================

    low_stock_products = [
        product
        for product in products
        if (
            money(product.quantity)
            <= money(product.minimum_stock)
            and money(product.quantity)
            > Decimal("0")
        )
    ]

    out_of_stock_products = [
        product
        for product in products
        if money(product.quantity)
        <= Decimal("0")
    ]

    healthy_stock_products = [
        product
        for product in products
        if (
            money(product.quantity)
            > money(product.minimum_stock)
        )
    ]

    low_stock_count = len(
        low_stock_products
    )

    out_of_stock_count = len(
        out_of_stock_products
    )

    healthy_stock_count = len(
        healthy_stock_products
    )

    # ============================================================
    # POTENTIAL STOCK PROFIT
    # ============================================================

    potential_profit = (
        total_selling_value
        - total_stock_value
    )

    # ============================================================
    # CATEGORY BREAKDOWN
    # ============================================================

    category_data = {}

    for product in products:

        category_name = (
            product.category.name
            if product.category
            else "Uncategorized"
        )

        if category_name not in category_data:

            category_data[category_name] = {
                "category": category_name,
                "products": 0,
                "quantity": Decimal("0"),
                "stock_value": Decimal("0")
            }

        row = category_data[
            category_name
        ]

        quantity = money(
            product.quantity
        )

        purchase_price = money(
            product.purchase_price
        )

        row["products"] += 1

        row["quantity"] += quantity

        row["stock_value"] += (
            quantity * purchase_price
        )

    category_breakdown = sorted(
        category_data.values(),
        key=lambda row: row["stock_value"],
        reverse=True
    )

    # ============================================================
    # CATEGORY PERCENTAGES
    # ============================================================

    for row in category_breakdown:

        row["percentage"] = (
            (
                row["stock_value"]
                / total_stock_value
            )
            * Decimal("100")

            if total_stock_value
            > Decimal("0")

            else Decimal("0")
        )

    # ============================================================
    # STOCK LEVEL DISTRIBUTION
    # ============================================================

    stock_level_chart = [
        {
            "status": "Healthy Stock",
            "count": healthy_stock_count
        },
        {
            "status": "Low Stock",
            "count": low_stock_count
        },
        {
            "status": "Out of Stock",
            "count": out_of_stock_count
        }
    ]

    # ============================================================
    # TOP PRODUCTS BY STOCK VALUE
    # ============================================================

    product_value_data = []

    for product in products:

        quantity = money(
            product.quantity
        )

        purchase_price = money(
            product.purchase_price
        )

        stock_value = (
            quantity * purchase_price
        )

        product_value_data.append(
            {
                "product": product.name,
                "sku": product.sku,
                "quantity": quantity,
                "stock_value": stock_value
            }
        )

    product_value_data.sort(
        key=lambda row: row["stock_value"],
        reverse=True
    )

    top_products = (
        product_value_data[:10]
    )

    # ============================================================
    # DETAILED INVENTORY ROWS
    # ============================================================

    inventory_rows = []

    for product in products:

        quantity = money(
            product.quantity
        )

        purchase_price = money(
            product.purchase_price
        )

        selling_price = money(
            product.selling_price
        )

        minimum_stock = money(
            product.minimum_stock
        )

        # --------------------------------------------------------
        # STOCK VALUE
        # --------------------------------------------------------

        stock_value = (
            quantity * purchase_price
        )

        # --------------------------------------------------------
        # SELLING VALUE
        # --------------------------------------------------------

        selling_value = (
            quantity * selling_price
        )

        # --------------------------------------------------------
        # POTENTIAL PROFIT
        # --------------------------------------------------------

        product_potential_profit = (
            selling_value
            - stock_value
        )

        # --------------------------------------------------------
        # STOCK STATUS
        # --------------------------------------------------------

        if quantity <= Decimal("0"):

            stock_status = "Out of Stock"

        elif quantity <= minimum_stock:

            stock_status = "Low Stock"

        else:

            stock_status = "Healthy"

        # --------------------------------------------------------
        # CATEGORY
        # --------------------------------------------------------

        category_name = (
            product.category.name
            if product.category
            else "Uncategorized"
        )

        # --------------------------------------------------------
        # INVENTORY ROW
        # --------------------------------------------------------

        inventory_rows.append(
            {
                "product": product.name,
                "sku": product.sku,
                "category": category_name,

                "unit": (
                    product.unit
                    or "piece"
                ),

                "quantity": quantity,

                "minimum_stock": (
                    minimum_stock
                ),

                "purchase_price": (
                    purchase_price
                ),

                "selling_price": (
                    selling_price
                ),

                "stock_value": (
                    stock_value
                ),

                "selling_value": (
                    selling_value
                ),

                "potential_profit": (
                    product_potential_profit
                ),

                "status": stock_status
            }
        )

    # ============================================================
    # EXPORT ROWS
    # ============================================================

    export_rows = inventory_rows

    # ============================================================
    # REPORT DATE
    # ============================================================

    report_date_string = (
        report_date.strftime("%Y-%m-%d")
    )

    # ============================================================
    # RENDER REPORT
    # ============================================================

    return render_template(
        "reports/inventory_report.html",

        # --------------------------------------------------------
        # COMPANY SETTINGS
        # --------------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # --------------------------------------------------------
        # REPORT DATE
        # --------------------------------------------------------

        report_date=report_date_string,

        # --------------------------------------------------------
        # SUMMARY
        # --------------------------------------------------------

        total_products=total_products,

        total_quantity=total_quantity,

        total_stock_value=total_stock_value,

        total_selling_value=total_selling_value,

        potential_profit=potential_profit,

        # --------------------------------------------------------
        # STOCK STATUS
        # --------------------------------------------------------

        low_stock_count=low_stock_count,

        out_of_stock_count=out_of_stock_count,

        healthy_stock_count=healthy_stock_count,

        # --------------------------------------------------------
        # CHART DATA
        # --------------------------------------------------------

        category_breakdown=category_breakdown,

        stock_level_chart=stock_level_chart,

        top_products=top_products,

        # --------------------------------------------------------
        # INVENTORY DATA
        # --------------------------------------------------------

        inventory_rows=inventory_rows,

        export_rows=export_rows
    )

# ============================================================
# STAFF REPORT
# ============================================================

@reports_bp.route("/staff")
@company_permission_required("view_reports")
def staff_report():

    # ============================================================
    # CURRENT COMPANY SETTINGS
    # ============================================================

    settings = get_current_company_settings()
    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's configured timezone
    today = datetime.now(
        company_timezone
    ).date()

    # ============================================================
    # DATE RANGE
    # ============================================================

    default_start = today.replace(
        day=1
    )

    start_date = (
        parse_date(
            request.args.get("start_date")
        )
        or default_start
    )

    end_date = (
        parse_date(
            request.args.get("end_date")
        )
        or today
    )

    # ============================================================
    # PREVENT REVERSED DATE RANGE
    # ============================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # ============================================================
    # DATE/TIME RANGE
    # ============================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # ============================================================
    # STAFF
    # ============================================================

    staff_users = (
        User.query
        .filter(
            User.company_id == company_id
        )
        .order_by(
            User.username.asc()
        )
        .all()
    )

    total_staff = len(
        staff_users
    )

    active_staff_count = sum(
        1
        for user in staff_users
        if user.is_active
    )

    inactive_staff_count = (
        total_staff
        - active_staff_count
    )

    # ============================================================
    # SALES BY STAFF
    # ============================================================

    sales_rows = (
        db.session.query(
            Sale.created_by.label(
                "user_id"
            ),

            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            ).label(
                "total_sales"
            ),

            func.count(
                Sale.id
            ).label(
                "sales_count"
            ),

            func.coalesce(
                func.sum(
                    Sale.paid_amount
                ),
                0
            ).label(
                "paid_amount"
            )
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            Sale.created_by
        )
        .all()
    )

    sales_by_user = {}

    for row in sales_rows:

        sales_by_user[row.user_id] = {
            "total_sales": money(
                row.total_sales
            ),

            "sales_count": (
                row.sales_count or 0
            ),

            "paid_amount": money(
                row.paid_amount
            )
        }

    # ============================================================
    # PAYMENTS BY STAFF
    # ============================================================

    payment_rows = (
        db.session.query(
            Payment.created_by.label(
                "user_id"
            ),

            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            ).label(
                "total_payments"
            ),

            func.count(
                Payment.id
            ).label(
                "payment_count"
            )
        )
        .filter(
            Payment.company_id == company_id,

            # Only customer payments against sales
            Payment.sale_id.isnot(None),

            Payment.payment_date >= start_datetime,

            Payment.payment_date <= end_datetime
        )
        .group_by(
            Payment.created_by
        )
        .all()
    )

    payments_by_user = {}

    for row in payment_rows:

        payments_by_user[row.user_id] = {
            "total_payments": money(
                row.total_payments
            ),

            "payment_count": (
                row.payment_count or 0
            )
        }

    # ============================================================
    # EXPENSES BY STAFF
    # ============================================================

    expense_rows = (
        db.session.query(
            Expense.created_by.label(
                "user_id"
            ),

            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            ).label(
                "total_expenses"
            ),

            func.count(
                Expense.id
            ).label(
                "expense_count"
            )
        )
        .filter(
            Expense.company_id == company_id,

            Expense.expense_date >= start_datetime,

            Expense.expense_date <= end_datetime
        )
        .group_by(
            Expense.created_by
        )
        .all()
    )

    expenses_by_user = {}

    for row in expense_rows:

        expenses_by_user[row.user_id] = {
            "total_expenses": money(
                row.total_expenses
            ),

            "expense_count": (
                row.expense_count or 0
            )
        }

    # ============================================================
    # STAFF BREAKDOWN
    # ============================================================

    staff_breakdown = []

    for user in staff_users:

        sales_data = sales_by_user.get(
            user.id,
            {
                "total_sales": Decimal("0"),
                "sales_count": 0,
                "paid_amount": Decimal("0")
            }
        )

        payment_data = payments_by_user.get(
            user.id,
            {
                "total_payments": Decimal("0"),
                "payment_count": 0
            }
        )

        expense_data = expenses_by_user.get(
            user.id,
            {
                "total_expenses": Decimal("0"),
                "expense_count": 0
            }
        )

        # ========================================================
        # USER ROLES
        # ========================================================

        roles = []

        for user_role in user.user_roles:

            if user_role.role:

                roles.append(
                    user_role.role.name
                )

        role_name = (
            ", ".join(roles)
            if roles
            else user.role or "Staff"
        )

        # ========================================================
        # TOTAL TRANSACTIONS
        # ========================================================

        total_transactions = (
            sales_data["sales_count"]
            + payment_data["payment_count"]
            + expense_data["expense_count"]
        )

        # ========================================================
        # STAFF ROW
        # ========================================================

        staff_breakdown.append(
            {
                "username": user.username,

                "email": (
                    user.email
                    or "—"
                ),

                "role": role_name,

                "status": (
                    "Active"
                    if user.is_active
                    else "Inactive"
                ),

                "sales_count": (
                    sales_data["sales_count"]
                ),

                "total_sales": (
                    sales_data["total_sales"]
                ),

                "paid_sales": (
                    sales_data["paid_amount"]
                ),

                "payment_count": (
                    payment_data["payment_count"]
                ),

                "total_payments": (
                    payment_data["total_payments"]
                ),

                "expense_count": (
                    expense_data["expense_count"]
                ),

                "total_expenses": (
                    expense_data["total_expenses"]
                ),

                "total_transactions": (
                    total_transactions
                )
            }
        )

    # ============================================================
    # SUMMARY TOTALS
    # ============================================================

    total_sales = sum(
        (
            row["total_sales"]
            for row in staff_breakdown
        ),
        Decimal("0")
    )

    total_sales_count = sum(
        row["sales_count"]
        for row in staff_breakdown
    )

    total_payments = sum(
        (
            row["total_payments"]
            for row in staff_breakdown
        ),
        Decimal("0")
    )

    total_payment_count = sum(
        row["payment_count"]
        for row in staff_breakdown
    )

    total_expenses = sum(
        (
            row["total_expenses"]
            for row in staff_breakdown
        ),
        Decimal("0")
    )

    total_expense_count = sum(
        row["expense_count"]
        for row in staff_breakdown
    )

    total_transactions = sum(
        row["total_transactions"]
        for row in staff_breakdown
    )

    # ============================================================
    # SALES PERFORMANCE CHART
    # ============================================================

    sales_performance = sorted(
        staff_breakdown,

        key=lambda row:
        row["total_sales"],

        reverse=True
    )

    sales_chart = [
        {
            "staff": row["username"],

            "total": float(
                row["total_sales"]
            )
        }

        for row in sales_performance

        if row["total_sales"]
        > Decimal("0")
    ]

    # ============================================================
    # TRANSACTION ACTIVITY CHART
    # ============================================================

    activity_chart = sorted(
        staff_breakdown,

        key=lambda row:
        row["total_transactions"],

        reverse=True
    )

    activity_chart = [
        {
            "staff": row["username"],

            "transactions": (
                row["total_transactions"]
            )
        }

        for row in activity_chart

        if row["total_transactions"] > 0
    ]

    # ============================================================
    # ROLE BREAKDOWN
    # ============================================================

    role_data = {}

    for row in staff_breakdown:

        roles = row["role"].split(",")

        for role in roles:

            role = role.strip()

            if not role:
                continue

            role_data[role] = (
                role_data.get(
                    role,
                    0
                ) + 1
            )

    role_chart = [
        {
            "role": role,
            "count": count
        }

        for role, count in sorted(
            role_data.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ]

    # ============================================================
    # EXPORT ROWS
    # ============================================================

    export_rows = staff_breakdown

    # ============================================================
    # RENDER
    # ============================================================

    return render_template(
        "reports/staff_report.html",

        # --------------------------------------------------------
        # DATE RANGE
        # --------------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # --------------------------------------------------------
        # COMPANY SETTINGS
        # --------------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # --------------------------------------------------------
        # STAFF
        # --------------------------------------------------------

        total_staff=total_staff,

        active_staff_count=active_staff_count,

        inactive_staff_count=(
            inactive_staff_count
        ),

        # --------------------------------------------------------
        # SALES
        # --------------------------------------------------------

        total_sales=total_sales,

        total_sales_count=(
            total_sales_count
        ),

        # --------------------------------------------------------
        # PAYMENTS
        # --------------------------------------------------------

        total_payments=total_payments,

        total_payment_count=(
            total_payment_count
        ),

        # --------------------------------------------------------
        # EXPENSES
        # --------------------------------------------------------

        total_expenses=total_expenses,

        total_expense_count=(
            total_expense_count
        ),

        # --------------------------------------------------------
        # TRANSACTIONS
        # --------------------------------------------------------

        total_transactions=(
            total_transactions
        ),

        # --------------------------------------------------------
        # CHARTS
        # --------------------------------------------------------

        sales_chart=sales_chart,

        activity_chart=activity_chart,

        role_chart=role_chart,

        # --------------------------------------------------------
        # STAFF DATA
        # --------------------------------------------------------

        staff_breakdown=staff_breakdown,

        export_rows=export_rows
    )

@reports_bp.route("/customers")
@company_permission_required("view_reports")
def customer_report():

    # ============================================================
    # CURRENT COMPANY
    # ============================================================

    company_id = current_user.company_id

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    # ============================================================
    # DATE RANGE
    # ============================================================

    # Use the current company's configured timezone.
    today = datetime.now(
        company_timezone
    ).date()

    default_start = today.replace(
        day=1
    )

    start_date = (
        parse_date(
            request.args.get("start_date")
        )
        or default_start
    )

    end_date = (
        parse_date(
            request.args.get("end_date")
        )
        or today
    )

    # ============================================================
    # PREVENT REVERSED DATE RANGE
    # ============================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # ============================================================
    # DATETIME RANGE
    # ============================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # ============================================================
    # CUSTOMERS
    # ============================================================

    customers = (
        Customer.query
        .filter(
            Customer.company_id == company_id
        )
        .order_by(
            Customer.name.asc()
        )
        .all()
    )

    total_customers = len(
        customers
    )

    active_customer_count = sum(
        1
        for customer in customers
        if customer.is_active
    )

    inactive_customer_count = (
        total_customers
        - active_customer_count
    )

    # ============================================================
    # SALES BY CUSTOMER
    # ============================================================

    sales_rows = (
        db.session.query(
            Sale.customer_id.label(
                "customer_id"
            ),

            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0
            ).label(
                "total_sales"
            ),

            func.coalesce(
                func.sum(
                    Sale.paid_amount
                ),
                0
            ).label(
                "total_paid"
            ),

            func.coalesce(
                func.sum(
                    Sale.balance
                ),
                0
            ).label(
                "total_balance"
            ),

            func.count(
                Sale.id
            ).label(
                "sale_count"
            )
        )
        .filter(
            Sale.company_id == company_id,

            Sale.sale_date >= start_datetime,

            Sale.sale_date <= end_datetime
        )
        .group_by(
            Sale.customer_id
        )
        .all()
    )

    # ============================================================
    # MAP SALES DATA TO CUSTOMER
    # ============================================================

    sales_by_customer = {}

    for row in sales_rows:

        sales_by_customer[
            row.customer_id
        ] = {

            "total_sales": money(
                row.total_sales
            ),

            "total_paid": money(
                row.total_paid
            ),

            "total_balance": money(
                row.total_balance
            ),

            "sale_count": (
                row.sale_count or 0
            )
        }

    # ============================================================
    # CUSTOMER BREAKDOWN
    # ============================================================

    customer_breakdown = []

    for customer in customers:

        sales_data = sales_by_customer.get(
            customer.id,
            {
                "total_sales": Decimal("0"),
                "total_paid": Decimal("0"),
                "total_balance": Decimal("0"),
                "sale_count": 0
            }
        )

        total_customer_sales = (
            sales_data["total_sales"]
        )

        total_customer_paid = (
            sales_data["total_paid"]
        )

        total_customer_balance = (
            sales_data["total_balance"]
        )

        sale_count = (
            sales_data["sale_count"]
        )

        # --------------------------------------------------------
        # CUSTOMER STATUS
        # --------------------------------------------------------

        if sale_count > 0:

            customer_status = "Customer"

        else:

            customer_status = "No Sales"

        # --------------------------------------------------------
        # CUSTOMER ROW
        # --------------------------------------------------------

        customer_breakdown.append(
            {
                "customer": customer.name,

                "email": (
                    customer.email
                    or "—"
                ),

                "phone": (
                    customer.phone
                    or "—"
                ),

                "status": (
                    "Active"
                    if customer.is_active
                    else "Inactive"
                ),

                "customer_status": (
                    customer_status
                ),

                "sale_count": sale_count,

                "total_sales": (
                    total_customer_sales
                ),

                "total_paid": (
                    total_customer_paid
                ),

                "total_balance": (
                    total_customer_balance
                )
            }
        )

    # ============================================================
    # SUMMARY TOTALS
    # ============================================================

    customers_with_sales = sum(
        1
        for row in customer_breakdown
        if row["sale_count"] > 0
    )

    total_sales = sum(
        (
            row["total_sales"]
            for row in customer_breakdown
        ),
        Decimal("0")
    )

    total_paid = sum(
        (
            row["total_paid"]
            for row in customer_breakdown
        ),
        Decimal("0")
    )

    total_receivables = sum(
        (
            row["total_balance"]
            for row in customer_breakdown
        ),
        Decimal("0")
    )

    total_sales_count = sum(
        row["sale_count"]
        for row in customer_breakdown
    )

    # ============================================================
    # AVERAGE CUSTOMER SALE
    # ============================================================

    average_customer_sale = (

        total_sales
        / Decimal(
            str(customers_with_sales)
        )

        if customers_with_sales > 0

        else Decimal("0")
    )

    # ============================================================
    # TOP CUSTOMERS
    # ============================================================

    top_customers = sorted(
        customer_breakdown,

        key=lambda row: (
            row["total_sales"]
        ),

        reverse=True
    )

    # ============================================================
    # TOP CUSTOMERS CHART
    #
    # Keep chart values numeric.
    # Currency formatting should happen in JavaScript.
    # ============================================================

    top_customers_chart = [

        {
            "customer": row["customer"],

            "total": float(
                row["total_sales"]
            )
        }

        for row in top_customers[:10]

        if row["total_sales"] > Decimal("0")
    ]

    # ============================================================
    # CUSTOMER PAYMENT STATUS
    # ============================================================

    fully_paid_customers = sum(
        1
        for row in customer_breakdown
        if (
            row["sale_count"] > 0
            and row["total_balance"] <= Decimal("0")
        )
    )

    customers_with_balance = sum(
        1
        for row in customer_breakdown
        if (
            row["total_balance"]
            > Decimal("0")
        )
    )

    customer_payment_chart = [

        {
            "status": "Fully Paid",
            "count": fully_paid_customers
        },

        {
            "status": "Outstanding",
            "count": customers_with_balance
        }
    ]

    # ============================================================
    # CUSTOMER SALES SHARE
    # ============================================================

    for row in customer_breakdown:

        row["percentage"] = (

            (
                row["total_sales"]
                / total_sales
            )
            * Decimal("100")

            if total_sales > Decimal("0")

            else Decimal("0")
        )

    # ============================================================
    # EXPORT ROWS
    # ============================================================

    export_rows = customer_breakdown

    # ============================================================
    # RENDER CUSTOMER REPORT
    # ============================================================

    return render_template(

        "reports/customer_report.html",

        # --------------------------------------------------------
        # DATE RANGE
        # --------------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # --------------------------------------------------------
        # COMPANY SETTINGS
        # --------------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # --------------------------------------------------------
        # CUSTOMER SUMMARY
        # --------------------------------------------------------

        total_customers=total_customers,

        active_customer_count=(
            active_customer_count
        ),

        inactive_customer_count=(
            inactive_customer_count
        ),

        customers_with_sales=(
            customers_with_sales
        ),

        # --------------------------------------------------------
        # SALES SUMMARY
        # --------------------------------------------------------

        total_sales=total_sales,

        total_paid=total_paid,

        total_receivables=(
            total_receivables
        ),

        total_sales_count=(
            total_sales_count
        ),

        average_customer_sale=(
            average_customer_sale
        ),

        # --------------------------------------------------------
        # CHART DATA
        # --------------------------------------------------------

        top_customers_chart=(
            top_customers_chart
        ),

        customer_payment_chart=(
            customer_payment_chart
        ),

        # --------------------------------------------------------
        # CUSTOMER DATA
        # --------------------------------------------------------

        customer_breakdown=(
            customer_breakdown
        ),

        export_rows=export_rows
    )

# =========================================================
# CASH DEPOSIT REPORT
# =========================================================

@reports_bp.route("/cash-deposits")
@company_permission_required("view_reports")
def cash_deposit_report():

    # =====================================================
    # CURRENT COMPANY SETTINGS
    # =====================================================

    settings = get_current_company_settings()

    company_timezone = get_company_timezone()

    company_id = current_user.company_id

    # Use the company's timezone for "today"
    today = datetime.now(
        company_timezone
    ).date()

    # =====================================================
    # DATE RANGE
    # =====================================================

    default_start = today.replace(
        day=1
    )

    start_date = (
        parse_date(
            request.args.get("start_date")
        )
        or default_start
    )

    end_date = (
        parse_date(
            request.args.get("end_date")
        )
        or today
    )

    # =====================================================
    # PREVENT REVERSED DATES
    # =====================================================

    if start_date > end_date:

        start_date, end_date = (
            end_date,
            start_date
        )

    # =====================================================
    # REPORT DATE/TIME RANGE
    # =====================================================

    start_datetime = datetime.combine(
        start_date,
        time.min
    )

    end_datetime = datetime.combine(
        end_date,
        time.max
    )

    # =====================================================
    # CASH SALES PAYMENTS
    #
    # Only customer payments connected to sales.
    #
    # Only CASH payments are included.
    # =====================================================

    cash_payments_query = Payment.query.filter(
        Payment.company_id == company_id,

        Payment.sale_id.isnot(None),

        func.lower(
            func.trim(
                Payment.method
            )
        ) == "cash",

        Payment.payment_date >= start_datetime,

        Payment.payment_date <= end_datetime
    )

    # =====================================================
    # TOTAL CASH RECEIVED
    # =====================================================

    total_cash_received = money(
        cash_payments_query
        .with_entities(
            func.coalesce(
                func.sum(
                    Payment.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # CASH EXPENSES
    #
    # Only expenses paid using CASH are deducted from
    # the cash available for deposit.
    # =====================================================

    cash_expenses_query = Expense.query.filter(
        Expense.company_id == company_id,

        func.lower(
            func.trim(
                Expense.payment_method
            )
        ) == "cash",

        Expense.expense_date >= start_datetime,

        Expense.expense_date <= end_datetime
    )

    # =====================================================
    # TOTAL CASH EXPENSES
    # =====================================================

    total_cash_expenses = money(
        cash_expenses_query
        .with_entities(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # CASH AFTER EXPENSES
    #
    # Cash received minus cash expenses.
    # =====================================================

    net_cash_before_deposits = (
        total_cash_received
        - total_cash_expenses
    )

    # =====================================================
    # CASH DEPOSITS
    #
    # Deposits recorded during the selected period.
    # =====================================================

    deposits_query = CashDeposit.query.filter(
        CashDeposit.company_id == company_id,

        CashDeposit.deposit_date >= start_datetime,

        CashDeposit.deposit_date <= end_datetime
    )

    # =====================================================
    # DEPOSITS
    # =====================================================

    deposits = (
        deposits_query
        .order_by(
            CashDeposit.deposit_date.desc(),
            CashDeposit.id.desc()
        )
        .all()
    )

    # =====================================================
    # TOTAL DEPOSITED
    # =====================================================

    total_cash_deposited = money(
        deposits_query
        .with_entities(
            func.coalesce(
                func.sum(
                    CashDeposit.amount
                ),
                0
            )
        )
        .scalar()
    )

    # =====================================================
    # CASH AVAILABLE
    #
    # Cash received
    # minus cash expenses
    # minus cash already deposited.
    # =====================================================

    cash_available = (
        total_cash_received
        - total_cash_expenses
        - total_cash_deposited
    )

    # Never display a negative amount as money available
    # for a new deposit.
    if cash_available < Decimal("0"):

        cash_available = Decimal("0")

    # =====================================================
    # NUMBER OF DEPOSITS
    # =====================================================

    deposit_count = (
        deposits_query.count()
    )

    # =====================================================
    # BANK BREAKDOWN
    # =====================================================

    bank_rows = (
        db.session.query(
            CashDeposit.bank_name.label(
                "bank_name"
            ),

            func.coalesce(
                func.sum(
                    CashDeposit.amount
                ),
                0
            ).label(
                "total"
            ),

            func.count(
                CashDeposit.id
            ).label(
                "count"
            )
        )
        .filter(
            CashDeposit.company_id == company_id,

            CashDeposit.deposit_date >= start_datetime,

            CashDeposit.deposit_date <= end_datetime
        )
        .group_by(
            CashDeposit.bank_name
        )
        .order_by(
            func.sum(
                CashDeposit.amount
            ).desc()
        )
        .all()
    )

    bank_breakdown = [

        {
            "bank": (
                row.bank_name
                or "Bank Not Specified"
            ),

            "total": money(
                row.total
            ),

            "count": (
                row.count
                or 0
            )
        }

        for row in bank_rows

    ]

    # =====================================================
    # DAILY DEPOSIT TREND
    # =====================================================

    daily_deposit_rows = (
        db.session.query(
            func.date(
                CashDeposit.deposit_date
            ).label(
                "date"
            ),

            func.coalesce(
                func.sum(
                    CashDeposit.amount
                ),
                0
            ).label(
                "total"
            )
        )
        .filter(
            CashDeposit.company_id == company_id,

            CashDeposit.deposit_date >= start_datetime,

            CashDeposit.deposit_date <= end_datetime
        )
        .group_by(
            func.date(
                CashDeposit.deposit_date
            )
        )
        .order_by(
            func.date(
                CashDeposit.deposit_date
            )
        )
        .all()
    )

    daily_deposit_trend = [

        {
            "date": (
                row.date.strftime("%d %b")
                if hasattr(
                    row.date,
                    "strftime"
                )
                else str(row.date)
            ),

            "total": float(
                money(
                    row.total
                )
            )
        }

        for row in daily_deposit_rows

    ]

    # =====================================================
    # DEPOSIT RATE
    #
    # Percentage of NET CASH available before deposits
    # that has been deposited.
    #
    # Net cash before deposits =
    # Cash Received - Cash Expenses
    # =====================================================

    if net_cash_before_deposits > Decimal("0"):

        deposit_percentage = (
            total_cash_deposited
            / net_cash_before_deposits
            * Decimal("100")
        )

    else:

        deposit_percentage = Decimal("0")

    # =====================================================
    # EXPORT ROWS
    # =====================================================

    export_rows = []

    for deposit in deposits:

        # -------------------------------------------------
        # Recorded by
        # -------------------------------------------------

        recorded_by = "—"

        if deposit.created_by:

            user = (
                User.query
                .filter(
                    User.id
                    == deposit.created_by
                )
                .first()
            )

            if user:

                recorded_by = (
                    user.username
                )

        # -------------------------------------------------
        # Bank
        # -------------------------------------------------

        bank_name = (
            deposit.bank_name
            or "Bank Not Specified"
        )

        # -------------------------------------------------
        # Reference
        # -------------------------------------------------

        reference = (
            deposit.reference
            or "—"
        )

        # -------------------------------------------------
        # Notes
        # -------------------------------------------------

        notes = (
            deposit.notes
            or "—"
        )

        # -------------------------------------------------
        # Export row
        # -------------------------------------------------

        export_rows.append(
            {
                "date": deposit.deposit_date,

                "bank": bank_name,

                "amount": money(
                    deposit.amount
                ),

                "reference": reference,

                "recorded_by": recorded_by,

                "notes": notes
            }
        )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "reports/cash_deposit_report.html",

        # -------------------------------------------------
        # COMPANY SETTINGS
        # -------------------------------------------------

        company_settings=settings,

        company_timezone=company_timezone,

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        start_date=start_date.strftime(
            "%Y-%m-%d"
        ),

        end_date=end_date.strftime(
            "%Y-%m-%d"
        ),

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        total_cash_received=(
            total_cash_received
        ),

        total_cash_expenses=(
            total_cash_expenses
        ),

        total_cash_deposited=(
            total_cash_deposited
        ),

        net_cash_before_deposits=(
            net_cash_before_deposits
        ),

        cash_available=(
            cash_available
        ),

        deposit_count=(
            deposit_count
        ),

        deposit_percentage=(
            deposit_percentage
        ),

        # -------------------------------------------------
        # BANK BREAKDOWN
        # -------------------------------------------------

        bank_breakdown=(
            bank_breakdown
        ),

        # -------------------------------------------------
        # DAILY TREND
        # -------------------------------------------------

        daily_deposit_trend=(
            daily_deposit_trend
        ),

        # -------------------------------------------------
        # DEPOSITS
        # -------------------------------------------------

        deposits=deposits,

        # -------------------------------------------------
        # EXPORT
        # -------------------------------------------------

        export_rows=export_rows
    )
