from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

from flask import (
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

from app.notifications.service import (
    notify_success,
    check_financial_alerts
)

from app.company_admin.decorators import (
    company_permission_required
)

from app.extensions import db

from app.models import (
    Purchase,
    PurchaseItem,
    Payment,
    Product,
    Supplier,
    InventoryTransaction
)

from app.utils.document_numbers import (
    generate_purchase_number
)

from app.utils.company_settings import (
    format_currency
)

from . import purchases_bp
from .forms import PurchaseForm


# =========================================================
# HELPERS
# =========================================================

def parse_decimal(
    value,
    default=Decimal("0")
):
    """
    Safely convert a value to Decimal.
    """

    if value is None:
        return default

    try:
        value = str(value).strip()

        if not value:
            return default

        return Decimal(value)

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):
        return None


def get_purchase_payment_data():
    """
    Parse multiple purchase payments from the request.

    Returns:
        (payments, total_paid)

    On validation error:
        (None, error_message)
    """

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

    # -----------------------------------------------------
    # NO PAYMENTS
    # -----------------------------------------------------

    if not methods and not amounts:
        return [], Decimal("0.00")

    # -----------------------------------------------------
    # METHOD / AMOUNT COUNT
    # -----------------------------------------------------

    if len(methods) != len(amounts):
        return (
            None,
            "Invalid payment information submitted."
        )

    # -----------------------------------------------------
    # NORMALIZE OPTIONAL LISTS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # VALID METHODS
    # -----------------------------------------------------

    valid_methods = {
        "Cash",
        "Bank Transfer",
        "POS",
        "Card",
        "Other"
    }

    payments = []

    total_paid = Decimal("0.00")

    # -----------------------------------------------------
    # PROCESS EACH PAYMENT
    # -----------------------------------------------------

    for index in range(len(methods)):

        method = (
            methods[index] or ""
        ).strip()

        if method not in valid_methods:
            return (
                None,
                "Invalid payment method."
            )

        # -------------------------------------------------
        # AMOUNT
        # -------------------------------------------------

        amount = parse_decimal(
            amounts[index]
        )

        if amount is None:
            return (
                None,
                f"Invalid payment amount for "
                f"Payment {index + 1}."
            )

        if amount < 0:
            return (
                None,
                f"Payment amount cannot be negative "
                f"for Payment {index + 1}."
            )

        # Zero-value rows are ignored.
        if amount == 0:
            continue

        # -------------------------------------------------
        # PAYMENT ID
        # -------------------------------------------------

        raw_payment_id = (
            payment_ids[index]
            if index < len(payment_ids)
            else ""
        )

        raw_payment_id = (
            raw_payment_id.strip()
            if raw_payment_id
            else ""
        )

        payment_id = None

        if raw_payment_id:

            try:
                payment_id = int(
                    raw_payment_id
                )

            except (
                ValueError,
                TypeError
            ):
                return (
                    None,
                    f"Invalid payment record "
                    f"for Payment {index + 1}."
                )

            if payment_id <= 0:
                return (
                    None,
                    f"Invalid payment record "
                    f"for Payment {index + 1}."
                )

        # -------------------------------------------------
        # PAYMENT DETAILS
        # -------------------------------------------------

        bank_name = None
        account_name = None
        account_number = None
        reference = None

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

        else:

            reference = (
                references[index].strip()
                if references[index]
                else None
            )

        # -------------------------------------------------
        # STORE PAYMENT
        # -------------------------------------------------

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


def calculate_payment_status(
    total,
    amount_paid
):
    """
    Determine purchase payment status.
    """

    total = Decimal(
        total or 0
    )

    amount_paid = Decimal(
        amount_paid or 0
    )

    if total <= 0:
        return "Paid"

    if amount_paid <= 0:
        return "Unpaid"

    if amount_paid >= total:
        return "Paid"

    return "Partially Paid"


def get_purchase_products():
    """
    Get active products belonging to
    the current company.
    """

    return (
        Product.query
        .filter(
            Product.company_id
            == current_user.company_id,
            Product.is_active.is_(True)
        )
        .order_by(
            Product.name.asc()
        )
        .all()
    )


def get_purchase_suppliers():
    """
    Get active suppliers belonging to
    the current company.
    """

    return (
        Supplier.query
        .filter(
            Supplier.company_id
            == current_user.company_id,
            Supplier.is_active.is_(True)
        )
        .order_by(
            Supplier.name.asc()
        )
        .all()
    )


def validate_purchase_items(
    product_ids,
    quantities,
    unit_costs,
    manufacturing_dates,
    expiry_dates
):
    """
    Validate purchase product lines.
    """

    if not product_ids:
        return (
            None,
            "Please add at least one product."
        )

    if not (
        len(product_ids)
        == len(quantities)
        == len(unit_costs)
        == len(manufacturing_dates)
        == len(expiry_dates)
    ):
        return (
            None,
            "Invalid purchase item data."
        )

    items = []

    for index, product_id_raw in enumerate(
        product_ids
    ):

        # -------------------------------------------------
        # PRODUCT ID
        # -------------------------------------------------

        try:
            product_id = int(
                product_id_raw
            )

        except (
            TypeError,
            ValueError
        ):
            return (
                None,
                "Invalid product selected."
            )

        # -------------------------------------------------
        # PRODUCT
        # -------------------------------------------------

        product = (
            Product.query
            .filter(
                Product.id == product_id,
                Product.company_id
                == current_user.company_id
            )
            .first()
        )

        if not product:
            return (
                None,
                "One of the selected products "
                "is invalid."
            )

        if not product.is_active:
            return (
                None,
                f"{product.name} is inactive."
            )

        # -------------------------------------------------
        # QUANTITY
        # -------------------------------------------------

        quantity = parse_decimal(
            quantities[index]
        )

        if quantity is None:
            return (
                None,
                f"Invalid quantity for "
                f"{product.name}."
            )

        if quantity <= 0:
            return (
                None,
                f"Quantity for {product.name} "
                "must be greater than zero."
            )

        # -------------------------------------------------
        # UNIT COST
        # -------------------------------------------------

        unit_cost = parse_decimal(
            unit_costs[index]
        )

        if unit_cost is None:
            return (
                None,
                f"Invalid unit cost for "
                f"{product.name}."
            )

        if unit_cost < 0:
            return (
                None,
                f"Unit cost for {product.name} "
                "cannot be negative."
            )

        # -------------------------------------------------
        # MANUFACTURING DATE
        # -------------------------------------------------

        manufacturing_date = None

        manufacturing_raw = (
            manufacturing_dates[index]
            if index < len(
                manufacturing_dates
            )
            else ""
        )

        if manufacturing_raw:

            try:
                manufacturing_date = (
                    datetime.strptime(
                        manufacturing_raw,
                        "%Y-%m-%d"
                    ).date()
                )

            except ValueError:
                return (
                    None,
                    f"Invalid manufacturing date "
                    f"for {product.name}."
                )

        # -------------------------------------------------
        # EXPIRY DATE
        # -------------------------------------------------

        expiry_date = None

        expiry_raw = (
            expiry_dates[index]
            if index < len(
                expiry_dates
            )
            else ""
        )

        if expiry_raw:

            try:
                expiry_date = (
                    datetime.strptime(
                        expiry_raw,
                        "%Y-%m-%d"
                    ).date()
                )

            except ValueError:
                return (
                    None,
                    f"Invalid expiry date "
                    f"for {product.name}."
                )

        # -------------------------------------------------
        # DATE VALIDATION
        # -------------------------------------------------

        if (
            manufacturing_date
            and expiry_date
            and expiry_date < manufacturing_date
        ):
            return (
                None,
                f"Expiry date for {product.name} "
                "cannot be before the "
                "manufacturing date."
            )

        # -------------------------------------------------
        # LINE TOTAL
        # -------------------------------------------------

        line_total = (
            quantity * unit_cost
        )

        items.append({
            "product": product,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "manufacturing_date":
                manufacturing_date,
            "expiry_date":
                expiry_date,
            "discount":
                Decimal("0"),
            "tax":
                Decimal("0"),
            "total":
                line_total
        })

    return (
        items,
        None
    )


def validate_purchase_dates(form):
    """
    Validate purchase date relationships.
    """

    purchase_date = (
        form.purchase_date.data
    )

    expected_delivery_date = (
        form.expected_delivery_date.data
    )

    if (
        purchase_date
        and expected_delivery_date
        and expected_delivery_date
        < purchase_date
    ):
        return (
            "Expected delivery date cannot be "
            "before the purchase date."
        )

    return None


def calculate_purchase_totals(
    items,
    discount,
    tax
):
    """
    Calculate purchase subtotal and total.
    """

    subtotal = sum(
        (
            item["total"]
            for item in items
        ),
        Decimal("0")
    )

    discount = Decimal(
        discount or 0
    )

    tax = Decimal(
        tax or 0
    )

    total = (
        subtotal
        - discount
        + tax
    )

    return (
        subtotal,
        total
    )


def render_purchase_form(
    form,
    products,
    suppliers,
    purchase=None
):
    """
    Render purchase form consistently.
    """

    return render_template(
        "purchases/purchase_form.html",
        form=form,
        products=products,
        suppliers=suppliers,
        purchase=purchase
    )


# =========================================================
# FINANCIAL ALERT HELPER
# =========================================================

def run_purchase_financial_alerts(
    purchase,
    user_id
):
    """
    Run financial alert checking for the purchase date.

    IMPORTANT:

    check_financial_alerts() creates financial notifications
    using the `financial` DELIVERY category.

    Its sounds are:
        gross-loss
        net-loss

    Sound preferences do not control notification delivery.
    """

    purchase_date = purchase.purchase_date

    if hasattr(
        purchase_date,
        "date"
    ):
        financial_date = (
            purchase_date.date()
        )
    else:
        financial_date = purchase_date

    if not financial_date:
        return

    start_datetime = (
        datetime.combine(
            financial_date,
            datetime.min.time(),
            tzinfo=timezone.utc
        )
    )

    end_datetime = (
        start_datetime
        + timedelta(days=1)
        - timedelta(microseconds=1)
    )

    check_financial_alerts(
        company_id=
            current_user.company_id,

        start_datetime=
            start_datetime,

        end_datetime=
            end_datetime,

        user_id=
            user_id
    )


# =========================================================
# PURCHASE LIST
# =========================================================

@purchases_bp.route("/")
@login_required
@company_permission_required("view_purchases")
def purchases():

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    query = (
        Purchase.query
        .filter(
            Purchase.company_id
            == current_user.company_id
        )
    )

    if search:

        query = query.filter(
            Purchase.purchase_number.ilike(
                f"%{search}%"
            )
        )

    purchases_list = (
        query
        .order_by(
            Purchase.purchase_date.desc(),
            Purchase.id.desc()
        )
        .all()
    )

    return render_template(
        "purchases/purchases.html",
        purchases=purchases_list,
        search=search
    )


# =========================================================
# NEW PURCHASE
# =========================================================

@purchases_bp.route(
    "/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_purchases")
def new_purchase():

    form = PurchaseForm()

    suppliers = get_purchase_suppliers()
    products = get_purchase_products()

    form.supplier_id.choices = [
        (
            0,
            "No Supplier / Cash Purchase"
        )
    ] + [
        (
            supplier.id,
            supplier.name
        )
        for supplier in suppliers
    ]

    if form.validate_on_submit():

        # -------------------------------------------------
        # DATE VALIDATION
        # -------------------------------------------------

        date_error = validate_purchase_dates(
            form
        )

        if date_error:

            flash(
                date_error,
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

        # -------------------------------------------------
        # PRODUCT DATA
        # -------------------------------------------------

        product_ids = request.form.getlist(
            "product_id"
        )

        quantities = request.form.getlist(
            "quantity"
        )

        unit_costs = request.form.getlist(
            "unit_cost"
        )

        manufacturing_dates = (
            request.form.getlist(
                "manufacturing_date"
            )
        )

        expiry_dates = (
            request.form.getlist(
                "expiry_date"
            )
        )

        items, error = (
            validate_purchase_items(
                product_ids,
                quantities,
                unit_costs,
                manufacturing_dates,
                expiry_dates
            )
        )

        if error:

            flash(
                error,
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

        # -------------------------------------------------
        # TOTALS
        # -------------------------------------------------

        discount = Decimal(
            form.discount.data or 0
        )

        tax = Decimal(
            form.tax.data or 0
        )

        subtotal, total = (
            calculate_purchase_totals(
                items,
                discount,
                tax
            )
        )

        if discount > subtotal:

            flash(
                "Discount cannot be greater "
                "than the purchase subtotal.",
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

        if total < 0:

            flash(
                "Purchase total cannot "
                "be negative.",
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

        # -------------------------------------------------
        # PAYMENTS
        # -------------------------------------------------

        payments, payment_result = (
            get_purchase_payment_data()
        )

        if payments is None:

            flash(
                payment_result,
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

        amount_paid = payment_result

        # -------------------------------------------------
        # PAYMENT LIMIT
        # -------------------------------------------------

        if amount_paid > total:

            flash(
                "Total payment cannot be greater "
                "than the purchase total.",
                "warning"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

        balance = (
            total - amount_paid
        )

        # -------------------------------------------------
        # SUPPLIER
        # -------------------------------------------------

        supplier_id = (
            form.supplier_id.data
            if form.supplier_id.data != 0
            else None
        )

        # -------------------------------------------------
        # CREATE PURCHASE
        # -------------------------------------------------

        purchase = Purchase(
            company_id=
                current_user.company_id,

            supplier_id=
                supplier_id,

            purchase_number=
                generate_purchase_number(),

            purchase_date=
                form.purchase_date.data,

            expected_delivery_date=
                form.expected_delivery_date.data,

            supplier_invoice_number=
                form.supplier_invoice_number.data,

            subtotal=
                subtotal,

            discount=
                discount,

            tax=
                tax,

            total=
                total,

            paid_amount=
                amount_paid,

            balance=
                balance,

            status=
                "Completed",

            payment_status=
                calculate_payment_status(
                    total,
                    amount_paid
                ),

            notes=
                form.notes.data,

            created_by=
                current_user.id
        )

        db.session.add(
            purchase
        )

        db.session.flush()

        # -------------------------------------------------
        # PURCHASE ITEMS
        # -------------------------------------------------

        for item_data in items:

            product = item_data["product"]

            quantity = item_data["quantity"]

            purchase_item = PurchaseItem(
                purchase_id=
                    purchase.id,

                product_id=
                    product.id,

                quantity=
                    quantity,

                unit_cost=
                    item_data["unit_cost"],

                manufacturing_date=
                    item_data["manufacturing_date"],

                expiry_date=
                    item_data["expiry_date"],

                discount=
                    Decimal("0"),

                tax=
                    Decimal("0"),

                total=
                    item_data["total"]
            )

            db.session.add(
                purchase_item
            )

            # -------------------------------------------------
            # INCREASE PHYSICAL STOCK
            # -------------------------------------------------

            product.quantity += quantity

            # -------------------------------------------------
            # INVENTORY TRANSACTION
            # -------------------------------------------------

            inventory_transaction = (
                InventoryTransaction(
                    company_id=
                        current_user.company_id,

                    product_id=
                        product.id,

                    transaction_type=
                        "Purchase",

                    quantity=
                        quantity,

                    reference_type=
                        "Purchase",

                    reference_id=
                        purchase.id,

                    notes=(
                        f"Purchase "
                        f"{purchase.purchase_number}"
                    ),

                    created_by=
                        current_user.id
                )
            )

            db.session.add(
                inventory_transaction
            )

        # -------------------------------------------------
        # PAYMENT RECORDS
        # -------------------------------------------------

        for payment_data in payments:

            payment = Payment(
                company_id=
                    current_user.company_id,

                purchase_id=
                    purchase.id,

                amount=
                    payment_data["amount"],

                method=
                    payment_data["method"],

                bank_name=
                    payment_data["bank_name"],

                account_name=
                    payment_data["account_name"],

                account_number=
                    payment_data["account_number"],

                reference=
                    payment_data["reference"],

                notes=None,

                created_by=
                    current_user.id
            )

            db.session.add(
                payment
            )

        # =================================================
        # COMMIT
        # =================================================

        try:

            db.session.commit()

            # =================================================
            # NOTIFICATIONS
            # =================================================

            try:

                # -------------------------------------------------
                # PURCHASE NOTIFICATION
                # -------------------------------------------------
                #
                # DELIVERY CATEGORY:
                #     purchase
                #
                # SOUND:
                #     success
                #
                # NotificationAssignment controls who receives
                # this notification.
                #
                # User sound settings do NOT control delivery.
                # -------------------------------------------------

                notify_success(
                    company_id=
                        current_user.company_id,

                    title=
                        "Purchase Completed",

                    message=(
                        f"Purchase "
                        f"{purchase.purchase_number} "
                        f"was completed successfully "
                        f"for {format_currency(total)}."
                    ),

                    notification_category=
                        "purchase",

                    user_id=
                        current_user.id,

                    link=url_for(
                        "purchases.view_purchase",
                        purchase_id=
                            purchase.id
                    ),

                    reference_type=
                        "Purchase",

                    reference_id=
                        purchase.id
                )

                # -------------------------------------------------
                # FINANCIAL ALERTS
                # -------------------------------------------------

                run_purchase_financial_alerts(
                    purchase=
                        purchase,

                    user_id=
                        current_user.id
                )

            except Exception as notification_error:

                current_app.logger.exception(
                    "Notification processing failed "
                    "after purchase %s: %s",
                    purchase.purchase_number,
                    notification_error
                )

            flash(
                f"Purchase "
                f"{purchase.purchase_number} "
                "completed successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "purchases.view_purchase",
                    purchase_id=
                        purchase.id
                )
            )

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                "PURCHASE SAVE ERROR"
            )

            flash(
                f"Unable to save purchase: {exc}",
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers
            )

    return render_purchase_form(
        form,
        products,
        suppliers
    )


# =========================================================
# VIEW PURCHASE
# =========================================================

@purchases_bp.route(
    "/<int:purchase_id>"
)
@login_required
@company_permission_required("view_purchases")
def view_purchase(
    purchase_id
):

    purchase = (
        Purchase.query
        .filter(
            Purchase.id ==
                purchase_id,

            Purchase.company_id
                == current_user.company_id
        )
        .first_or_404()
    )

    return render_template(
        "purchases/view_purchase.html",
        purchase=purchase
    )


# =========================================================
# EDIT PURCHASE
# =========================================================

@purchases_bp.route(
    "/<int:purchase_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_purchases")
def edit_purchase(purchase_id):

    purchase = (
        Purchase.query
        .filter(
            Purchase.id == purchase_id,
            Purchase.company_id == current_user.company_id
        )
        .first_or_404()
    )

    form = PurchaseForm(obj=purchase)

    suppliers = get_purchase_suppliers()
    products = get_purchase_products()

    form.supplier_id.choices = [
        (
            0,
            "No Supplier / Cash Purchase"
        )
    ] + [
        (
            supplier.id,
            supplier.name
        )
        for supplier in suppliers
    ]

    # =====================================================
    # GET
    # =====================================================

    if request.method == "GET":

        form.supplier_id.data = (
            purchase.supplier_id or 0
        )

        form.amount_paid.data = (
            purchase.paid_amount or 0
        )

    # =====================================================
    # POST
    # =====================================================

    if form.validate_on_submit():

        # =================================================
        # DATE VALIDATION
        # =================================================

        date_error = validate_purchase_dates(form)

        if date_error:

            flash(
                date_error,
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

        # =================================================
        # FORM ITEMS
        # =================================================

        product_ids = request.form.getlist(
            "product_id"
        )

        quantities = request.form.getlist(
            "quantity"
        )

        unit_costs = request.form.getlist(
            "unit_cost"
        )

        manufacturing_dates = (
            request.form.getlist(
                "manufacturing_date"
            )
        )

        expiry_dates = (
            request.form.getlist(
                "expiry_date"
            )
        )

        items, error = validate_purchase_items(
            product_ids,
            quantities,
            unit_costs,
            manufacturing_dates,
            expiry_dates
        )

        if error:

            flash(
                error,
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

        # =================================================
        # TOTALS
        # =================================================

        discount = Decimal(
            form.discount.data or 0
        )

        tax = Decimal(
            form.tax.data or 0
        )

        subtotal, total = calculate_purchase_totals(
            items,
            discount,
            tax
        )

        if discount > subtotal:

            flash(
                "Discount cannot be greater than "
                "the purchase subtotal.",
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

        if total < 0:

            flash(
                "Purchase total cannot be negative.",
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

        # =================================================
        # PAYMENTS
        # =================================================

        payments, payment_result = (
            get_purchase_payment_data()
        )

        if payments is None:

            flash(
                payment_result,
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

        amount_paid = payment_result

        # =================================================
        # PAYMENT LIMIT
        # =================================================

        if amount_paid > total:

            flash(
                "Total payment cannot be greater "
                "than the purchase total.",
                "warning"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

        balance = total - amount_paid

        # =================================================
        # SAVE ORIGINAL ITEMS
        # =================================================

        old_items = list(
            purchase.items
        )

        # =================================================
        # BUILD OLD STOCK MAP
        # =================================================
        #
        # Product ID -> original purchase quantity
        #
        # This lets us compare the OLD purchase against
        # the NEW purchase instead of reversing everything.
        #
        # =================================================

        old_quantities = {}

        for old_item in old_items:

            product_id = old_item.product_id

            quantity = Decimal(
                str(old_item.quantity or 0)
            )

            old_quantities[product_id] = (
                old_quantities.get(
                    product_id,
                    Decimal("0")
                )
                + quantity
            )

        # =================================================
        # BUILD NEW STOCK MAP
        # =================================================

        new_quantities = {}

        for item_data in items:

            product = item_data["product"]

            quantity = Decimal(
                str(
                    item_data["quantity"] or 0
                )
            )

            new_quantities[product.id] = (
                new_quantities.get(
                    product.id,
                    Decimal("0")
                )
                + quantity
            )

        # =================================================
        # DETERMINE STOCK CHANGES
        # =================================================
        #
        # IMPORTANT:
        #
        # If old quantity = 9
        # New quantity = 9
        #
        # Delta = 0
        #
        # Therefore:
        # NO inventory reversal
        # NO inventory addition
        #
        # This allows payment/details edits even when stock
        # is currently reserved.
        #
        # =================================================

        all_product_ids = set(
            old_quantities.keys()
        ).union(
            new_quantities.keys()
        )

        stock_changes = {}

        for product_id in all_product_ids:

            old_quantity = old_quantities.get(
                product_id,
                Decimal("0")
            )

            new_quantity = new_quantities.get(
                product_id,
                Decimal("0")
            )

            delta = (
                new_quantity
                - old_quantity
            )

            if delta != 0:

                stock_changes[product_id] = delta

        # =================================================
        # VALIDATE STOCK REDUCTIONS ONLY
        # =================================================
        #
        # We only need to validate products where the
        # edited purchase is REDUCING stock.
        #
        # Payment-only edits have delta = 0 and therefore
        # completely skip this validation.
        #
        # =================================================

        for (
            product_id,
            delta
        ) in stock_changes.items():

            if delta >= 0:
                continue

            product = db.session.get(
                Product,
                product_id
            )

            if not product:

                flash(
                    "A product affected by this purchase "
                    "could not be found.",
                    "danger"
                )

                return render_purchase_form(
                    form,
                    products,
                    suppliers,
                    purchase
                )

            # -------------------------------------------------
            # COMPANY SECURITY CHECK
            # -------------------------------------------------

            if (
                product.company_id
                != current_user.company_id
            ):

                flash(
                    "A product affected by this purchase "
                    "does not belong to your company.",
                    "danger"
                )

                return render_purchase_form(
                    form,
                    products,
                    suppliers,
                    purchase
                )

            reduction = abs(delta)

            current_quantity = Decimal(
                str(
                    product.quantity or 0
                )
            )

            reserved_quantity = Decimal(
                str(
                    product.reserved_quantity or 0
                )
            )

            available_quantity = (
                current_quantity
                - reserved_quantity
            )

            if reduction > available_quantity:

                flash(
                    f"Cannot reduce "
                    f"{product.name} stock by "
                    f"{reduction} units because "
                    f"{current_quantity} units are physically "
                    f"in stock and "
                    f"{reserved_quantity} units are reserved. "
                    f"Only {available_quantity} units are "
                    f"available to reduce.",
                    "danger"
                )

                return render_purchase_form(
                    form,
                    products,
                    suppliers,
                    purchase
                )

        # =================================================
        # BEGIN DATABASE UPDATE
        # =================================================

        try:

            # =================================================
            # APPLY ONLY STOCK DIFFERENCES
            # =================================================
            #
            # This is the major fix.
            #
            # We DO NOT reverse the entire old purchase.
            #
            # We only apply:
            #
            # new quantity - old quantity
            #
            # =================================================

            for (
                product_id,
                delta
            ) in stock_changes.items():

                product = db.session.get(
                    Product,
                    product_id
                )

                if not product:

                    raise ValueError(
                        "Product affected by purchase "
                        "edit could not be found."
                    )

                # -------------------------------------------------
                # STOCK REDUCTION
                # -------------------------------------------------

                if delta < 0:

                    reduction = abs(delta)

                    product.quantity -= reduction

                    inventory_transaction = (
                        InventoryTransaction(
                            company_id=
                                current_user.company_id,

                            product_id=
                                product.id,

                            transaction_type=
                                "Purchase Edit Reduction",

                            quantity=
                                -reduction,

                            reference_type=
                                "Purchase",

                            reference_id=
                                purchase.id,

                            notes=(
                                f"Stock reduced by "
                                f"{reduction} units while "
                                f"editing purchase "
                                f"{purchase.purchase_number}"
                            ),

                            created_by=
                                current_user.id
                        )
                    )

                    db.session.add(
                        inventory_transaction
                    )

                # -------------------------------------------------
                # STOCK INCREASE
                # -------------------------------------------------

                elif delta > 0:

                    addition = delta

                    product.quantity += addition

                    inventory_transaction = (
                        InventoryTransaction(
                            company_id=
                                current_user.company_id,

                            product_id=
                                product.id,

                            transaction_type=
                                "Purchase Edit Addition",

                            quantity=
                                addition,

                            reference_type=
                                "Purchase",

                            reference_id=
                                purchase.id,

                            notes=(
                                f"Additional stock of "
                                f"{addition} units added "
                                f"while editing purchase "
                                f"{purchase.purchase_number}"
                            ),

                            created_by=
                                current_user.id
                        )
                    )

                    db.session.add(
                        inventory_transaction
                    )

            # =================================================
            # UPDATE PURCHASE
            # =================================================

            purchase.supplier_id = (
                form.supplier_id.data
                if form.supplier_id.data != 0
                else None
            )

            purchase.purchase_date = (
                form.purchase_date.data
            )

            purchase.expected_delivery_date = (
                form.expected_delivery_date.data
            )

            purchase.supplier_invoice_number = (
                form.supplier_invoice_number.data
            )

            purchase.subtotal = subtotal

            purchase.discount = discount

            purchase.tax = tax

            purchase.total = total

            purchase.paid_amount = amount_paid

            purchase.balance = balance

            purchase.payment_status = (
                calculate_payment_status(
                    total,
                    amount_paid
                )
            )

            purchase.notes = (
                form.notes.data
            )

            # =================================================
            # DELETE OLD PURCHASE ITEMS
            # =================================================
            #
            # This is safe because PurchaseItem records are
            # being replaced, while actual inventory has
            # already been adjusted only by the net difference.
            #
            # =================================================

            for old_item in old_items:

                db.session.delete(
                    old_item
                )

            db.session.flush()

            # =================================================
            # ADD NEW PURCHASE ITEMS
            # =================================================

            for item_data in items:

                product = (
                    item_data["product"]
                )

                quantity = (
                    item_data["quantity"]
                )

                purchase_item = PurchaseItem(
                    purchase_id=
                        purchase.id,

                    product_id=
                        product.id,

                    quantity=
                        quantity,

                    unit_cost=
                        item_data["unit_cost"],

                    manufacturing_date=
                        item_data[
                            "manufacturing_date"
                        ],

                    expiry_date=
                        item_data[
                            "expiry_date"
                        ],

                    discount=
                        Decimal("0"),

                    tax=
                        Decimal("0"),

                    total=
                        item_data["total"]
                )

                db.session.add(
                    purchase_item
                )

            # =================================================
            # UPDATE PAYMENT RECORDS
            # =================================================

            old_payments = list(
                purchase.payments
            )

            old_payment_map = {
                payment.id: payment
                for payment in old_payments
            }

            submitted_payment_ids = set()

            for payment_data in payments:

                payment_id = (
                    payment_data["id"]
                )

                # =================================================
                # EXISTING PAYMENT
                # =================================================

                if payment_id:

                    payment = (
                        old_payment_map.get(
                            payment_id
                        )
                    )

                    if not payment:

                        db.session.rollback()

                        flash(
                            "Invalid payment record submitted.",
                            "danger"
                        )

                        return render_purchase_form(
                            form,
                            products,
                            suppliers,
                            purchase
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

                    payment.notes = None

                # =================================================
                # NEW PAYMENT
                # =================================================

                else:

                    payment = Payment(
                        company_id=
                            current_user.company_id,

                        purchase_id=
                            purchase.id,

                        amount=
                            payment_data["amount"],

                        method=
                            payment_data["method"],

                        bank_name=
                            payment_data["bank_name"],

                        account_name=
                            payment_data["account_name"],

                        account_number=
                            payment_data["account_number"],

                        reference=
                            payment_data["reference"],

                        notes=None,

                        created_by=
                            current_user.id
                    )

                    db.session.add(
                        payment
                    )

            # =================================================
            # DELETE REMOVED PAYMENTS
            # =================================================

            for payment in old_payments:

                if (
                    payment.id
                    not in submitted_payment_ids
                ):

                    db.session.delete(
                        payment
                    )

            # =================================================
            # COMMIT
            # =================================================

            db.session.commit()

            # =================================================
            # NOTIFICATIONS
            # =================================================

            try:

                notify_success(
                    company_id=
                        current_user.company_id,

                    title=
                        "Purchase Updated",

                    message=(
                        f"Purchase "
                        f"{purchase.purchase_number} "
                        "was updated successfully."
                    ),

                    notification_category=
                        "purchase",

                    user_id=
                        current_user.id,

                    link=url_for(
                        "purchases.view_purchase",
                        purchase_id=
                            purchase.id
                    ),

                    reference_type=
                        "Purchase",

                    reference_id=
                        purchase.id
                )

                run_purchase_financial_alerts(
                    purchase=
                        purchase,

                    user_id=
                        current_user.id
                )

            except Exception as notification_error:

                current_app.logger.exception(
                    "Notification processing failed "
                    "after purchase update %s: %s",
                    purchase.purchase_number,
                    notification_error
                )

            # =================================================
            # SUCCESS
            # =================================================

            flash(
                f"Purchase "
                f"{purchase.purchase_number} "
                "updated successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "purchases.view_purchase",
                    purchase_id=
                        purchase.id
                )
            )

        # =====================================================
        # DATABASE ERROR
        # =====================================================

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                "PURCHASE EDIT ERROR"
            )

            flash(
                f"Unable to update purchase: {exc}",
                "danger"
            )

            return render_purchase_form(
                form,
                products,
                suppliers,
                purchase
            )

    # =====================================================
    # DEFAULT
    # =====================================================

    return render_purchase_form(
        form,
        products,
        suppliers,
        purchase
    )


# =========================================================
# DELETE PURCHASE
# =========================================================

@purchases_bp.route(
    "/<int:purchase_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_purchases")
def delete_purchase(purchase_id):

    purchase = (
        Purchase.query
        .filter(
            Purchase.id ==
                purchase_id,

            Purchase.company_id
                == current_user.company_id
        )
        .first_or_404()
    )

    # -----------------------------------------------------
    # SAVE PURCHASE NUMBER
    # -----------------------------------------------------

    purchase_number = (
        purchase.purchase_number
    )

    # -----------------------------------------------------
    # SAVE ITEMS
    # -----------------------------------------------------

    purchase_items = list(
        purchase.items
    )

    # -----------------------------------------------------
    # VERIFY STOCK
    # -----------------------------------------------------

    for item in purchase_items:

        product = item.product

        if not product:

            flash(
                "A product belonging to this purchase "
                "could not be found.",
                "danger"
            )

            return redirect(
                url_for(
                    "purchases.purchases"
                )
            )

        # -------------------------------------------------
        # COMPANY SECURITY CHECK
        # -------------------------------------------------

        if (
            product.company_id
            != current_user.company_id
        ):

            flash(
                "A product belonging to this purchase "
                "does not belong to your company.",
                "danger"
            )

            return redirect(
                url_for(
                    "purchases.purchases"
                )
            )

        current_quantity = Decimal(
            str(
                product.quantity or 0
            )
        )

        purchase_quantity = Decimal(
            str(
                item.quantity or 0
            )
        )

        reserved_quantity = Decimal(
            str(
                product.reserved_quantity or 0
            )
        )

        available_quantity = (
            current_quantity
            - reserved_quantity
        )

        if (
            purchase_quantity
            > available_quantity
        ):

            flash(
                f"Cannot delete purchase "
                f"{purchase_number}. "
                f"{product.name} has "
                f"{current_quantity} units physically "
                f"in stock, with "
                f"{reserved_quantity} units reserved. "
                f"Only {available_quantity} units are "
                f"available to reverse.",
                "danger"
            )

            return redirect(
                url_for(
                    "purchases.view_purchase",
                    purchase_id=
                        purchase.id
                )
            )

    # =====================================================
    # DATABASE OPERATION
    # =====================================================

    try:

        # -------------------------------------------------
        # REVERSE STOCK
        # -------------------------------------------------

        for item in purchase_items:

            product = item.product

            quantity = Decimal(
                str(
                    item.quantity
                )
            )

            product.quantity -= (
                quantity
            )

            inventory_transaction = (
                InventoryTransaction(
                    company_id=
                        current_user.company_id,

                    product_id=
                        product.id,

                    transaction_type=
                        "Purchase Reversal",

                    quantity=
                        -quantity,

                    reference_type=
                        "Purchase",

                    reference_id=
                        purchase.id,

                    notes=(
                        f"Purchase "
                        f"{purchase_number} "
                        "deleted"
                    ),

                    created_by=
                        current_user.id
                )
            )

            db.session.add(
                inventory_transaction
            )

        # -------------------------------------------------
        # SAVE FINANCIAL DATE BEFORE DELETE
        # -------------------------------------------------

        purchase_date = (
            purchase.purchase_date
        )

        if hasattr(
            purchase_date,
            "date"
        ):
            financial_date = (
                purchase_date.date()
            )
        else:
            financial_date = (
                purchase_date
            )

        # -------------------------------------------------
        # DELETE PURCHASE
        # -------------------------------------------------

        db.session.delete(
            purchase
        )

        db.session.commit()

        # =================================================
        # NOTIFICATIONS
        # =================================================

        try:

            # -------------------------------------------------
            # PURCHASE DELETE NOTIFICATION
            # -------------------------------------------------
            #
            # DELIVERY CATEGORY:
            #     purchase
            #
            # SOUND:
            #     success
            #
            # Only users assigned to the Purchase notification
            # category receive this notification.
            # -------------------------------------------------

            notify_success(
                company_id=
                    current_user.company_id,

                title=
                    "Purchase Deleted",

                message=(
                    f"Purchase "
                    f"{purchase_number} "
                    "was deleted successfully and "
                    "inventory was reversed."
                ),

                notification_category=
                    "purchase",

                user_id=
                    current_user.id,

                link=url_for(
                    "purchases.purchases"
                ),

                reference_type=
                    "Purchase",

                reference_id=
                    purchase_id
            )

            # -------------------------------------------------
            # FINANCIAL ALERTS
            # -------------------------------------------------

            if financial_date:

                start_datetime = (
                    datetime.combine(
                        financial_date,
                        datetime.min.time(),
                        tzinfo=timezone.utc
                    )
                )

                end_datetime = (
                    start_datetime
                    + timedelta(days=1)
                    - timedelta(
                        microseconds=1
                    )
                )

                check_financial_alerts(
                    company_id=
                        current_user.company_id,

                    start_datetime=
                        start_datetime,

                    end_datetime=
                        end_datetime,

                    user_id=
                        current_user.id
                )

        except Exception as notification_error:

            current_app.logger.exception(
                "Notification processing failed "
                "after purchase deletion %s: %s",
                purchase_number,
                notification_error
            )

        flash(
            f"Purchase "
            f"{purchase_number} "
            "deleted successfully and "
            "inventory was reversed.",
            "success"
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "PURCHASE DELETE ERROR"
        )

        flash(
            f"Unable to delete purchase: {exc}",
            "danger"
        )

    return redirect(
        url_for(
            "purchases.purchases"
        )
    )
