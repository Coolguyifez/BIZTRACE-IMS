from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    DecimalField,
    TextAreaField,
    SubmitField
)
from wtforms.validators import (
    DataRequired,
    NumberRange,
    Optional
)


class InventoryAdjustmentForm(FlaskForm):

    product_id = SelectField(
        "Product",
        coerce=int,
        validators=[DataRequired()]
    )

    adjustment_type = SelectField(
        "Adjustment Type",
        choices=[
            ("increase", "Increase Stock"),
            ("decrease", "Decrease Stock"),
            ("set", "Set Stock Level")
        ],
        validators=[DataRequired()]
    )

    quantity = DecimalField(
        "Quantity",
        places=3,
        validators=[
            NumberRange(min=0)
        ]
    )

    notes = TextAreaField(
        "Reason / Notes",
        validators=[Optional()]
    )

    submit = SubmitField("Save Adjustment")

# =========================================================
# INVENTORY RESERVATION FORM
# =========================================================

class InventoryReservationForm(FlaskForm):

    product_id = SelectField(
        "Product",
        coerce=int,
        validators=[
            DataRequired()
        ]
    )

    action = SelectField(
        "Action",
        choices=[
            ("reserve", "Reserve Stock"),
            ("release", "Release Reservation")
        ],
        validators=[
            DataRequired()
        ]
    )

    quantity = DecimalField(
        "Quantity",
        places=3,
        validators=[
            DataRequired(),
            NumberRange(
                min=0.001,
                message="Quantity must be greater than zero."
            )
        ]
    )

    notes = TextAreaField(
        "Reason / Notes",
        validators=[
            Optional()
        ]
    )

    submit = SubmitField(
        "Save Reservation"
    )