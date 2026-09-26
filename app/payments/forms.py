from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

from urllib.parse import quote

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request
)

from flask_login import (
    login_required,
    current_user
)

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

from .forms import SaleForm


sales_bp = Blueprint(
    "sales",
    __name__,
    url_prefix="/sales"
)


# ============================================================
# INVOICE NUMBER
# ============================================================

def generate_invoice_number():

    today = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d")

    prefix = f"INV-{today}-"

    last_sale = (
        Sale.query
        .filter(
            Sale.company_id == current_user.company_id,
            Sale.invoice_number.like(f"{prefix}%")
        )
        .order_by(
            Sale.id.desc()
        )
        .first()
    )

    if last_sale:

        try:

            last_number = int(
                last_sale.invoice_number.split("-")[-1]
            )

            next_number = (
                last_number + 1
            )

        except (
            ValueError,
            IndexError
        ):

            next_number = 1

    else:

        next_number = 1

    return (
        f"{prefix}{next_number:04d}"
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


def decimal_stock(value):

    """
    Convert a database quantity to Decimal safely.
    """

    try:

        return Decimal(
            str(value or 0)
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):

        return Decimal("0")


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
    # No payment rows
    # --------------------------------------------------------

    if not methods and not amounts:

        return [], Decimal("0.00")

    # --------------------------------------------------------
    # Required arrays must match
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

        method = (
            method.strip()
            if method
            else ""
        )

        # ----------------------------------------------------
        # Validate payment method
        # ----------------------------------------------------

        if method not in valid_methods:

            return (
                None,
                "Invalid payment method."
            )

        # ----------------------------------------------------
        # Validate amount
        # ----------------------------------------------------

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

        # Ignore zero payment rows
        if amount == 0:

            continue

        # ----------------------------------------------------
        # Payment ID
        # ----------------------------------------------------

        payment_id = (
            payment_ids[index].strip()
            if payment_ids[index]
            else ""
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

        # ----------------------------------------------------
        # Default payment fields
        # ----------------------------------------------------

        bank_name = None
        account_name = None
        account_number = None
        reference = None

        # ----------------------------------------------------
        # BANK TRANSFER
        #
        # Bank name
        # Account name
        # Account number
        # Reference
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # POS
        #
        # POS requires:
        # Bank name
        # Reference
        #
        # Account name/account number are not required.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # OTHER PAYMENT METHODS
        #
        # Cash / Card / Other
        # Only reference is applicable.
        # ----------------------------------------------------

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
# PAYMENT REFERENCE CHECK
# ============================================================

def payment_reference_exists(
    reference,
    exclude_payment_id=None
):

    if not reference:

        return False

    query = (
        Payment.query
        .filter(
            Payment.company_id ==
            current_user.company_id,

            Payment.reference ==
            reference
        )
    )

    if exclude_payment_id:

        query = query.filter(
            Payment.id != exclude_payment_id
        )

    return (
        query.first()
        is not None
    )


# ============================================================
# PRODUCT AVAILABLE STOCK
# ============================================================

def get_available_quantity(product):

    quantity = decimal_stock(
        product.quantity
    )

    reserved = decimal_stock(
        product.reserved_quantity
    )

    available = (
        quantity - reserved
    )

    if available < 0:

        return Decimal("0")

    return available


# ============================================================
# SALES LIST
# ============================================================

@sales_bp.route("/")
@login_required
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

    # =========================================================
    # SEARCH BY INVOICE
    # =========================================================

    if search:

        query = query.filter(
            Sale.invoice_number.ilike(
                f"%{search}%"
            )
        )

    # =========================================================
    # CURRENT TIME
    # =========================================================

    now = datetime.now(
        timezone.utc
    )

    # =========================================================
    # DAILY FILTER
    # =========================================================

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

                start_date = datetime(
                    selected.year,
                    selected.month,
                    selected.day,
                    tzinfo=timezone.utc
                )

                end_date = (
                    start_date
                    + timedelta(days=1)
                )

                query = query.filter(
                    Sale.sale_date >= start_date,
                    Sale.sale_date < end_date
                )

            except ValueError:

                pass

        else:

            start_date = now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            end_date = (
                start_date
                + timedelta(days=1)
            )

            query = query.filter(
                Sale.sale_date >= start_date,
                Sale.sale_date < end_date
            )

    # =========================================================
    # WEEKLY FILTER
    # =========================================================

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

                start_date = datetime(
                    week_start.year,
                    week_start.month,
                    week_start.day,
                    tzinfo=timezone.utc
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

            start_date = (
                now
                - timedelta(
                    days=now.weekday()
                )
            ).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            end_date = (
                start_date
                + timedelta(days=7)
            )

            query = query.filter(
                Sale.sale_date >= start_date,
                Sale.sale_date < end_date
            )

    # =========================================================
    # MONTHLY FILTER
    # =========================================================

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

        start_date = datetime(
            selected_year,
            selected_month,
            1,
            tzinfo=timezone.utc
        )

        if selected_month == 12:

            end_date = datetime(
                selected_year + 1,
                1,
                1,
                tzinfo=timezone.utc
            )

        else:

            end_date = datetime(
                selected_year,
                selected_month + 1,
                1,
                tzinfo=timezone.utc
            )

        query = query.filter(
            Sale.sale_date >= start_date,
            Sale.sale_date < end_date
        )

    # =========================================================
    # YEARLY FILTER
    # =========================================================

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

        start_date = datetime(
            selected_year,
            1,
            1,
            tzinfo=timezone.utc
        )

        end_date = datetime(
            selected_year + 1,
            1,
            1,
            tzinfo=timezone.utc
        )

        query = query.filter(
            Sale.sale_date >= start_date,
            Sale.sale_date < end_date
        )

    # =========================================================
    # GET SALES
    # =========================================================

    sales_list = (
        query
        .order_by(
            Sale.sale_date.desc(),
            Sale.id.desc()
        )
        .all()
    )

    # =========================================================
    # YEAR OPTIONS
    # =========================================================

    current_year = now.year

    years = list(
        range(
            current_year - 10,
            current_year + 1
        )
    )

    return render_template(
        "sales/sales.html",
        sales=sales_list,
        search=search,
        period=period,
        month=month,
        year=year,
        years=years
    )


# ============================================================
# NEW SALE
# ============================================================

@sales_bp.route(
    "/new",
    methods=["GET", "POST"]
)
@login_required
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

    # ========================================================
    # GET
    # ========================================================

    if request.method == "GET":

        form.customer_id.data = 0

        form.sale_date.data = (
            datetime.now(
                timezone.utc
            ).date()
        )

    # ========================================================
    # POST
    # ========================================================

    if form.validate_on_submit():

        # ====================================================
        # PRODUCT DATA
        # ====================================================

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
                customers=customers
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
                customers=customers
            )

        # ====================================================
        # VALIDATE PRODUCTS
        # ====================================================

        sale_lines = []

        subtotal = Decimal("0.00")

        # ----------------------------------------------------
        # Track quantities by product.
        #
        # This prevents a user from adding the same product
        # twice and accidentally consuming more stock than
        # is actually available.
        # ----------------------------------------------------

        requested_quantities = {}

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
                    customers=customers
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
                    customers=customers
                )

            requested_quantities[product_id] = (
                requested_quantities.get(
                    product_id,
                    Decimal("0")
                )
                + quantity
            )

        # ----------------------------------------------------
        # Validate each product only once
        # ----------------------------------------------------

        product_map = {}

        for product_id, requested_quantity in (
            requested_quantities.items()
        ):

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
                    "One of the selected products "
                    "could not be found.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers
                )

            available_quantity = (
                get_available_quantity(
                    product
                )
            )

            if requested_quantity > available_quantity:

                flash(
                    f"Insufficient available stock for "
                    f"{product.name}. "
                    f"Physical stock: "
                    f"{decimal_stock(product.quantity):g}. "
                    f"Reserved: "
                    f"{decimal_stock(product.reserved_quantity):g}. "
                    f"Available: "
                    f"{available_quantity:g}.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers
                )

            product_map[product_id] = product

        # ----------------------------------------------------
        # Build sale lines
        # ----------------------------------------------------

        for product_id, quantity_value in zip(
            product_ids,
            quantities
        ):

            product = product_map[
                int(product_id)
            ]

            quantity = Decimal(
                str(quantity_value)
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
                customers=customers
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
                customers=customers
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
                customers=customers
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
                customers=customers
            )

        total_paid = payment_result

        # ====================================================
        # PAYMENT REFERENCES
        # ====================================================

        for payment_data in payments:

            reference = payment_data.get(
                "reference"
            )

            if not reference:

                continue

            reference = reference.strip()

            if payment_reference_exists(
                reference
            ):

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
                    customers=customers
                )

        # ====================================================
        # PAYMENT TOTAL
        # ====================================================

        if total_paid > total:

            flash(
                "Total payment cannot be greater than the sale total.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=None,
                products=products,
                customers=customers
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
                    customers=customers
                )

            # =================================================
            # CREDIT LIMIT
            # =================================================

            existing_balance = (
                customer.opening_balance
                or Decimal("0.00")
            )

            existing_balance += sum(
                (
                    sale_record.balance
                    or Decimal("0.00")
                )
                for sale_record
                in customer.sales
            )

            credit_limit = (
                customer.credit_limit
                or Decimal("0.00")
            )

            new_credit = balance

            projected_balance = (
                existing_balance
                + new_credit
            )

            if (
                new_credit > 0
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

                flash(
                    f"Credit limit exceeded for "
                    f"{customer.name}. "
                    f"Current outstanding balance: "
                    f"₦{existing_balance:,.2f}. "
                    f"Available credit: "
                    f"₦{available_credit:,.2f}.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=None,
                    products=products,
                    customers=customers
                )

        # ====================================================
        # CREATE SALE
        # ====================================================

        sale = Sale(

            company_id=current_user.company_id,

            customer_id=customer_id,

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
        # SALE ITEMS + INVENTORY
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

            # ------------------------------------------------
            # Consume PHYSICAL stock.
            #
            # Reserved quantity remains untouched.
            # ------------------------------------------------

            product.quantity = (
                decimal_stock(
                    product.quantity
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
        # CREATE PAYMENTS
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
                customers=customers
            )

        flash(
            f"Sale {sale.invoice_number} "
            "completed successfully.",
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
        customers=customers
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

    return render_template(
        "sales/view_sale.html",
        sale=sale,
        company=company,
        company_url=company_url,
        qr_image_url=qr_image_url
    )


# ============================================================
# EDIT SALE
# ============================================================

@sales_bp.route(
    "/<int:sale_id>/edit",
    methods=["GET", "POST"]
)
@login_required
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

        form.discount.data = (
            sale.discount
        )

        form.tax.data = (
            sale.tax
        )

        form.notes.data = (
            sale.notes
        )

    # ========================================================
    # POST
    # ========================================================

    if form.validate_on_submit():

        # ====================================================
        # PRODUCT DATA
        # ====================================================

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
                customers=customers
            )

        if len(product_ids) != len(
            quantities
        ):

            flash(
                "Invalid product information submitted.",
                "danger"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers
            )

        # ====================================================
        # ORIGINAL SALE QUANTITIES
        # ====================================================

        original_items = list(
            sale.items
        )

        original_quantities = {}

        for item in original_items:

            quantity = decimal_stock(
                item.quantity
            )

            original_quantities[
                item.product_id
            ] = (
                original_quantities.get(
                    item.product_id,
                    Decimal("0")
                )
                + quantity
            )

        # ====================================================
        # VALIDATE REQUESTED QUANTITIES
        # ====================================================

        requested_quantities = {}

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
                    sale=sale,
                    products=products,
                    customers=customers
                )

            if quantity <= 0:

                flash(
                    "Product quantities must be greater than zero.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers
                )

            requested_quantities[
                product_id
            ] = (
                requested_quantities.get(
                    product_id,
                    Decimal("0")
                )
                + quantity
            )

        # ====================================================
        # VALIDATE PRODUCTS + INVENTORY
        # ====================================================

        product_map = {}

        for product_id, requested_quantity in (
            requested_quantities.items()
        ):

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
                    "One of the selected products "
                    "could not be found.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers
                )

            current_quantity = decimal_stock(
                product.quantity
            )

            reserved_quantity = decimal_stock(
                product.reserved_quantity
            )

            # ------------------------------------------------
            # Restore the original sale quantity mentally.
            #
            # We do NOT actually change the database yet.
            # ------------------------------------------------

            original_quantity = (
                original_quantities.get(
                    product.id,
                    Decimal("0")
                )
            )

            restored_quantity = (
                current_quantity
                + original_quantity
            )

            available_after_restore = (
                restored_quantity
                - reserved_quantity
            )

            if available_after_restore < 0:

                available_after_restore = (
                    Decimal("0")
                )

            if (
                requested_quantity
                > available_after_restore
            ):

                flash(
                    f"Insufficient available stock "
                    f"for {product.name}. "
                    f"Physical stock currently: "
                    f"{current_quantity:g}. "
                    f"Reserved: "
                    f"{reserved_quantity:g}. "
                    f"Available after restoring "
                    f"the original sale: "
                    f"{available_after_restore:g}.",
                    "warning"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers
                )

            product_map[
                product.id
            ] = product

        # ====================================================
        # BUILD SALE LINES
        # ====================================================

        sale_lines = []

        subtotal = Decimal("0.00")

        for product_id, quantity_value in zip(
            product_ids,
            quantities
        ):

            product = product_map[
                int(product_id)
            ]

            quantity = Decimal(
                str(quantity_value)
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
                sale=sale,
                products=products,
                customers=customers
            )

        if tax < 0:

            flash(
                "Tax cannot be negative.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers
            )

        if discount > subtotal:

            flash(
                "Discount cannot be greater than the subtotal.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers
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
                sale=sale,
                products=products,
                customers=customers
            )

        total_paid = payment_result

        # ====================================================
        # PAYMENT REFERENCES
        # ====================================================

        for payment_data in payments:

            reference = payment_data.get(
                "reference"
            )

            if not reference:

                continue

            reference = reference.strip()

            payment_id = payment_data.get(
                "id"
            )

            if payment_reference_exists(
                reference,
                exclude_payment_id=payment_id
            ):

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
                    customers=customers
                )

        # ====================================================
        # PAYMENT TOTAL
        # ====================================================

        if total_paid > total:

            flash(
                "Total payment cannot be greater than the sale total.",
                "warning"
            )

            return render_template(
                "sales/sale_form.html",
                form=form,
                sale=sale,
                products=products,
                customers=customers
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
                    sale=sale,
                    products=products,
                    customers=customers
                )

            # =================================================
            # CREDIT LIMIT
            # =================================================

            existing_balance = (
                customer.opening_balance
                or Decimal("0.00")
            )

            existing_balance += sum(
                (
                    sale_record.balance
                    or Decimal("0.00")
                )
                for sale_record
                in customer.sales
                if sale_record.id != sale.id
            )

            credit_limit = (
                customer.credit_limit
                or Decimal("0.00")
            )

            new_credit = balance

            projected_balance = (
                existing_balance
                + new_credit
            )

            if (
                new_credit > 0
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

                flash(
                    f"Credit limit exceeded for "
                    f"{customer.name}. "
                    f"Current outstanding balance: "
                    f"₦{existing_balance:,.2f}. "
                    f"Available credit: "
                    f"₦{available_credit:,.2f}.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers
                )

        # ====================================================
        # BEGIN INVENTORY UPDATE
        # ====================================================

        # ----------------------------------------------------
        # First reverse the original sale.
        # ----------------------------------------------------

        for item in original_items:

            product = item.product

            if not product:

                flash(
                    "A product belonging to the original "
                    "sale could not be found.",
                    "danger"
                )

                return render_template(
                    "sales/sale_form.html",
                    form=form,
                    sale=sale,
                    products=products,
                    customers=customers
                )

            quantity = decimal_stock(
                item.quantity
            )

            product.quantity = (
                decimal_stock(
                    product.quantity
                )
                + quantity
            )

            reversal = InventoryTransaction(

                company_id=current_user.company_id,

                product_id=product.id,

                transaction_type="Sale Edit Reversal",

                quantity=quantity,

                reference_type="Sale",

                reference_id=sale.id,

                notes=(
                    f"Original stock restored "
                    f"while editing "
                    f"{sale.invoice_number}"
                ),

                created_by=current_user.id

            )

            db.session.add(
                reversal
            )

        # ====================================================
        # UPDATE SALE
        # ====================================================

        sale.customer_id = (
            customer_id
        )

        sale.sale_date = (
            form.sale_date.data
        )

        sale.subtotal = (
            subtotal
        )

        sale.discount = (
            discount
        )

        sale.tax = (
            tax
        )

        sale.total = (
            total
        )

        sale.paid_amount = (
            total_paid
        )

        sale.balance = (
            balance
        )

        sale.payment_status = (
            payment_status
        )

        sale.notes = (
            form.notes.data.strip()
            if form.notes.data
            else None
        )

        # ====================================================
        # DELETE OLD SALE ITEMS
        # ====================================================

        for item in original_items:

            db.session.delete(
                item
            )

        db.session.flush()

        # ====================================================
        # CREATE UPDATED SALE ITEMS
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
                decimal_stock(
                    product.quantity
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
                    f"Updated sale "
                    f"{sale.invoice_number}"
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

        # ====================================================
        # UPDATE EXISTING / CREATE NEW
        # ====================================================

        for payment_data in payments:

            payment_id = (
                payment_data.get(
                    "id"
                )
            )

            # ------------------------------------------------
            # EXISTING PAYMENT
            # ------------------------------------------------

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
                        customers=customers
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

                # Existing payment date remains unchanged.

            # ------------------------------------------------
            # NEW PAYMENT
            # ------------------------------------------------

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

            if (
                payment.id
                not in submitted_payment_ids
            ):

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
                customers=customers
            )

        flash(
            f"Sale {sale.invoice_number} "
            "updated successfully.",
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
        customers=customers
    )


# ============================================================
# DELETE SALE
# ============================================================

@sales_bp.route(
    "/<int:sale_id>/delete",
    methods=["POST"]
)
@login_required
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

        # ----------------------------------------------------
        # RESTORE PHYSICAL STOCK
        #
        # IMPORTANT:
        # reserved_quantity is NOT changed.
        # ----------------------------------------------------

        for item in sale.items:

            product = item.product

            if not product:

                raise ValueError(
                    "A product belonging to this sale "
                    "could not be found."
                )

            quantity = decimal_stock(
                item.quantity
            )

            product.quantity = (
                decimal_stock(
                    product.quantity
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

        # ----------------------------------------------------
        # DELETE SALE
        # ----------------------------------------------------

        db.session.delete(
            sale
        )

        db.session.commit()

        flash(
            f"Sale {invoice_number} deleted "
            "and inventory restored.",
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