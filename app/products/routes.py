from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request
)

from flask_login import login_required, current_user

from app.company_admin.decorators import company_permission_required
from app.extensions import db

from app.models import (
    Category,
    Product,
    InventoryTransaction,
    Customer,
    Supplier
)

from app.products.forms import (
    CategoryForm,
    ProductForm,
    CustomerForm,
    SupplierForm
)


products_bp = Blueprint(
    "products",
    __name__,
    url_prefix="/products"
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def clean_text(value):
    """
    Safely clean optional text fields.
    """
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def clean_required_text(value):
    """
    Safely clean required text fields.
    """
    return str(value or "").strip()


def company_id():
    """
    Return the currently authenticated user's company ID.
    """
    return current_user.company_id


# =========================================================
# CATEGORIES
# =========================================================

@products_bp.route("/categories")
@login_required
@company_permission_required("view_categories")
def categories():

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    query = Category.query.filter_by(
        company_id=company_id()
    )

    if search:
        query = query.filter(
            Category.name.ilike(f"%{search}%")
        )

    categories = query.order_by(
        Category.name.asc()
    ).all()

    return render_template(
        "products/categories.html",
        categories=categories,
        search=search
    )


@products_bp.route(
    "/categories/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_categories")
def new_category():

    form = CategoryForm()

    if form.validate_on_submit():

        name = clean_required_text(form.name.data)

        existing = Category.query.filter_by(
            company_id=company_id(),
            name=name
        ).first()

        if existing:
            flash(
                "A category with this name already exists.",
                "warning"
            )

            return render_template(
                "products/category_form.html",
                form=form,
                title="New Category"
            )

        category = Category(
            company_id=company_id(),
            name=name,
            description=clean_text(form.description.data)
        )

        try:
            db.session.add(category)
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to create the category. Please try again.",
                "danger"
            )

            return render_template(
                "products/category_form.html",
                form=form,
                title="New Category"
            )

        flash(
            "Category created successfully.",
            "success"
        )

        return redirect(
            url_for("products.categories")
        )

    return render_template(
        "products/category_form.html",
        form=form,
        title="New Category"
    )


@products_bp.route(
    "/categories/<int:category_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_categories")
def edit_category(category_id):

    category = Category.query.filter_by(
        id=category_id,
        company_id=company_id()
    ).first_or_404()

    form = CategoryForm(obj=category)

    if form.validate_on_submit():

        name = clean_required_text(form.name.data)

        duplicate = Category.query.filter(
            Category.company_id == company_id(),
            Category.name == name,
            Category.id != category.id
        ).first()

        if duplicate:
            flash(
                "Another category already uses this name.",
                "warning"
            )

            return render_template(
                "products/category_form.html",
                form=form,
                title="Edit Category"
            )

        category.name = name
        category.description = clean_text(
            form.description.data
        )

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update the category. Please try again.",
                "danger"
            )

            return render_template(
                "products/category_form.html",
                form=form,
                title="Edit Category"
            )

        flash(
            "Category updated successfully.",
            "success"
        )

        return redirect(
            url_for("products.categories")
        )

    return render_template(
        "products/category_form.html",
        form=form,
        title="Edit Category"
    )


@products_bp.route(
    "/categories/<int:category_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_categories")
def delete_category(category_id):

    category = Category.query.filter_by(
        id=category_id,
        company_id=company_id()
    ).first_or_404()

    if category.products:
        flash(
            "This category cannot be deleted because products are assigned to it.",
            "danger"
        )

        return redirect(
            url_for("products.categories")
        )

    try:
        db.session.delete(category)
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the category. Please try again.",
            "danger"
        )

        return redirect(
            url_for("products.categories")
        )

    flash(
        "Category deleted successfully.",
        "success"
    )

    return redirect(
        url_for("products.categories")
    )


# =========================================================
# PRODUCTS
# =========================================================

@products_bp.route("/")
@login_required
@company_permission_required("view_products")
def products():

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    category_id = request.args.get(
        "category",
        type=int
    )

    query = Product.query.filter_by(
        company_id=company_id()
    )

    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
                Product.barcode.ilike(f"%{search}%")
            )
        )

    if category_id:
        query = query.filter(
            Product.category_id == category_id
        )

    products = query.order_by(
        Product.name.asc()
    ).all()

    categories = Category.query.filter_by(
        company_id=company_id()
    ).order_by(
        Category.name.asc()
    ).all()

    return render_template(
        "products/products.html",
        products=products,
        categories=categories,
        search=search,
        selected_category=category_id
    )


# =========================================================
# NEW PRODUCT
# =========================================================

@products_bp.route(
    "/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_products")
def new_product():

    form = ProductForm()

    categories = Category.query.filter_by(
        company_id=company_id()
    ).order_by(
        Category.name.asc()
    ).all()

    form.category_id.choices = [
        (0, "No Category")
    ] + [
        (category.id, category.name)
        for category in categories
    ]

    if form.validate_on_submit():

        sku = clean_required_text(form.sku.data)

        existing = Product.query.filter_by(
            company_id=company_id(),
            sku=sku
        ).first()

        if existing:
            flash(
                "A product with this SKU already exists.",
                "warning"
            )

            return render_template(
                "products/product_form.html",
                form=form,
                title="New Product"
            )

        category_id = (
            form.category_id.data
            if form.category_id.data != 0
            else None
        )

        opening_stock = form.quantity.data or 0

        # -------------------------------------------------
        # Opening stock cannot be negative.
        # -------------------------------------------------

        if opening_stock < 0:
            flash(
                "Opening stock cannot be negative.",
                "warning"
            )

            return render_template(
                "products/product_form.html",
                form=form,
                title="New Product"
            )

        product = Product(
            company_id=company_id(),
            category_id=category_id,

            name=clean_required_text(
                form.name.data
            ),

            sku=sku,

            barcode=clean_text(
                form.barcode.data
            ),

            description=clean_text(
                form.description.data
            ),

            unit=clean_required_text(
                form.unit.data
            ),

            purchase_price=form.purchase_price.data or 0,
            selling_price=form.selling_price.data or 0,

            quantity=opening_stock,

            # New products never begin with reserved stock.
            reserved_quantity=0,

            minimum_stock=form.minimum_stock.data or 0,

            is_active=True
        )

        try:

            db.session.add(product)

            # Get product ID before creating inventory history.
            db.session.flush()

            # -------------------------------------------------
            # Record opening stock in inventory history.
            # -------------------------------------------------

            if opening_stock > 0:

                transaction = InventoryTransaction(
                    company_id=company_id(),
                    product_id=product.id,

                    transaction_type="Opening Stock",

                    quantity=opening_stock,

                    reference_type="Product",
                    reference_id=product.id,

                    notes=(
                        "Opening stock when product was created."
                    ),

                    created_by=current_user.id
                )

                db.session.add(transaction)

            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to create the product. Please try again.",
                "danger"
            )

            return render_template(
                "products/product_form.html",
                form=form,
                title="New Product"
            )

        flash(
            "Product created successfully.",
            "success"
        )

        return redirect(
            url_for("products.products")
        )

    return render_template(
        "products/product_form.html",
        form=form,
        title="New Product"
    )


# =========================================================
# EDIT PRODUCT
# =========================================================

@products_bp.route(
    "/<int:product_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_products")
def edit_product(product_id):

    product = Product.query.filter_by(
        id=product_id,
        company_id=company_id()
    ).first_or_404()

    form = ProductForm(obj=product)

    categories = Category.query.filter_by(
        company_id=company_id()
    ).order_by(
        Category.name.asc()
    ).all()

    form.category_id.choices = [
        (0, "No Category")
    ] + [
        (category.id, category.name)
        for category in categories
    ]

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    if request.method == "GET":

        form.category_id.data = (
            product.category_id
            if product.category_id
            else 0
        )

        form.quantity.data = product.quantity

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if form.validate_on_submit():

        sku = clean_required_text(form.sku.data)

        duplicate = Product.query.filter(
            Product.company_id == company_id(),
            Product.sku == sku,
            Product.id != product.id
        ).first()

        if duplicate:
            flash(
                "Another product already uses this SKU.",
                "warning"
            )

            return render_template(
                "products/product_form.html",
                form=form,
                title="Edit Product"
            )

        category_id = form.category_id.data

        # -------------------------------------------------
        # Prevent assigning a category belonging to another
        # company.
        # -------------------------------------------------

        if category_id and category_id != 0:

            category = Category.query.filter_by(
                id=category_id,
                company_id=company_id()
            ).first()

            if not category:
                flash(
                    "Invalid category selected.",
                    "danger"
                )

                return render_template(
                    "products/product_form.html",
                    form=form,
                    title="Edit Product"
                )

        product.category_id = (
            category_id
            if category_id != 0
            else None
        )

        product.name = clean_required_text(
            form.name.data
        )

        product.sku = sku

        product.barcode = clean_text(
            form.barcode.data
        )

        product.description = clean_text(
            form.description.data
        )

        product.unit = clean_required_text(
            form.unit.data
        )

        product.purchase_price = (
            form.purchase_price.data or 0
        )

        product.selling_price = (
            form.selling_price.data or 0
        )

        # -------------------------------------------------
        # IMPORTANT:
        #
        # Do NOT change product.quantity here.
        #
        # Inventory adjustments, purchases, sales and
        # reservations must control stock.
        # -------------------------------------------------

        product.minimum_stock = (
            form.minimum_stock.data or 0
        )

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update the product. Please try again.",
                "danger"
            )

            return render_template(
                "products/product_form.html",
                form=form,
                title="Edit Product"
            )

        flash(
            "Product updated successfully.",
            "success"
        )

        return redirect(
            url_for("products.products")
        )

    return render_template(
        "products/product_form.html",
        form=form,
        title="Edit Product"
    )


# =========================================================
# DELETE PRODUCT
# =========================================================

@products_bp.route(
    "/<int:product_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_products")
def delete_product(product_id):

    product = Product.query.filter_by(
        id=product_id,
        company_id=company_id()
    ).first_or_404()

    if product.inventory_transactions:
        flash(
            "This product cannot be deleted because it has inventory history.",
            "danger"
        )

        return redirect(
            url_for("products.products")
        )

    try:
        db.session.delete(product)
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the product. Please try again.",
            "danger"
        )

        return redirect(
            url_for("products.products")
        )

    flash(
        "Product deleted successfully.",
        "success"
    )

    return redirect(
        url_for("products.products")
    )


# =========================================================
# CUSTOMERS
# =========================================================

@products_bp.route("/customers")
@login_required
@company_permission_required("view_customers")
def customers():

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    query = Customer.query.filter_by(
        company_id=company_id()
    )

    if search:
        query = query.filter(
            db.or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%")
            )
        )

    customers = query.order_by(
        Customer.name.asc()
    ).all()

    return render_template(
        "products/customers.html",
        customers=customers,
        search=search
    )


@products_bp.route(
    "/customers/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_customers")
def new_customer():

    form = CustomerForm()

    if form.validate_on_submit():

        customer = Customer(
            company_id=company_id(),

            name=clean_required_text(
                form.name.data
            ),

            email=(
                form.email.data.lower().strip()
                if form.email.data
                else None
            ),

            phone=clean_text(
                form.phone.data
            ),

            address=clean_text(
                form.address.data
            ),

            opening_balance=(
                form.opening_balance.data or 0
            ),

            credit_limit=(
                form.credit_limit.data or 0
            ),

            notes=clean_text(
                form.notes.data
            )
        )

        try:
            db.session.add(customer)
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to create the customer. Please try again.",
                "danger"
            )

            return render_template(
                "products/customer_form.html",
                form=form,
                title="New Customer"
            )

        flash(
            "Customer created successfully.",
            "success"
        )

        return redirect(
            url_for("products.customers")
        )

    return render_template(
        "products/customer_form.html",
        form=form,
        title="New Customer"
    )


@products_bp.route(
    "/customers/<int:customer_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_customers")
def edit_customer(customer_id):

    customer = Customer.query.filter_by(
        id=customer_id,
        company_id=company_id()
    ).first_or_404()

    form = CustomerForm(obj=customer)

    if form.validate_on_submit():

        customer.name = clean_required_text(
            form.name.data
        )

        customer.email = (
            form.email.data.lower().strip()
            if form.email.data
            else None
        )

        customer.phone = clean_text(
            form.phone.data
        )

        customer.address = clean_text(
            form.address.data
        )

        customer.opening_balance = (
            form.opening_balance.data or 0
        )

        customer.credit_limit = (
            form.credit_limit.data or 0
        )

        customer.notes = clean_text(
            form.notes.data
        )

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update the customer. Please try again.",
                "danger"
            )

            return render_template(
                "products/customer_form.html",
                form=form,
                title="Edit Customer"
            )

        flash(
            "Customer updated successfully.",
            "success"
        )

        return redirect(
            url_for("products.customers")
        )

    return render_template(
        "products/customer_form.html",
        form=form,
        title="Edit Customer"
    )


@products_bp.route(
    "/customers/<int:customer_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_customers")
def delete_customer(customer_id):

    customer = Customer.query.filter_by(
        id=customer_id,
        company_id=company_id()
    ).first_or_404()

    try:
        db.session.delete(customer)
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the customer. Please try again.",
            "danger"
        )

        return redirect(
            url_for("products.customers")
        )

    flash(
        "Customer deleted successfully.",
        "success"
    )

    return redirect(
        url_for("products.customers")
    )


# =========================================================
# SUPPLIERS
# =========================================================

@products_bp.route("/suppliers")
@login_required
@company_permission_required("view_suppliers")
def suppliers():

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    query = Supplier.query.filter_by(
        company_id=company_id()
    )

    if search:
        query = query.filter(
            db.or_(
                Supplier.name.ilike(f"%{search}%"),
                Supplier.email.ilike(f"%{search}%"),
                Supplier.phone.ilike(f"%{search}%")
            )
        )

    suppliers = query.order_by(
        Supplier.name.asc()
    ).all()

    return render_template(
        "products/suppliers.html",
        suppliers=suppliers,
        search=search
    )


@products_bp.route(
    "/suppliers/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_suppliers")
def new_supplier():

    form = SupplierForm()

    if form.validate_on_submit():

        supplier = Supplier(
            company_id=company_id(),

            name=clean_required_text(
                form.name.data
            ),

            email=(
                form.email.data.lower().strip()
                if form.email.data
                else None
            ),

            phone=clean_text(
                form.phone.data
            ),

            address=clean_text(
                form.address.data
            ),

            opening_balance=(
                form.opening_balance.data or 0
            ),

            notes=clean_text(
                form.notes.data
            )
        )

        try:
            db.session.add(supplier)
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to create the supplier. Please try again.",
                "danger"
            )

            return render_template(
                "products/supplier_form.html",
                form=form,
                title="New Supplier"
            )

        flash(
            "Supplier created successfully.",
            "success"
        )

        return redirect(
            url_for("products.suppliers")
        )

    return render_template(
        "products/supplier_form.html",
        form=form,
        title="New Supplier"
    )


@products_bp.route(
    "/suppliers/<int:supplier_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_suppliers")
def edit_supplier(supplier_id):

    supplier = Supplier.query.filter_by(
        id=supplier_id,
        company_id=company_id()
    ).first_or_404()

    form = SupplierForm(obj=supplier)

    if form.validate_on_submit():

        supplier.name = clean_required_text(
            form.name.data
        )

        supplier.email = (
            form.email.data.lower().strip()
            if form.email.data
            else None
        )

        supplier.phone = clean_text(
            form.phone.data
        )

        supplier.address = clean_text(
            form.address.data
        )

        supplier.opening_balance = (
            form.opening_balance.data or 0
        )

        supplier.notes = clean_text(
            form.notes.data
        )

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update the supplier. Please try again.",
                "danger"
            )

            return render_template(
                "products/supplier_form.html",
                form=form,
                title="Edit Supplier"
            )

        flash(
            "Supplier updated successfully.",
            "success"
        )

        return redirect(
            url_for("products.suppliers")
        )

    return render_template(
        "products/supplier_form.html",
        form=form,
        title="Edit Supplier"
    )


@products_bp.route(
    "/suppliers/<int:supplier_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_suppliers")
def delete_supplier(supplier_id):

    supplier = Supplier.query.filter_by(
        id=supplier_id,
        company_id=company_id()
    ).first_or_404()

    try:
        db.session.delete(supplier)
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the supplier. Please try again.",
            "danger"
        )

        return redirect(
            url_for("products.suppliers")
        )

    flash(
        "Supplier deleted successfully.",
        "success"
    )

    return redirect(
        url_for("products.suppliers")
    )