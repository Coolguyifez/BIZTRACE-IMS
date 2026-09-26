from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)

from flask_login import login_required, current_user

from app.extensions import db

from app.models import (
    Product,
    Customer,
    Company,
    Sale,
    SaleItem,
    Payment,
    InventoryTransaction
)

from app.notifications.service import (
    notify_success,
    notify_low_stock,
    check_financial_alerts
)

from app.company_admin.decorators import company_permission_required

from app.utils.document_numbers import (
    generate_invoice_number
)

from app.utils.company_settings import (
    get_current_company_settings,
    get_company_timezone,
    company_now,
    format_currency
)

from .forms import SaleForm


sales_bp = Blueprint(
    "sales",
    __name__,
    url_prefix="/sales"
)


# ============================================================
# DECIMAL HELPER
# ============================================================

def parse_decimal(
    value,
    default=Decimal("0.00")
):
    try:
        if (
            value is None
            or str(value).strip() == ""
        ):
            return default

        return Decimal(
            str(value)
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):
        return None


# ============================================================
# COMPANY SETTINGS
# ============================================================

def get_sales_company_settings():
    """
    Return the settings belonging to the currently
    authenticated user's company.

    System Administrators do not have a company and
    therefore do not receive company financial settings.
    """

    return get_current_company_settings()


# ============================================================
# DATE/TIME HELPERS
# ============================================================

def company_date_to_utc_start(selected_date):
    """
    Convert a company-local calendar date to the
    corresponding UTC start datetime.

    Example:

        Company timezone:
        Africa/Lagos

        Local:
        2026-09-25 00:00

        Stored/query boundary:
        UTC equivalent
    """

    if not selected_date:
        return None

    company_timezone = get_company_timezone()

    local_start = datetime(
        selected_date.year,
        selected_date.month,
        selected_date.day,
        0,
        0,
        0,
        tzinfo=company_timezone
    )

    return local_start.astimezone(
        timezone.utc
    )


def company_date_to_utc_end(selected_date):
    """
    Return the UTC boundary immediately after
    the specified company-local date.
    """

    if not selected_date:
        return None

    next_date = selected_date + timedelta(
        days=1
    )

    return company_date_to_utc_start(
        next_date
    )


def company_week_start_to_utc(week_start):
    """
    Convert a company-local week start date into UTC.
    """

    return company_date_to_utc_start(
        week_start
    )


def company_month_start_to_utc(year, month):
    """
    Convert the beginning of a company-local month
    into UTC.
    """

    selected_date = datetime(
        year,
        month,
        1
    ).date()

    return company_date_to_utc_start(
        selected_date
    )


def company_year_start_to_utc(year):
    """
    Convert the beginning of a company-local year
    into UTC.
    """

    selected_date = datetime(
        year,
        1,
        1
    ).date()

    return company_date_to_utc_start(
        selected_date
    )


# ============================================================
# FINANCIAL DAY RANGE
# ============================================================

def get_company_day_range(value):
    """
    Return the UTC start/end range for the company-local
    calendar day represented by value.

    Used by financial alerts.
    """

    if isinstance(value, datetime):

        if value.tzinfo is None:

            value = value.replace(
                tzinfo=timezone.utc
            )

        company_timezone = get_company_timezone()

        local_value = value.astimezone(
            company_timezone
        )

        selected_date = local_value.date()

    else:

        selected_date = value

    start_datetime = (
        company_date_to_utc_start(
            selected_date
        )
    )

    end_datetime = (
        company_date_to_utc_end(
            selected_date
        )
        - timedelta(
            microseconds=1
        )
    )

    return (
        start_datetime,
        end_datetime
    )


# ============================================================
# PAYMENT DATA
# ============================================================

def get_payment_data():

    payment_ids = request.form.getlist(
        "payment_id"
    )

    methods = request.form.getlist(
        "payment_method"
    )

    amounts = request.form.getlist(
        "payment_amount"
    )

    bank_names = request.form.getlist(
        "bank_name"
    )

    account_names = request.form.getlist(
        "account_name"
    )

    account_numbers = request.form.getlist(
        "account_number"
    )

    references = request.form.getlist(
        "payment_reference"
    )

    # --------------------------------------------------------
    # No payment
    # --------------------------------------------------------

    if not methods and not amounts:

        return [], Decimal("0.00")

    # --------------------------------------------------------
    # Payment arrays must match
    # --------------------------------------------------------

    if len(methods) != len(amounts):

        return (
            None,
            "Invalid payment information submitted."
        )

    # --------------------------------------------------------
    # Pad optional arrays
    # --------------------------------------------------------

    while len(payment_ids) < len(methods):
        payment_ids.append("")

    while len(bank_names) < len(methods):
        bank_names.append("")

    while len(account_names) < len(methods):
        account_names.append("")

    while len(account_numbers) < len(methods):
        account_numbers.append("")

    while len(references) < len(methods):
        references.append("")

    # --------------------------------------------------------
    # VALID PAYMENT METHODS
    # --------------------------------------------------------

    valid_methods = {
        "Cash",
        "Bank Transfer",
        "POS",
        "Card",
        "Other"
    }

    payments = []

    total_paid = Decimal("0.00")

    # --------------------------------------------------------
    # PROCESS PAYMENT ROWS
    # --------------------------------------------------------

    for index, (
        method,
        amount_value
    ) in enumerate(
        zip(
            methods,
            amounts
        )
    ):

        method = method.strip()

        if method not in valid_methods:

            return (
                None,
                "Invalid payment method."
            )

        amount = parse_decimal(
            amount_value
        )

        if amount is None:

            return (
                None,
                "Invalid payment amount."
            )

        if amount < 0:

            return (
                None,
                "Payment amount cannot be negative."
            )

        if amount == 0:
            continue

        payment_id = (
            payment_ids[index].strip()
        )

        if payment_id:

            try:

                payment_id = int(
                    payment_id
                )

            except (
                ValueError,
                TypeError
            ):

                return (
                    None,
                    "Invalid payment information."
                )

        else:

            payment_id = None

        bank_name = None
        account_name = None
        account_number = None
        reference = None

        # ====================================================
        # BANK TRANSFER
        # ====================================================

        if method == "Bank Transfer":

            bank_name = (
                bank_names[index].strip()
                if bank_names[index]
                else None
            )

            account_name = (
                account_names[index].strip()
                if account_names[index]
                else None
            )

            account_number = (
                account_numbers[index].strip()
                if account_numbers[index]
                else None
            )

            reference = (
                references[index].strip()
                if references[index]
                else None
            )

        # ====================================================
        # POS
        # ====================================================

        elif method == "POS":

            bank_name = (
                bank_names[index].strip()
                if bank_names[index]
                else None
            )

            reference = (
                references[index].strip()
                if references[index]
                else None
            )

        # ====================================================
        # OTHER PAYMENT METHODS
        # ====================================================

        else:

            reference = (
                references[index].strip()
                if references[index]
                else None
            )

        payments.append({

            "id": payment_id,

            "method": method,

            "amount": amount,

            "bank_name": bank_name,

            "account_name": account_name,

            "account_number": account_number,

            "reference": reference

        })

        total_paid += amount

    return (
        payments,
        total_paid
    )


# ============================================================
# PROCESS SALE NOTIFICATIONS
# ============================================================

def process_sale_notifications(
    sale,
    sale_lines,
    user_id
):
    """
    Process all notifications after a sale has been
    successfully committed.

    Notification failures must never roll back
    an already completed sale.

    Notification architecture:

        SALE
        ----
        Delivery category = "sale"
        Sound = "success"

        LOW STOCK
        ---------
        Delivery category = "inventory"
        Sound = "low-stock"

        FINANCIAL LOSS
        ---------------
        Delivery category = "financial"
        Sound = "gross-loss" / "net-loss"
    """

    # ========================================================
    # SALE SUCCESS
    # ========================================================
    #
    # IMPORTANT:
    #
    # notification_category="sale"
    #
    # This controls WHO receives the notification through
    # NotificationAssignment.
    #
    # notify_success() itself supplies:
    #
    #     sound="success"
    #
    # Therefore sound settings remain completely separate
    # from notification assignment.
    # ========================================================

    try:

        notify_success(

            company_id=sale.company_id,

            user_id=user_id,

            title="Sale Completed",

            message=(
                f"Sale {sale.invoice_number} "
                f"was completed successfully for "
                f"{format_currency(sale.total or 0)}."
            ),

            notification_category="sale",

            link=url_for(
                "sales.view_sale",
                sale_id=sale.id
            ),

            reference_type="Sale",

            reference_id=sale.id

        )

    except Exception:

        current_app.logger.exception(
            "Unable to create sale success notification "
            "for sale %s.",
            sale.invoice_number
        )

    # ========================================================
    # LOW STOCK
    # ========================================================
    #
    # notify_low_stock() is responsible for creating:
    #
    #     category = "inventory"
    #     sound    = "low-stock"
    #
    # Inventory NotificationAssignment controls delivery.
    # low_stock_sound_enabled controls only the sound.
    # ========================================================

    checked_products = set()

    for line in sale_lines:

        try:

            product = line["product"]

            if product.id in checked_products:
                continue

            checked_products.add(
                product.id
            )

            minimum_stock = Decimal(
                str(
                    product.minimum_stock or 0
                )
            )

            current_quantity = Decimal(
                str(
                    product.quantity or 0
                )
            )

            current_app.logger.info(
                "Low-stock check: product=%s "
                "quantity=%s minimum=%s",
                product.name,
                current_quantity,
                minimum_stock
            )

            if current_quantity <= minimum_stock:

                notification = notify_low_stock(

                    product=product,

                    user_id=user_id

                )

                current_app.logger.info(
                    "Low-stock notification processed "
                    "for product=%s notification=%s",
                    product.name,
                    getattr(
                        notification,
                        "id",
                        None
                    )
                )

        except Exception:

            current_app.logger.exception(
                "Unable to create low-stock notification."
            )

    # ========================================================
    # FINANCIAL LOSS ALERTS
    # ========================================================
    #
    # check_financial_alerts() is responsible for:
    #
    #     category = "financial"
    #
    # with sounds:
    #
    #     gross-loss
    #     net-loss
    #
    # Financial assignment controls delivery.
    # Sound preferences only control audio.
    # ========================================================

    try:

        (
            start_datetime,
            end_datetime
        ) = get_company_day_range(
            sale.sale_date
        )

        financial_result = (
            check_financial_alerts(

                company_id=sale.company_id,

                start_datetime=start_datetime,

                end_datetime=end_datetime,

                user_id=user_id

            )
        )

        current_app.logger.info(
            "Financial alert check for %s: "
            "sales=%s cogs=%s expenses=%s "
            "gross_profit=%s net_profit=%s",
            sale.invoice_number,
            financial_result.get("sales"),
            financial_result.get("cogs"),
            financial_result.get("expenses"),
            financial_result.get("gross_profit"),
            financial_result.get("net_profit")
        )

    except Exception:

        current_app.logger.exception(
            "Unable to process financial loss "
            "notifications for sale %s.",
            sale.invoice_number
        )


# ============================================================
# PROCESS SALE UPDATE NOTIFICATIONS
# ============================================================

def process_sale_update_notifications(
    sale,
    sale_lines,
    user_id
):
    """
    Process notifications after a sale has been
    successfully edited.

    Sale update notification:

        Delivery category = "sale"
        Sound = "success"
    """

    # ========================================================
    # SALE UPDATE SUCCESS
    # ========================================================

    try:

        notify_success(

            company_id=sale.company_id,

            user_id=user_id,

            title="Sale Updated",

            message=(
                f"Sale {sale.invoice_number} "
                f"was updated successfully."
            ),

            notification_category="sale",

            link=url_for(
                "sales.view_sale",
                sale_id=sale.id
            ),

            reference_type="Sale",

            reference_id=sale.id

        )

    except Exception:

        current_app.logger.exception(
            "Unable to create sale update notification "
            "for sale %s.",
            sale.invoice_number
        )

    # ========================================================
    # LOW STOCK
    # ========================================================

    checked_products = set()

    for line in sale_lines:

        try:

            product = line["product"]

            if product.id in checked_products:
                continue

            checked_products.add(
                product.id
            )

            minimum_stock = Decimal(
                str(
                    product.minimum_stock or 0
                )
            )

            current_quantity = Decimal(
                str(
                    product.quantity or 0
                )
            )

            current_app.logger.info(
                "Low-stock check after sale edit: "
                "product=%s quantity=%s minimum=%s",
                product.name,
                current_quantity,
                minimum_stock
            )

            if current_quantity <= minimum_stock:

                notification = notify_low_stock(

                    product=product,

                    user_id=user_id

                )

                current_app.logger.info(
                    "Low-stock notification processed "
                    "for edited sale product=%s notification=%s",
                    product.name,
                    getattr(
                        notification,
                        "id",
                        None
                    )
                )

        except Exception:

            current_app.logger.exception(
                "Unable to create low-stock notification "
                "after sale edit."
            )

    # ========================================================
    # FINANCIAL LOSS ALERTS
    # ========================================================

    try:

        (
            start_datetime,
            end_datetime
        ) = get_company_day_range(
            sale.sale_date
        )

        financial_result = (
            check_financial_alerts(

                company_id=sale.company_id,

                start_datetime=start_datetime,

                end_datetime=end_datetime,

                user_id=user_id

            )
        )

        current_app.logger.info(
            "Financial alert check after sale edit "
            "%s: sales=%s cogs=%s expenses=%s "
            "gross_profit=%s net_profit=%s",
            sale.invoice_number,
            financial_result.get("sales"),
            financial_result.get("cogs"),
            financial_result.get("expenses"),
            financial_result.get("gross_profit"),
            financial_result.get("net_profit")
        )

    except Exception:

        current_app.logger.exception(
            "Unable to process financial loss "
            "notifications after sale edit %s.",
            sale.invoice_number
        )


# ============================================================
# SALES LIST
# ============================================================

@sales_bp.route("/")
@login_required
@company_permission_required("view_sales")
def sales():

    search = request.args.get(
        "q",
        ""
    ).strip()

    period = request.args.get(
        "period",
        "all"
    ).strip().lower()

    month = request.args.get(
        "month",
        ""
    ).strip()

    year = request.args.get(
        "year",
        ""
    ).strip()

    query = Sale.query.filter_by(
        company_id=current_user.company_id
    )

    if search:

        query = query.filter(
            Sale.invoice_number.ilike(
                f"%{search}%"
            )
        )

    # IMPORTANT:
    # Use company-local current date/time instead
    # of server UTC for period defaults.

    now = company_now()

    # ========================================================
    # DAILY
    # ========================================================

    if period == "daily":

        selected_date = request.args.get(
            "date",
            ""
        ).strip()

        if selected_date:

            try:

                selected = datetime.strptime(
                    selected_date,
                    "%Y-%m-%d"
                ).date()

                start_date = (
                    company_date_to_utc_start(
                        selected
                    )
                )

                end_date = (
                    company_date_to_utc_end(
                        selected
                    )
                )

                query = query.filter(
                    Sale.sale_date >= start_date,
                    Sale.sale_date < end_date
                )

            except ValueError:
                pass

        else:

            selected = now.date()

            start_date = (
                company_date_to_utc_start(
                    selected
                )
            )

            end_date = (
                company_date_to_utc_end(
                    selected
                )
            )

            query = query.filter(
                Sale.sale_date >= start_date,
                Sale.sale_date < end_date
            )

    # ========================================================
    # WEEKLY
    # ========================================================

    elif period == "weekly":

        selected_week = request.args.get(
            "week",
            ""
        ).strip()

        if selected_week:

            try:

                week_start = datetime.strptime(
                    selected_week,
                    "%Y-%m-%d"
                ).date()

                start_date = (
                    company_week_start_to_utc(
                        week_start
                    )
                )

                end_date = (
                    start_date
                    + timedelta(days=7)
                )

                query = query.filter(
                    Sale.sale_date >= start_date,
                    Sale.sale_date < end_date
                )

            except ValueError:
                pass

        else:

            current_date = now.date()

            week_start = (
                current_date
                - timedelta(
                    days=current_date.weekday()
                )
            )

            start_date = (
                company_date_to_utc_start(
                    week_start
                )
            )

            end_date = (
                company_date_to_utc_start(
                    week_start
                    + timedelta(days=7)
                )
            )

            query = query.filter(
                Sale.sale_date >= start_date,
                Sale.sale_date < end_date
            )

    # ========================================================
    # MONTHLY
    # ========================================================

    elif period == "monthly":

        try:

            selected_month = int(
                month
            )

            selected_year = int(
                year
            )

            if not 1 <= selected_month <= 12:
                raise ValueError

            if not 2000 <= selected_year <= 2100:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            selected_month = now.month
            selected_year = now.year

        start_date = (
            company_month_start_to_utc(
                selected_year,
                selected_month
            )
        )

        if selected_month == 12:

            end_date = (
                company_year_start_to_utc(
                    selected_year + 1
                )
            )

        else:

            end_date = (
                company_month_start_to_utc(
                    selected_year,
                    selected_month + 1
                )
            )

        query = query.filter(
            Sale.sale_date >= start_date,
            Sale.sale_date < end_date
        )

    # ========================================================
    # YEARLY
    # ========================================================

    elif period == "yearly":

        try:

            selected_year = int(
                year
            )

            if not 2000 <= selected_year <= 2100:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            selected_year = now.year

        start_date = (
            company_year_start_to_utc(
                selected_year
            )
        )

        end_date = (
            company_year_start_to_utc(
                selected_year + 1
            )
        )

        query = query.filter(
            Sale.sale_date >= start_date,
            Sale.sale_date < end_date
        )

    sales = (
        query
        .order_by(
            Sale.sale_date.desc(),
            Sale.id.desc()
        )
        .all()
    )

    current_year = now.year

    years = list(
        range(
            current_year - 10,
            current_year + 1
        )
    )

    settings = get_sales_company_settings()

    return render_template(
        "sales/sales.html",
        sales=sales,
        search=search,
        period=period,
        month=month,
        year=year,
        years=years,
        settings=settings
    )


# ============================================================
# NEW SALE
# ============================================================

@sales_bp.route(
    "/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("view_sales")
def new_sale():

    form = SaleForm()

    customers = (
        Customer.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True
        )
        .order_by(
            Customer.name.asc()
        )
        .all()
    )

    products = (
        Product.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True
        )
        .order_by(
            Product.name.asc()
        )
        .all()
    )

    form.customer_id.choices = [
        (
            0,
            "Walk-in Customer"
        )
    ] + [
        (
            customer.id,
            customer.name
        )
        for customer in customers
    ]

    settings = get_sales_company_settings()

    # ========================================================
    # GET
    # ========================================================

    if request.method == "GET":

        form.customer_id.data = 0

        form.sale_date.data = (
            company_now().date()
        )

    # ========================================================
    # POST
    # ========================================================

    if form.validate_on_submit():

        product_ids = request.form.getlist(
            "product_id"
        )

        quantities = request.form.getlist(
            "quantity"
        )

        if not product_ids:

            flash(
                "Please add at least one product.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        if len(product_ids) != len(quantities):

            flash(
                "Invalid product information submitted.",
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        # ====================================================
        # VALIDATE PRODUCTS
        # ====================================================

        sale_lines = []

        subtotal = Decimal("0.00")

        for product_id, quantity_value in zip(
            product_ids,
            quantities
        ):

            try:

                product_id = int(
                    product_id
                )

                quantity = Decimal(
                    str(quantity_value)
                )

            except (
                ValueError,
                TypeError,
                InvalidOperation
            ):

                flash(
                    "Invalid product or quantity.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            if quantity <= 0:

                flash(
                    "Product quantities must be greater than zero.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            product = (
                Product.query
                .filter_by(
                    id=product_id,
                    company_id=current_user.company_id,
                    is_active=True
                )
                .first()
            )

            if not product:

                flash(
                    "One of the selected products could not be found.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            available_quantity = (
                product.available_quantity
            )

            if quantity > available_quantity:

                flash(
                    f"Insufficient available stock for "
                    f"{product.name}. "
                    f"Available stock: "
                    f"{available_quantity:,.3f} "
                    f"{product.unit}. "
                    f"Reserved: "
                    f"{Decimal(str(product.reserved_quantity or 0)):,.3f} "
                    f"{product.unit}.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            unit_price = Decimal(
                str(
                    product.selling_price or 0
                )
            )

            line_total = (
                quantity
                * unit_price
            )

            subtotal += line_total

            sale_lines.append({

                "product": product,

                "quantity": quantity,

                "unit_price": unit_price,

                "total": line_total

            })

        # ====================================================
        # FINANCIAL CALCULATIONS
        # ====================================================

        discount = Decimal(
            str(
                form.discount.data or 0
            )
        )

        tax = Decimal(
            str(
                form.tax.data or 0
            )
        )

        if discount < 0:

            flash(
                "Discount cannot be negative.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        if tax < 0:

            flash(
                "Tax cannot be negative.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        if discount > subtotal:

            flash(
                "Discount cannot be greater than the subtotal.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        total = (
            subtotal
            - discount
            + tax
        )

        # ====================================================
        # PAYMENTS
        # ====================================================

        payments, payment_result = (
            get_payment_data()
        )

        if payments is None:

            flash(
                payment_result,
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        total_paid = payment_result

        # ====================================================
        # DUPLICATE REFERENCES
        # ====================================================

        for payment_data in payments:

            reference = payment_data.get(
                "reference"
            )

            if not reference:
                continue

            reference = reference.strip()

            existing_payment = (
                Payment.query
                .filter(
                    Payment.company_id
                    == current_user.company_id,

                    Payment.reference
                    == reference
                )
                .first()
            )

            if existing_payment:

                flash(
                    f"Payment reference "
                    f"'{reference}' already exists.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

        # ====================================================
        # PAYMENT TOTAL
        # ====================================================

        if total_paid > total:

            flash(
                "Total payment cannot be greater than "
                "the sale total.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        balance = (
            total
            - total_paid
        )

        if total_paid <= 0:

            payment_status = "Unpaid"

        elif total_paid < total:

            payment_status = "Partially Paid"

        else:

            payment_status = "Paid"

        # ====================================================
        # CUSTOMER
        # ====================================================

        customer_id = (
            form.customer_id.data
        )

        if customer_id == 0:

            customer_id = None

            customer = None

        else:

            customer = (
                Customer.query
                .filter_by(
                    id=customer_id,
                    company_id=current_user.company_id,
                    is_active=True
                )
                .first()
            )

            if not customer:

                flash(
                    "Invalid customer selected.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            existing_balance = (
                customer.opening_balance
                or Decimal("0.00")
            )

            existing_balance += sum(
                (
                    sale_record.balance
                    or Decimal("0.00")
                )
                for sale_record in customer.sales
            )

            credit_limit = (
                customer.credit_limit
                or Decimal("0.00")
            )

            projected_balance = (
                existing_balance
                + balance
            )

            if (
                balance > 0
                and projected_balance > credit_limit
            ):

                available_credit = (
                    credit_limit
                    - existing_balance
                )

                if available_credit < 0:
                    available_credit = Decimal("0.00")

                flash(
                    f"Credit limit exceeded for "
                    f"{customer.name}. "
                    f"Current outstanding balance: "
                    f"{format_currency(existing_balance)}. "
                    f"Available credit: "
                    f"{format_currency(available_credit)}.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers,
                    settings=settings
                )

        # ====================================================
        # CREATE SALE
        # ====================================================

        sale = Sale(

            company_id=current_user.company_id,

            customer_id=customer_id,

            # DO NOT CHANGE NUMBERING.
            invoice_number=generate_invoice_number(),

            sale_date=form.sale_date.data,

            subtotal=subtotal,

            discount=discount,

            tax=tax,

            total=total,

            paid_amount=total_paid,

            balance=balance,

            status="Completed",

            payment_status=payment_status,

            notes=(
                form.notes.data.strip()
                if form.notes.data
                else None
            ),

            created_by=current_user.id

        )

        db.session.add(
            sale
        )

        db.session.flush()

        # ====================================================
        # SALE ITEMS + STOCK
        # ====================================================

        for line in sale_lines:

            product = line["product"]

            quantity = line["quantity"]

            sale_item = SaleItem(

                sale_id=sale.id,

                product_id=product.id,

                quantity=quantity,

                unit_price=line["unit_price"],

                discount=Decimal("0.00"),

                tax=Decimal("0.00"),

                total=line["total"]

            )

            db.session.add(
                sale_item
            )

            product.quantity = (
                Decimal(
                    str(
                        product.quantity or 0
                    )
                )
                - quantity
            )

            transaction = InventoryTransaction(

                company_id=current_user.company_id,

                product_id=product.id,

                transaction_type="Sale",

                quantity=-quantity,

                reference_type="Sale",

                reference_id=sale.id,

                notes=(
                    f"Sale {sale.invoice_number}"
                ),

                created_by=current_user.id

            )

            db.session.add(
                transaction
            )

        # ====================================================
        # PAYMENTS
        # ====================================================

        for payment_data in payments:

            payment = Payment(

                company_id=current_user.company_id,

                sale_id=sale.id,

                amount=payment_data["amount"],

                method=payment_data["method"],

                bank_name=payment_data["bank_name"],

                account_name=payment_data["account_name"],

                account_number=payment_data["account_number"],

                reference=payment_data["reference"],

                # DATABASE STORAGE REMAINS UTC.
                payment_date=datetime.now(
                    timezone.utc
                ),

                notes=None,

                created_by=current_user.id

            )

            db.session.add(
                payment
            )

        # ====================================================
        # COMMIT
        # ====================================================

        try:

            db.session.commit()

        except Exception as error:

            db.session.rollback()

            flash(
                f"Unable to complete sale: {error}",
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers,
                settings=settings
            )

        # ====================================================
        # NOTIFICATIONS
        # ====================================================

        process_sale_notifications(

            sale=sale,

            sale_lines=sale_lines,

            user_id=current_user.id

        )

        # ====================================================
        # SUCCESS MESSAGE
        # ====================================================

        flash(
            f"Sale {sale.invoice_number} "
            f"completed successfully.",
            "success"
        )

        return redirect(
            url_for(
                "sales.view_sale",
                sale_id=sale.id
            )
        )

    return render_template(
        "sales/sale_form.html",
        form=form,
        sale=None,
        products=products,
        customers=customers,
        settings=settings
    )


# ============================================================
# PUBLIC COMPANY PAGE
# ============================================================

@sales_bp.route(
    "/company/<string:qr_code>"
)
def public_company(qr_code):

    company = (
        Company.query
        .filter_by(
            qr_code=qr_code
        )
        .first_or_404()
    )

    return render_template(
        "sales/public_company.html",
        company=company
    )


# ============================================================
# VIEW SALE
# ============================================================

@sales_bp.route(
    "/<int:sale_id>"
)
@login_required
@company_permission_required("view_sales")
def view_sale(sale_id):

    sale = (
        Sale.query
        .filter_by(
            id=sale_id,
            company_id=current_user.company_id
        )
        .first_or_404()
    )

    company = Company.query.get_or_404(
        sale.company_id
    )

    company_url = url_for(
        "sales.public_company",
        qr_code=company.qr_code,
        _external=True
    )

    qr_image_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=100x100&data="
        f"{quote(company_url, safe='')}"
    )

    settings = get_sales_company_settings()

    return render_template(
        "sales/view_sale.html",
        sale=sale,
        company=company,
        company_url=company_url,
        qr_image_url=qr_image_url,
        settings=settings
    )


# ============================================================
# EDIT SALE
# ============================================================

@sales_bp.route(
    "/<int:sale_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_sales")
def edit_sale(sale_id):

    sale = (
        Sale.query
        .filter_by(
            id=sale_id,
            company_id=current_user.company_id
        )
        .first_or_404()
    )

    form = SaleForm()

    customers = (
        Customer.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True
        )
        .order_by(
            Customer.name.asc()
        )
        .all()
    )

    products = (
        Product.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True
        )
        .order_by(
            Product.name.asc()
        )
        .all()
    )

    form.customer_id.choices = [
        (
            0,
            "Walk-in Customer"
        )
    ] + [
        (
            customer.id,
            customer.name
        )
        for customer in customers
    ]

    settings = get_sales_company_settings()

    # ========================================================
    # GET
    # ========================================================

    if request.method == "GET":

        form.customer_id.data = (
            sale.customer_id
            if sale.customer_id
            else 0
        )

        form.sale_date.data = (
            sale.sale_date.date()
            if hasattr(
                sale.sale_date,
                "date"
            )
            else sale.sale_date
        )

        form.discount.data = sale.discount

        form.tax.data = sale.tax

        form.notes.data = sale.notes

    # ========================================================
    # POST
    # ========================================================

    if form.validate_on_submit():

        product_ids = request.form.getlist(
            "product_id"
        )

        quantities = request.form.getlist(
            "quantity"
        )

        if not product_ids:

            flash(
                "Please add at least one product.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        if len(product_ids) != len(quantities):

            flash(
                "Invalid product information submitted.",
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        # ====================================================
        # ORIGINAL QUANTITIES
        # ====================================================

        original_items = list(
            sale.items
        )

        original_quantities = defaultdict(
            lambda: Decimal("0")
        )

        for item in original_items:

            original_quantities[
                item.product_id
            ] += Decimal(
                str(
                    item.quantity or 0
                )
            )

        # ====================================================
        # VALIDATE NEW PRODUCTS
        # ====================================================

        sale_lines = []

        subtotal = Decimal("0.00")

        for product_id, quantity_value in zip(
            product_ids,
            quantities
        ):

            try:

                product_id = int(
                    product_id
                )

                quantity = Decimal(
                    str(quantity_value)
                )

            except (
                ValueError,
                TypeError,
                InvalidOperation
            ):

                db.session.rollback()

                flash(
                    "Invalid product or quantity.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            if quantity <= 0:

                db.session.rollback()

                flash(
                    "Product quantities must be greater than zero.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            product = (
                Product.query
                .filter_by(
                    id=product_id,
                    company_id=current_user.company_id,
                    is_active=True
                )
                .first()
            )

            if not product:

                db.session.rollback()

                flash(
                    "One of the selected products could not be found.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            physical_quantity = Decimal(
                str(
                    product.quantity or 0
                )
            )

            reserved_quantity = Decimal(
                str(
                    product.reserved_quantity or 0
                )
            )

            original_quantity = (
                original_quantities.get(
                    product.id,
                    Decimal("0")
                )
            )

            available_for_edit = (
                physical_quantity
                + original_quantity
                - reserved_quantity
            )

            if available_for_edit < 0:

                available_for_edit = Decimal("0")

            if quantity > available_for_edit:

                db.session.rollback()

                flash(
                    f"Insufficient available stock for "
                    f"{product.name}. "
                    f"Available for this sale: "
                    f"{available_for_edit:,.3f} "
                    f"{product.unit}. "
                    f"Reserved: "
                    f"{reserved_quantity:,.3f} "
                    f"{product.unit}.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            unit_price = Decimal(
                str(
                    product.selling_price or 0
                )
            )

            line_total = (
                quantity
                * unit_price
            )

            subtotal += line_total

            sale_lines.append({

                "product": product,

                "quantity": quantity,

                "unit_price": unit_price,

                "total": line_total

            })

        # ====================================================
        # FINANCIAL CALCULATIONS
        # ====================================================

        discount = Decimal(
            str(
                form.discount.data or 0
            )
        )

        tax = Decimal(
            str(
                form.tax.data or 0
            )
        )

        if discount < 0:

            db.session.rollback()

            flash(
                "Discount cannot be negative.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        if tax < 0:

            db.session.rollback()

            flash(
                "Tax cannot be negative.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        if discount > subtotal:

            db.session.rollback()

            flash(
                "Discount cannot be greater than the subtotal.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        total = (
            subtotal
            - discount
            + tax
        )

        # ====================================================
        # PAYMENTS
        # ====================================================

        payments, payment_result = (
            get_payment_data()
        )

        if payments is None:

            db.session.rollback()

            flash(
                payment_result,
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        total_paid = payment_result

        # ====================================================
        # DUPLICATE PAYMENT REFERENCES
        # ====================================================

        for payment_data in payments:

            reference = payment_data.get(
                "reference"
            )

            if not reference:
                continue

            reference = reference.strip()

            query = Payment.query.filter(

                Payment.company_id
                == current_user.company_id,

                Payment.reference
                == reference

            )

            payment_id = payment_data.get(
                "id"
            )

            if payment_id:

                query = query.filter(
                    Payment.id != payment_id
                )

            existing_payment = (
                query.first()
            )

            if existing_payment:

                db.session.rollback()

                flash(
                    f"Payment reference "
                    f"'{reference}' already exists.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

        # ====================================================
        # PAYMENT TOTAL
        # ====================================================

        if total_paid > total:

            db.session.rollback()

            flash(
                "Total payment cannot be greater than "
                "the sale total.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        balance = (
            total
            - total_paid
        )

        if total_paid <= 0:

            payment_status = "Unpaid"

        elif total_paid < total:

            payment_status = "Partially Paid"

        else:

            payment_status = "Paid"

        # ====================================================
        # CUSTOMER
        # ====================================================

        customer_id = (
            form.customer_id.data
        )

        if customer_id == 0:

            customer_id = None

            customer = None

        else:

            customer = (
                Customer.query
                .filter_by(
                    id=customer_id,
                    company_id=current_user.company_id,
                    is_active=True
                )
                .first()
            )

            if not customer:

                db.session.rollback()

                flash(
                    "Invalid customer selected.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

            existing_balance = (
                customer.opening_balance
                or Decimal("0.00")
            )

            existing_balance += sum(
                (
                    sale_record.balance
                    or Decimal("0.00")
                )
                for sale_record in customer.sales
                if sale_record.id != sale.id
            )

            credit_limit = (
                customer.credit_limit
                or Decimal("0.00")
            )

            projected_balance = (
                existing_balance
                + balance
            )

            if (
                balance > 0
                and projected_balance > credit_limit
            ):

                available_credit = (
                    credit_limit
                    - existing_balance
                )

                if available_credit < 0:

                    available_credit = (
                        Decimal("0.00")
                    )

                db.session.rollback()

                flash(
                    f"Credit limit exceeded for "
                    f"{customer.name}. "
                    f"Current outstanding balance: "
                    f"{format_currency(existing_balance)}. "
                    f"Available credit: "
                    f"{format_currency(available_credit)}.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers,
                    settings=settings
                )

        # ====================================================
        # UPDATE SALE HEADER
        # ====================================================

        sale.customer_id = customer_id

        sale.sale_date = form.sale_date.data

        sale.subtotal = subtotal

        sale.discount = discount

        sale.tax = tax

        sale.total = total

        sale.paid_amount = total_paid

        sale.balance = balance

        sale.payment_status = payment_status

        sale.notes = (
            form.notes.data.strip()
            if form.notes.data
            else None
        )

        # ====================================================
        # RESTORE ORIGINAL STOCK
        # ====================================================

        for item in original_items:

            product = item.product

            original_quantity = Decimal(
                str(
                    item.quantity or 0
                )
            )

            product.quantity = (
                Decimal(
                    str(
                        product.quantity or 0
                    )
                )
                + original_quantity
            )

            reversal = InventoryTransaction(

                company_id=current_user.company_id,

                product_id=product.id,

                transaction_type="Sale Edit Reversal",

                quantity=original_quantity,

                reference_type="Sale",

                reference_id=sale.id,

                notes=(
                    f"Reversed previous quantity "
                    f"from edited sale "
                    f"{sale.invoice_number}"
                ),

                created_by=current_user.id

            )

            db.session.add(
                reversal
            )

        # ====================================================
        # DELETE OLD ITEMS
        # ====================================================

        for item in original_items:

            db.session.delete(
                item
            )

        db.session.flush()

        # ====================================================
        # CREATE UPDATED ITEMS + STOCK
        # ====================================================

        for line in sale_lines:

            product = line["product"]

            quantity = line["quantity"]

            sale_item = SaleItem(

                sale_id=sale.id,

                product_id=product.id,

                quantity=quantity,

                unit_price=line["unit_price"],

                discount=Decimal("0.00"),

                tax=Decimal("0.00"),

                total=line["total"]

            )

            db.session.add(
                sale_item
            )

            product.quantity = (
                Decimal(
                    str(
                        product.quantity or 0
                    )
                )
                - quantity
            )

            transaction = InventoryTransaction(

                company_id=current_user.company_id,

                product_id=product.id,

                transaction_type="Sale Edit",

                quantity=-quantity,

                reference_type="Sale",

                reference_id=sale.id,

                notes=(
                    f"Applied updated quantity "
                    f"to sale {sale.invoice_number}"
                ),

                created_by=current_user.id

            )

            db.session.add(
                transaction
            )

        # ====================================================
        # UPDATE PAYMENTS
        # ====================================================

        old_payments = list(
            sale.payments
        )

        old_payment_map = {
            payment.id: payment
            for payment in old_payments
        }

        submitted_payment_ids = set()

        for payment_data in payments:

            payment_id = (
                payment_data.get("id")
            )

            if payment_id:

                payment = (
                    old_payment_map.get(
                        payment_id
                    )
                )

                if not payment:

                    db.session.rollback()

                    flash(
                        "Invalid payment information submitted.",
                        "danger"
                    )

                    return render_template(
                        "sales/sale_form.html",
                        form=form,
                        sale=sale,
                        products=products,
                        customers=customers,
                        settings=settings
                    )

                submitted_payment_ids.add(
                    payment.id
                )

                payment.amount = (
                    payment_data["amount"]
                )

                payment.method = (
                    payment_data["method"]
                )

                payment.bank_name = (
                    payment_data["bank_name"]
                )

                payment.account_name = (
                    payment_data["account_name"]
                )

                payment.account_number = (
                    payment_data["account_number"]
                )

                payment.reference = (
                    payment_data["reference"]
                )

            else:

                payment = Payment(

                    company_id=current_user.company_id,

                    sale_id=sale.id,

                    amount=payment_data["amount"],

                    method=payment_data["method"],

                    bank_name=payment_data["bank_name"],

                    account_name=payment_data["account_name"],

                    account_number=payment_data["account_number"],

                    reference=payment_data["reference"],

                    # STORE UTC.
                    payment_date=datetime.now(
                        timezone.utc
                    ),

                    notes=None,

                    created_by=current_user.id

                )

                db.session.add(
                    payment
                )

        # ====================================================
        # DELETE REMOVED PAYMENTS
        # ====================================================

        for payment in old_payments:

            if payment.id not in submitted_payment_ids:

                db.session.delete(
                    payment
                )

        # ====================================================
        # COMMIT
        # ====================================================

        try:

            db.session.commit()

        except Exception as error:

            db.session.rollback()

            flash(
                f"Unable to update sale: {error}",
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers,
                settings=settings
            )

        # ====================================================
        # NOTIFICATIONS
        # ====================================================

        process_sale_update_notifications(

            sale=sale,

            sale_lines=sale_lines,

            user_id=current_user.id

        )

        # ====================================================
        # SUCCESS MESSAGE
        # ====================================================

        flash(
            f"Sale {sale.invoice_number} "
            f"updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "sales.view_sale",
                sale_id=sale.id
            )
        )

    # ========================================================
    # RETURN FORM
    # ========================================================

    return render_template(
        "sales/sale_form.html",
        form=form,
        sale=sale,
        products=products,
        customers=customers,
        settings=settings
    )


# ============================================================
# DELETE SALE
# ============================================================

@sales_bp.route(
    "/<int:sale_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_sales")
def delete_sale(sale_id):

    sale = (
        Sale.query
        .filter_by(
            id=sale_id,
            company_id=current_user.company_id
        )
        .first_or_404()
    )

    try:

        # ====================================================
        # RESTORE PHYSICAL STOCK
        # ====================================================

        for item in sale.items:

            product = item.product

            quantity = Decimal(
                str(
                    item.quantity or 0
                )
            )

            product.quantity = (
                Decimal(
                    str(
                        product.quantity or 0
                    )
                )
                + quantity
            )

            reversal = InventoryTransaction(

                company_id=current_user.company_id,

                product_id=product.id,

                transaction_type="Sale Reversal",

                quantity=quantity,

                reference_type="Sale Deletion",

                reference_id=sale.id,

                notes=(
                    f"Stock restored after deleting "
                    f"{sale.invoice_number}"
                ),

                created_by=current_user.id

            )

            db.session.add(
                reversal
            )

        invoice_number = (
            sale.invoice_number
        )

        db.session.delete(
            sale
        )

        db.session.commit()

        flash(
            f"Sale {invoice_number} deleted "
            f"and inventory restored.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        flash(
            f"Unable to delete sale: {error}",
            "danger"
        )

    return redirect(
        url_for(
            "sales.sales"
        )
    )