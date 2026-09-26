from flask_wtf import FlaskForm

from wtforms import (
    SelectField,
    DecimalField,
    DateField,
    TextAreaField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    NumberRange,
    Optional
)


class SaleForm(FlaskForm):

    # ========================================================
    # CUSTOMER
    # ========================================================

    customer_id = SelectField(
        "Customer",
        coerce=int,
        validators=[Optional()]
    )

    sale_date = DateField(
        "Sale Date",
        validators=[DataRequired()]
    )

    # ========================================================
    # FINANCIAL
    # ========================================================

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

    # ========================================================
    # NOTES
    # ========================================================

    notes = TextAreaField(
        "Sale Notes",
        validators=[Optional()]
    )

    # ========================================================
    # SUBMIT
    # ========================================================

    submit = SubmitField(
        "Complete Sale"
    )