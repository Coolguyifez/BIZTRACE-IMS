from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    StringField,
    DecimalField,
    DateField,
    TextAreaField,
    SubmitField
)
from wtforms.validators import (
    DataRequired,
    NumberRange,
    Optional,
    Length
)


class ExpenseForm(FlaskForm):

    category_id = SelectField(
        "Expense Category",
        coerce=int,
        validators=[DataRequired()]
    )

    description = StringField(
        "Description",
        validators=[
            DataRequired(),
            Length(max=250)
        ]
    )

    amount = DecimalField(
        "Amount",
        places=2,
        validators=[
            DataRequired(),
            NumberRange(min=0.01)
        ]
    )

    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("Cash", "Cash"),
            ("Bank Transfer", "Bank Transfer"),
            ("POS", "POS"),
            ("Card", "Card"),
            ("Other", "Other")
        ],
        validators=[DataRequired()]
    )

    expense_date = DateField(
        "Expense Date",
        default=date.today,
        validators=[DataRequired()]
    )

    reference = StringField(
        "Reference",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    notes = TextAreaField(
        "Notes",
        validators=[Optional()]
    )

    submit = SubmitField(
        "Save Expense"
    )

class ExpenseCategoryForm(FlaskForm):

    name = StringField(
        "Category Name",
        validators=[
            DataRequired(),
            Length(max=100)
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
        "Add Category"
    )