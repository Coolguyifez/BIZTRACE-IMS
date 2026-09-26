from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)

from flask_login import (
    login_required,
    current_user,
)

from sqlalchemy import or_

from app.company_admin.decorators import (
    company_permission_required,
)

from app.extensions import db

from app.models import (
    Product,
    Category,
    InventoryTransaction,
)

from app.inventory.forms import (
    InventoryAdjustmentForm,
    InventoryReservationForm,
)

# =========================================================
# COMPANY SETTINGS
# =========================================================

from app.utils.company_settings import (
    format_currency,
)

# =========================================================
# NOTIFICATIONS
# =========================================================

from app.notifications.service import (
    notify_success,
    notify_low_stock,
)


inventory_bp = Blueprint(
    "inventory",
    __name__,
    url_prefix="/inventory",
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def decimal_value(value):
    """
    Safely convert a value to Decimal.
    """

    try:
        return Decimal(
            str(value or "0")
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return Decimal("0")


def clean_notes(value):
    """
    Clean optional notes.
    """

    if value:

        value = value.strip()

        return (
            value
            if value
            else None
        )

    return None


def product_choices(products):
    """
    Build product choices for select fields.
    """

    return [
        (
            product.id,
            (
                f"{product.name} — {product.sku} "
                f"(Stock: "
                f"{decimal_value(product.quantity):g}, "
                f"Available: "
                f"{decimal_value(product.available_quantity):g})"
            ),
        )
        for product in products
    ]


# =========================================================
# INVENTORY OVERVIEW
# =========================================================

@inventory_bp.route("/")
@login_required
@company_permission_required("view_inventory")
def inventory():

    search = request.args.get(
        "search",
        "",
        type=str,
    ).strip()

    category_id = request.args.get(
        "category",
        type=int,
    )

    status = request.args.get(
        "status",
        "",
        type=str,
    ).strip()

    # =====================================================
    # PRODUCTS
    # =====================================================

    query = Product.query.filter_by(
        company_id=current_user.company_id,
        is_active=True,
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search:

        query = query.filter(
            or_(
                Product.name.ilike(
                    f"%{search}%"
                ),
                Product.sku.ilike(
                    f"%{search}%"
                ),
                Product.barcode.ilike(
                    f"%{search}%"
                ),
            )
        )

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    if category_id:

        query = query.filter_by(
            category_id=category_id
        )

    products = (
        query
        .order_by(
            Product.name.asc()
        )
        .all()
    )

    # =====================================================
    # STATUS FILTER
    # =====================================================

    if status == "out":

        products = [
            product
            for product in products
            if decimal_value(
                product.quantity
            ) <= 0
        ]

    elif status == "low":

        products = [
            product
            for product in products
            if (
                decimal_value(
                    product.quantity
                ) > 0
                and product.is_low_stock
            )
        ]

    elif status == "in":

        products = [
            product
            for product in products
            if (
                decimal_value(
                    product.quantity
                ) > 0
                and not product.is_low_stock
            )
        ]

    elif status == "reserved":

        products = [
            product
            for product in products
            if decimal_value(
                product.reserved_quantity
            ) > 0
        ]

    elif status == "available":

        products = [
            product
            for product in products
            if decimal_value(
                product.available_quantity
            ) > 0
        ]

    # =====================================================
    # CATEGORIES
    # =====================================================

    categories = (
        Category.query
        .filter_by(
            company_id=current_user.company_id
        )
        .order_by(
            Category.name.asc()
        )
        .all()
    )

    # =====================================================
    # INVENTORY STATISTICS
    # =====================================================

    all_products = (
        Product.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True,
        )
        .all()
    )

    # -----------------------------------------------------
    # TOTAL PRODUCTS
    # -----------------------------------------------------

    total_products = len(
        all_products
    )

    # -----------------------------------------------------
    # TOTAL PHYSICAL UNITS
    # -----------------------------------------------------

    total_units = sum(
        (
            decimal_value(
                product.quantity
            )
            for product in all_products
        ),
        Decimal("0"),
    )

    # -----------------------------------------------------
    # TOTAL RESERVED
    # -----------------------------------------------------

    total_reserved = sum(
        (
            decimal_value(
                product.reserved_quantity
            )
            for product in all_products
        ),
        Decimal("0"),
    )

    # -----------------------------------------------------
    # TOTAL AVAILABLE
    # -----------------------------------------------------

    total_available = sum(
        (
            decimal_value(
                product.available_quantity
            )
            for product in all_products
        ),
        Decimal("0"),
    )

    # -----------------------------------------------------
    # TOTAL STOCK VALUE
    # -----------------------------------------------------

    total_stock_value = sum(
        (
            decimal_value(
                product.quantity
            )
            * decimal_value(
                product.purchase_price
            )
            for product in all_products
        ),
        Decimal("0"),
    )

    # -----------------------------------------------------
    # LOW STOCK
    # -----------------------------------------------------

    low_stock_count = sum(
        1
        for product in all_products
        if (
            decimal_value(
                product.quantity
            ) > 0
            and product.is_low_stock
        )
    )

    # -----------------------------------------------------
    # OUT OF STOCK
    # -----------------------------------------------------

    out_of_stock_count = sum(
        1
        for product in all_products
        if decimal_value(
            product.quantity
        ) <= 0
    )

    # -----------------------------------------------------
    # RESERVED PRODUCTS
    # -----------------------------------------------------

    reserved_products_count = sum(
        1
        for product in all_products
        if decimal_value(
            product.reserved_quantity
        ) > 0
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "inventory/inventory.html",

        products=products,

        categories=categories,

        search=search,

        selected_category=category_id,

        selected_status=status,

        total_products=total_products,

        total_units=total_units,

        total_reserved=total_reserved,

        total_available=total_available,

        total_stock_value=total_stock_value,

        low_stock_count=low_stock_count,

        out_of_stock_count=out_of_stock_count,

        reserved_products_count=
            reserved_products_count,

        # -------------------------------------------------
        # COMPANY CURRENCY
        # -------------------------------------------------

        format_currency=format_currency,
    )


# =========================================================
# STOCK ADJUSTMENT
# =========================================================

@inventory_bp.route(
    "/adjust",
    methods=["GET", "POST"],
)
@login_required
@company_permission_required("manage_inventory")
def adjust_stock():

    form = InventoryAdjustmentForm()

    preselected_product = request.args.get(
        "product",
        type=int,
    )

    products = (
        Product.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True,
        )
        .order_by(
            Product.name.asc()
        )
        .all()
    )

    form.product_id.choices = (
        product_choices(products)
    )

    # =====================================================
    # PRESELECT PRODUCT
    # =====================================================

    if (
        request.method == "GET"
        and preselected_product
        and any(
            product.id == preselected_product
            for product in products
        )
    ):

        form.product_id.data = (
            preselected_product
        )

    # =====================================================
    # VALIDATE
    # =====================================================

    if form.validate_on_submit():

        product = (
            Product.query
            .filter_by(
                id=form.product_id.data,
                company_id=current_user.company_id,
                is_active=True,
            )
            .first_or_404()
        )

        quantity = decimal_value(
            form.quantity.data
        )

        if quantity <= 0:

            flash(
                "Adjustment quantity must be greater than zero.",
                "danger",
            )

            return render_template(
                "inventory/adjust_form.html",
                form=form,
                title="Adjust Stock",
            )

        old_quantity = decimal_value(
            product.quantity
        )

        reserved_quantity = decimal_value(
            product.reserved_quantity
        )

        adjustment_type = (
            form.adjustment_type.data
        )

        # =================================================
        # INCREASE STOCK
        # =================================================

        if adjustment_type == "increase":

            new_quantity = (
                old_quantity
                + quantity
            )

            movement_quantity = quantity

        # =================================================
        # DECREASE STOCK
        # =================================================

        elif adjustment_type == "decrease":

            new_quantity = (
                old_quantity
                - quantity
            )

            if new_quantity < 0:

                flash(
                    (
                        f"Cannot decrease "
                        f"{product.name} "
                        f"by {quantity:g}. "
                        f"Current stock is "
                        f"{old_quantity:g}."
                    ),
                    "danger",
                )

                return render_template(
                    "inventory/adjust_form.html",
                    form=form,
                    title="Adjust Stock",
                )

            if new_quantity < reserved_quantity:

                available_quantity = (
                    old_quantity
                    - reserved_quantity
                )

                flash(
                    (
                        f"Cannot decrease stock by "
                        f"{quantity:g}. "
                        f"Only "
                        f"{available_quantity:g} "
                        f"is currently available."
                    ),
                    "danger",
                )

                return render_template(
                    "inventory/adjust_form.html",
                    form=form,
                    title="Adjust Stock",
                )

            movement_quantity = -quantity

        # =================================================
        # SET STOCK
        # =================================================

        elif adjustment_type == "set":

            new_quantity = quantity

            if new_quantity < reserved_quantity:

                flash(
                    (
                        f"Cannot set stock to "
                        f"{new_quantity:g}. "
                        f"{reserved_quantity:g} "
                        f"units are already reserved."
                    ),
                    "danger",
                )

                return render_template(
                    "inventory/adjust_form.html",
                    form=form,
                    title="Adjust Stock",
                )

            movement_quantity = (
                new_quantity
                - old_quantity
            )

        else:

            flash(
                "Invalid stock adjustment type.",
                "danger",
            )

            return render_template(
                "inventory/adjust_form.html",
                form=form,
                title="Adjust Stock",
            )

        # =================================================
        # NO CHANGE
        # =================================================

        if new_quantity == old_quantity:

            flash(
                "No stock change was made.",
                "warning",
            )

            return render_template(
                "inventory/adjust_form.html",
                form=form,
                title="Adjust Stock",
            )

        # =================================================
        # TRANSACTION
        # =================================================

        transaction = InventoryTransaction(
            company_id=
                current_user.company_id,

            product_id=
                product.id,

            transaction_type=
                "Adjustment",

            quantity=
                movement_quantity,

            reference_type=
                "Adjustment",

            reference_id=
                None,

            notes=
                clean_notes(
                    form.notes.data
                ),

            created_by=
                current_user.id,
        )

        product.quantity = (
            new_quantity
        )

        db.session.add(
            transaction
        )

        # =================================================
        # COMMIT
        # =================================================

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "An error occurred while "
                "updating stock.",
                "danger",
            )

            return render_template(
                "inventory/adjust_form.html",
                form=form,
                title="Adjust Stock",
            )

        # =================================================
        # SUCCESS NOTIFICATION
        # =================================================
        #
        # DELIVERY CATEGORY:
        #     inventory
        #
        # SOUND:
        #     success
        #
        # The service handles the sound. The notification
        # is delivered only to users assigned to Inventory.
        # =================================================

        direction = (
            "increased"
            if movement_quantity > 0
            else "decreased"
        )

        if adjustment_type == "set":

            notification_message = (
                f"Stock for {product.name} "
                f"was set to "
                f"{new_quantity:g} units."
            )

        else:

            notification_message = (
                f"Stock for {product.name} "
                f"was {direction} by "
                f"{abs(movement_quantity):g} units. "
                f"Current stock: "
                f"{new_quantity:g}."
            )

        notify_success(
            company_id=
                current_user.company_id,

            title=
                "Inventory updated",

            message=
                notification_message,

            # IMPORTANT:
            # This is the DELIVERY category.
            notification_category=
                "inventory",

            user_id=
                current_user.id,

            link=url_for(
                "inventory.product_inventory",
                product_id=product.id,
            ),

            reference_type=
                "Inventory",

            reference_id=
                product.id,
        )

        # =================================================
        # LOW STOCK NOTIFICATION
        # =================================================
        #
        # notify_low_stock() creates:
        #
        #     category = inventory
        #     sound    = low-stock
        #
        # Therefore Inventory assignment controls delivery.
        # The low-stock sound preference controls sound only.
        # =================================================

        if (
            decimal_value(
                product.quantity
            ) > 0
            and product.is_low_stock
        ):

            notify_low_stock(
                product,
                user_id=current_user.id,
            )

        flash(
            (
                f"Stock for {product.name} "
                "updated successfully."
            ),
            "success",
        )

        return redirect(
            url_for(
                "inventory.inventory"
            )
        )

    return render_template(
        "inventory/adjust_form.html",
        form=form,
        title="Adjust Stock",
    )


# =========================================================
# RESERVE / RELEASE STOCK
# =========================================================

@inventory_bp.route(
    "/reserve",
    methods=["GET", "POST"],
)
@login_required
@company_permission_required("manage_inventory")
def reserve_stock():

    form = InventoryReservationForm()

    preselected_product = request.args.get(
        "product",
        type=int,
    )

    products = (
        Product.query
        .filter_by(
            company_id=current_user.company_id,
            is_active=True,
        )
        .order_by(
            Product.name.asc()
        )
        .all()
    )

    form.product_id.choices = (
        product_choices(products)
    )

    # =====================================================
    # PRESELECT PRODUCT
    # =====================================================

    if (
        request.method == "GET"
        and preselected_product
        and any(
            product.id == preselected_product
            for product in products
        )
    ):

        form.product_id.data = (
            preselected_product
        )

    # =====================================================
    # VALIDATE
    # =====================================================

    if form.validate_on_submit():

        product = (
            Product.query
            .filter_by(
                id=form.product_id.data,
                company_id=current_user.company_id,
                is_active=True,
            )
            .first_or_404()
        )

        quantity = decimal_value(
            form.quantity.data
        )

        if quantity <= 0:

            flash(
                "Reservation quantity must be greater than zero.",
                "danger",
            )

            return render_template(
                "inventory/reservation_form.html",
                form=form,
                title="Reserve Stock",
            )

        physical_quantity = decimal_value(
            product.quantity
        )

        reserved_quantity = decimal_value(
            product.reserved_quantity
        )

        available_quantity = (
            physical_quantity
            - reserved_quantity
        )

        action = (
            form.action.data
        )

        # =================================================
        # RESERVE
        # =================================================

        if action == "reserve":

            if quantity > available_quantity:

                flash(
                    (
                        f"Cannot reserve "
                        f"{quantity:g} units. "
                        f"Only "
                        f"{available_quantity:g} "
                        f"units are available."
                    ),
                    "danger",
                )

                return render_template(
                    "inventory/reservation_form.html",
                    form=form,
                    title="Reserve Stock",
                )

            product.reserved_quantity = (
                reserved_quantity
                + quantity
            )

            transaction_quantity = (
                quantity
            )

            transaction_type = (
                "Reservation"
            )

        # =================================================
        # RELEASE
        # =================================================

        elif action == "release":

            if quantity > reserved_quantity:

                flash(
                    (
                        f"Cannot release "
                        f"{quantity:g} units. "
                        f"Only "
                        f"{reserved_quantity:g} "
                        f"units are currently reserved."
                    ),
                    "danger",
                )

                return render_template(
                    "inventory/reservation_form.html",
                    form=form,
                    title="Reserve Stock",
                )

            product.reserved_quantity = (
                reserved_quantity
                - quantity
            )

            transaction_quantity = (
                -quantity
            )

            transaction_type = (
                "Reservation Release"
            )

        else:

            flash(
                "Invalid reservation action.",
                "danger",
            )

            return render_template(
                "inventory/reservation_form.html",
                form=form,
                title="Reserve Stock",
            )

        # =================================================
        # TRANSACTION
        # =================================================

        transaction = InventoryTransaction(
            company_id=
                current_user.company_id,

            product_id=
                product.id,

            transaction_type=
                transaction_type,

            quantity=
                transaction_quantity,

            reference_type=
                "Reservation",

            reference_id=
                None,

            notes=
                clean_notes(
                    form.notes.data
                ),

            created_by=
                current_user.id,
        )

        db.session.add(
            transaction
        )

        # =================================================
        # COMMIT
        # =================================================

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                (
                    "An error occurred while "
                    "updating the reservation."
                ),
                "danger",
            )

            return render_template(
                "inventory/reservation_form.html",
                form=form,
                title="Reserve Stock",
            )

        # =================================================
        # NOTIFICATION
        # =================================================
        #
        # Both reservation and release use:
        #
        #     category = inventory
        #     sound    = success
        #
        # NotificationAssignment controls delivery.
        # The success sound setting controls sound only.
        # =================================================

        if action == "reserve":

            notify_success(
                company_id=
                    current_user.company_id,

                title=
                    "Stock reserved",

                message=(
                    f"{quantity:g} units of "
                    f"{product.name} were reserved. "
                    f"Available stock: "
                    f"{decimal_value(product.available_quantity):g}."
                ),

                notification_category=
                    "inventory",

                user_id=
                    current_user.id,

                link=url_for(
                    "inventory.product_inventory",
                    product_id=product.id,
                ),

                reference_type=
                    "Reservation",

                reference_id=
                    product.id,
            )

            flash(
                (
                    f"{quantity:g} units of "
                    f"{product.name} "
                    "reserved successfully."
                ),
                "success",
            )

        else:

            notify_success(
                company_id=
                    current_user.company_id,

                title=
                    "Stock reservation released",

                message=(
                    f"{quantity:g} units of "
                    f"{product.name} were released. "
                    f"Available stock: "
                    f"{decimal_value(product.available_quantity):g}."
                ),

                notification_category=
                    "inventory",

                user_id=
                    current_user.id,

                link=url_for(
                    "inventory.product_inventory",
                    product_id=product.id,
                ),

                reference_type=
                    "Reservation",

                reference_id=
                    product.id,
            )

            flash(
                (
                    f"{quantity:g} units of "
                    f"{product.name} "
                    "released successfully."
                ),
                "success",
            )

        # =================================================
        # LOW STOCK
        # =================================================
        #
        # Low-stock notification remains separate.
        #
        # Service:
        #
        #     category = inventory
        #     sound    = low-stock
        # =================================================

        if (
            action == "reserve"
            and decimal_value(
                product.quantity
            ) > 0
            and product.is_low_stock
        ):

            notify_low_stock(
                product,
                user_id=current_user.id,
            )

        return redirect(
            url_for(
                "inventory.inventory"
            )
        )

    return render_template(
        "inventory/reservation_form.html",
        form=form,
        title="Reserve / Release Stock",
    )


# =========================================================
# PRODUCT INVENTORY DETAILS
# =========================================================

@inventory_bp.route(
    "/product/<int:product_id>"
)
@login_required
@company_permission_required("view_inventory")
def product_inventory(product_id):

    product = (
        Product.query
        .filter_by(
            id=product_id,
            company_id=current_user.company_id,
        )
        .first_or_404()
    )

    transactions = (
        InventoryTransaction.query
        .filter_by(
            company_id=current_user.company_id,
            product_id=product.id,
        )
        .order_by(
            InventoryTransaction.created_at.desc()
        )
        .all()
    )

    # =====================================================
    # STOCK VALUES
    # =====================================================

    quantity = decimal_value(
        product.quantity
    )

    reserved_quantity = decimal_value(
        product.reserved_quantity
    )

    available_quantity = (
        quantity
        - reserved_quantity
    )

    # =====================================================
    # STOCK VALUE
    # =====================================================

    stock_value = (
        quantity
        * decimal_value(
            product.purchase_price
        )
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "inventory/product_inventory.html",

        product=product,

        transactions=transactions,

        quantity=quantity,

        reserved_quantity=
            reserved_quantity,

        available_quantity=
            available_quantity,

        stock_value=
            stock_value,

        # -------------------------------------------------
        # COMPANY CURRENCY
        # -------------------------------------------------

        format_currency=
            format_currency,
    )


# =========================================================
# INVENTORY HISTORY
# =========================================================

@inventory_bp.route(
    "/history"
)
@login_required
@company_permission_required("view_inventory")
def history():

    search = request.args.get(
        "search",
        "",
        type=str,
    ).strip()

    query = (
        InventoryTransaction.query
        .filter_by(
            company_id=current_user.company_id
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    if search:

        query = (
            query
            .join(
                Product,
                InventoryTransaction.product_id
                == Product.id
            )
            .filter(
                or_(
                    Product.name.ilike(
                        f"%{search}%"
                    ),

                    Product.sku.ilike(
                        f"%{search}%"
                    ),

                    InventoryTransaction
                    .transaction_type
                    .ilike(
                        f"%{search}%"
                    ),

                    InventoryTransaction
                    .notes
                    .ilike(
                        f"%{search}%"
                    ),
                )
            )
        )

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    transactions = (
        query
        .order_by(
            InventoryTransaction.created_at.desc()
        )
        .all()
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "inventory/history.html",

        transactions=
            transactions,

        search=
            search,

        # -------------------------------------------------
        # COMPANY CURRENCY
        # -------------------------------------------------

        format_currency=
            format_currency,
    )