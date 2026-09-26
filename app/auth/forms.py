from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo
)


class LoginForm(FlaskForm):

    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email()
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired()
        ]
    )

    remember = BooleanField(
        "Remember me"
    )

    submit = SubmitField(
        "Sign In"
    )


class RegistrationForm(FlaskForm):

    company_name = StringField(
        "Business Name",
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )

    company_email = StringField(
        "Business Email",
        validators=[
            DataRequired(),
            Email()
        ]
    )

    company_phone = StringField(
        "Business Phone",
        validators=[
            Length(max=50)
        ]
    )

    company_address = StringField(
        "Business Address",
        validators=[
            DataRequired(),
            Length(min=5, max=255)
        ]
    )

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=80)
        ]
    )

    email = StringField(
        "Administrator Email",
        validators=[
            DataRequired(),
            Email()
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8)
        ]
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo(
                "password",
                message="Passwords must match."
            )
        ]
    )

    submit = SubmitField(
        "Create Business"
    )

