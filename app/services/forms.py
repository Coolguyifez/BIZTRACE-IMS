from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    DecimalField,
    SubmitField
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional
)


class ServiceForm(FlaskForm):

    name = StringField(
        "Service Name",
        validators=[
            DataRequired(),
            Length(max=150)
        ]
    )

    service_code = StringField(
        "Service Code",
        validators=[
            DataRequired(),
            Length(max=80)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=5000)
        ]
    )

    price = DecimalField(
        "Price",
        validators=[
            DataRequired(),
            NumberRange(min=0)
        ],
        places=2
    )

    submit = SubmitField("Save Service")