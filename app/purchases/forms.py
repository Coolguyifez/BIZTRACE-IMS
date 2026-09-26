
from datetime import date

from flask_wtf import FlaskForm

from wtforms import (
    SelectField,
    DecimalField,
    DateField,
    TextAreaField,
    StringField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    NumberRange,
    Optional,
    Length
)


class PurchaseForm(FlaskForm):

    # =====================================================
    # SUPPLIER
    # =====================================================

    supplier_id = SelectField(
        "Supplier",
        coerce=int,
        validators=[
            Optional()
        ]
    )

    # =====================================================
    # PURCHASE DATES
    # =====================================================

    purchase_date = DateField(
        "Purchase Date",
        default=date.today,
        validators=[
            DataRequired()
        ]
    )

    expected_delivery_date = DateField(
        "Expected Delivery Date",
        validators=[
            Optional()
        ]
    )

    # =====================================================
    # SUPPLIER REFERENCE
    # =====================================================

    supplier_invoice_number = StringField(
        "Supplier Invoice / Reference",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    # =====================================================
    # FINANCIAL
    # =====================================================

    discount = DecimalField(
        "Discount",
        places=2,
        default=0,
        validators=[
            NumberRange(min=0)
        ]
    )

    tax = DecimalField(
        "Tax",
        places=2,
        default=0,
        validators=[
            NumberRange(min=0)
        ]
    )

    # =====================================================
    # PAYMENT
    #
    # These fields are kept for backward compatibility.
    # Multiple payments are now submitted dynamically from
    # the purchase form and processed manually in routes.py.
    #
    # They MUST NOT be required here.
    # =====================================================

    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("Cash", "Cash"),
            ("Bank Transfer", "Bank Transfer"),
            ("POS", "POS"),
            ("Card", "Card"),
            ("Other", "Other")
        ],
        validators=[
            Optional()
        ]
    )

    amount_paid = DecimalField(
        "Amount Paid",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0)
        ]
    )

    # =====================================================
    # PAYMENT DETAILS
    #
    # These are also kept for compatibility with older
    # templates/routes. The new multiple-payment rows are
    # processed from request.form.
    # =====================================================

    bank_name = StringField(
        "Bank Name",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    account_name = StringField(
        "Account Name",
        validators=[
            Optional(),
            Length(max=150)
        ]
    )

    account_number = StringField(
        "Account Number",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    payment_reference = StringField(
        "Payment Reference",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    # =====================================================
    # NOTES
    # =====================================================

    notes = TextAreaField(
        "Purchase Notes",
        validators=[
            Optional()
        ]
    )

    # =====================================================
    # SUBMIT
    # =====================================================

    submit = SubmitField(
        "Complete Purchase"
    )

