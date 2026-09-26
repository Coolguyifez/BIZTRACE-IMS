from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    TextAreaField,
    DecimalField,
    SelectField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional
)


# =========================================================
# CATEGORY FORM
# =========================================================

class CategoryForm(FlaskForm):

    name = StringField(
        "Category Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=250)
        ]
    )

    submit = SubmitField(
        "Save Category"
    )


# =========================================================
# PRODUCT FORM
# =========================================================

class ProductForm(FlaskForm):

    name = StringField(
        "Product Name",
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )

    sku = StringField(
        "SKU",
        validators=[
            DataRequired(),
            Length(min=1, max=80)
        ]
    )

    barcode = StringField(
        "Barcode",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    category_id = SelectField(
        "Category",
        coerce=int,
        validators=[
            Optional()
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    unit = StringField(
        "Unit",
        default="piece",
        validators=[
            DataRequired(),
            Length(max=30)
        ]
    )

    purchase_price = DecimalField(
        "Purchase Price",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    selling_price = DecimalField(
        "Selling Price",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    quantity = DecimalField(
        "Opening Stock",
        places=1,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    minimum_stock = DecimalField(
        "Minimum Stock Level",
        places=1,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    submit = SubmitField(
        "Save Product"
    )


# =========================================================
# CUSTOMER FORM
# =========================================================

class CustomerForm(FlaskForm):

    name = StringField(
        "Customer Name",
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )

    email = StringField(
        "Email",
        validators=[
            Optional(),
            Email()
        ]
    )

    phone = StringField(
        "Phone",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    address = StringField(
        "Address",
        validators=[
        Optional(),
            Length(max=250)
        ]
    )

    opening_balance = DecimalField(
        "Opening Balance",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    credit_limit = DecimalField(
        "Credit Limit",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    notes = TextAreaField(
        "Notes",
        validators=[
            Optional()
        ]
    )

    submit = SubmitField(
        "Save Customer"
    )


# =========================================================
# SUPPLIER FORM
# =========================================================

class SupplierForm(FlaskForm):

    name = StringField(
        "Supplier Name",
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )

    email = StringField(
        "Email",
        validators=[
            Optional(),
            Email()
        ]
    )

    phone = StringField(
        "Phone",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    address = StringField(
        "Address",
        validators=[
            Optional(),
            Length(max=250)
        ]
    )

    opening_balance = DecimalField(
        "Opening Balance",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    notes = TextAreaField(
        "Notes",
        validators=[
            Optional()
        ]
    )

    submit = SubmitField(
        "Save Supplier"
    )