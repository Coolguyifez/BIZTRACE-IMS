from datetime import datetime, timezone
from hashlib import sha256
import hmac
import smtplib
from email.message import EmailMessage

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired
)

from app.extensions import db
from app.models import User, Company
from app.auth.forms import LoginForm, RegistrationForm
from app.rbac import initialize_company_rbac


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


# =========================================================
# PASSWORD RESET HELPERS
# =========================================================

RESET_TOKEN_SALT = "bizflow-password-reset-v1"
RESET_TOKEN_MAX_AGE = 7200  # 2 hours


def get_reset_serializer():

    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )


def get_password_fingerprint(user):

    return hmac.new(
        current_app.config["SECRET_KEY"].encode(),
        user.password_hash.encode(),
        sha256
    ).hexdigest()


def generate_password_reset_token(user):

    serializer = get_reset_serializer()

    return serializer.dumps(
        {
            "user_id": user.id,
            "fingerprint": get_password_fingerprint(user)
        },
        salt=RESET_TOKEN_SALT
    )


def verify_password_reset_token(token):

    serializer = get_reset_serializer()

    try:

        data = serializer.loads(
            token,
            salt=RESET_TOKEN_SALT,
            max_age=RESET_TOKEN_MAX_AGE
        )

    except SignatureExpired:

        current_app.logger.warning(
            "PASSWORD RESET: Token has expired."
        )

        return None

    except BadSignature:

        current_app.logger.warning(
            "PASSWORD RESET: Invalid reset token."
        )

        return None

    user_id = data.get("user_id")
    fingerprint = data.get("fingerprint")

    if not user_id or not fingerprint:

        current_app.logger.warning(
            "PASSWORD RESET: Reset token is missing required data."
        )

        return None

    user = db.session.get(
        User,
        user_id
    )

    if not user:

        current_app.logger.warning(
            "PASSWORD RESET: User associated with token does not exist."
        )

        return None

    current_fingerprint = get_password_fingerprint(
        user
    )

    if not hmac.compare_digest(
        fingerprint,
        current_fingerprint
    ):

        current_app.logger.warning(
            "PASSWORD RESET: Password fingerprint mismatch."
        )

        return None

    if not user.is_active:

        current_app.logger.warning(
            "PASSWORD RESET: User account is inactive."
        )

        return None

    return user


# =========================================================
# SEND PASSWORD RESET EMAIL
# =========================================================

def send_password_reset_email(user, reset_url):
    """
    Send the password reset email.

    IMPORTANT:

    MAIL_USERNAME
        = The email account used by the application
          to authenticate with the SMTP server.

    MAIL_DEFAULT_SENDER
        = The email address shown in the From field.

    user.email
        = The actual recipient who requested the
          password reset.
    """

    # -----------------------------------------------------
    # Get SMTP configuration
    # -----------------------------------------------------

    smtp_host = current_app.config.get(
        "MAIL_SERVER"
    )

    smtp_port = current_app.config.get(
        "MAIL_PORT",
        587
    )

    smtp_username = current_app.config.get(
        "MAIL_USERNAME"
    )

    smtp_password = current_app.config.get(
        "MAIL_PASSWORD"
    )

    mail_sender = current_app.config.get(
        "MAIL_DEFAULT_SENDER"
    )

    smtp_use_tls = current_app.config.get(
        "MAIL_USE_TLS",
        True
    )

    smtp_use_ssl = current_app.config.get(
        "MAIL_USE_SSL",
        False
    )

    # -----------------------------------------------------
    # Validate recipient
    # -----------------------------------------------------

    recipient_email = (
        user.email
        if user.email
        else ""
    ).strip().lower()

    if not recipient_email:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "User ID=%s has no email address.",
            user.id
        )

        return False

    # -----------------------------------------------------
    # Validate SMTP configuration
    # -----------------------------------------------------

    if not smtp_host:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "MAIL_SERVER is not configured."
        )

        return False

    if not smtp_username:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "MAIL_USERNAME is not configured."
        )

        return False

    if not smtp_password:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "MAIL_PASSWORD is not configured."
        )

        return False

    if not mail_sender:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "MAIL_DEFAULT_SENDER is not configured."
        )

        return False

    # -----------------------------------------------------
    # Log exactly where the email will go
    # -----------------------------------------------------

    current_app.logger.info(
        "=================================================="
    )

    current_app.logger.info(
        "PASSWORD RESET EMAIL"
    )

    current_app.logger.info(
        "User ID: %s",
        user.id
    )

    current_app.logger.info(
        "Username: %s",
        user.username
    )

    current_app.logger.info(
        "Database email / RECIPIENT: %s",
        recipient_email
    )

    current_app.logger.info(
        "SMTP account / SENDER ACCOUNT: %s",
        smtp_username
    )

    current_app.logger.info(
        "From address: %s",
        mail_sender
    )

    current_app.logger.info(
        "SMTP server: %s:%s",
        smtp_host,
        smtp_port
    )

    current_app.logger.info(
        "=================================================="
    )

    # -----------------------------------------------------
    # Create email
    # -----------------------------------------------------

    message = EmailMessage()

    message["Subject"] = (
        "Reset your BizTrace IMS password"
    )

    # This is the application sender.
    message["From"] = mail_sender

    # IMPORTANT:
    # This is the person requesting the reset.
    message["To"] = recipient_email

    message.set_content(
        f"""
Hello {user.username},

We received a request to reset your BizTrace IMS password.

Use the link below to create a new password:

{reset_url}

This password reset link expires in 2 hours.

If you did not request a password reset, you can safely ignore this email.

For security reasons, never share this link with anyone.

Regards,
BizTrace IMS
""".strip()
    )

    # -----------------------------------------------------
    # Send email
    # -----------------------------------------------------

    try:

        current_app.logger.info(
            "PASSWORD RESET: Connecting to SMTP server %s:%s",
            smtp_host,
            smtp_port
        )

        # -------------------------------------------------
        # SSL connection
        # -------------------------------------------------

        if smtp_use_ssl:

            current_app.logger.info(
                "PASSWORD RESET: Using SMTP SSL."
            )

            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                timeout=30
            ) as server:

                server.ehlo()

                current_app.logger.info(
                    "PASSWORD RESET: Authenticating SMTP account."
                )

                server.login(
                    smtp_username,
                    smtp_password
                )

                current_app.logger.info(
                    "PASSWORD RESET: Sending email TO: %s",
                    recipient_email
                )

                server.send_message(
                    message
                )

        # -------------------------------------------------
        # Normal SMTP + STARTTLS
        # -------------------------------------------------

        else:

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=30
            ) as server:

                server.ehlo()

                if smtp_use_tls:

                    current_app.logger.info(
                        "PASSWORD RESET: Starting TLS."
                    )

                    server.starttls()

                    server.ehlo()

                current_app.logger.info(
                    "PASSWORD RESET: Authenticating SMTP account."
                )

                server.login(
                    smtp_username,
                    smtp_password
                )

                current_app.logger.info(
                    "PASSWORD RESET: Sending email TO: %s",
                    recipient_email
                )

                server.send_message(
                    message
                )

        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        current_app.logger.info(
            "PASSWORD RESET: Email successfully accepted "
            "by SMTP server."
        )

        current_app.logger.info(
            "PASSWORD RESET: FINAL RECIPIENT = %s",
            recipient_email
        )

        return True

    # -----------------------------------------------------
    # SMTP authentication error
    # -----------------------------------------------------

    except smtplib.SMTPAuthenticationError:

        current_app.logger.exception(
            "PASSWORD RESET EMAIL ERROR: "
            "SMTP authentication failed."
        )

        return False

    # -----------------------------------------------------
    # SMTP connection error
    # -----------------------------------------------------

    except smtplib.SMTPConnectError:

        current_app.logger.exception(
            "PASSWORD RESET EMAIL ERROR: "
            "Could not connect to SMTP server."
        )

        return False

    # -----------------------------------------------------
    # General SMTP error
    # -----------------------------------------------------

    except smtplib.SMTPException:

        current_app.logger.exception(
            "PASSWORD RESET EMAIL ERROR: "
            "SMTP error occurred."
        )

        return False

    # -----------------------------------------------------
    # Any other error
    # -----------------------------------------------------

    except Exception:

        current_app.logger.exception(
            "PASSWORD RESET EMAIL ERROR: "
            "Unexpected email error."
        )

        return False


# =========================================================
# WELCOME
# =========================================================

@auth_bp.route("/welcome")
def welcome():

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    return render_template(
        "auth/welcome.html"
    )


# =========================================================
# LOGIN
# =========================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    form = LoginForm()

    if form.validate_on_submit():

        email = (
            form.email.data
            .lower()
            .strip()
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            not user
            or not user.check_password(
                form.password.data
            )
        ):

            flash(
                "Invalid email or password.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        if not user.is_active:

            flash(
                "Your account has been deactivated. "
                "Please contact your administrator.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        if user.is_system_admin:

            login_user(
                user,
                remember=form.remember.data
            )

            next_page = request.args.get(
                "next"
            )

            if next_page:

                return redirect(
                    next_page
                )

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        if user.company_id is None:

            flash(
                "Your account is not associated "
                "with a company.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        company = db.session.get(
            Company,
            user.company_id
        )

        if company is None:

            flash(
                "Your company account could not "
                "be found. Please contact support.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        if not company.is_active:

            flash(
                "Your company account is currently "
                "inactive. Please contact the "
                "system administrator.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        login_user(
            user,
            remember=form.remember.data
        )

        next_page = request.args.get(
            "next"
        )

        if next_page:

            return redirect(
                next_page
            )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    return render_template(
        "auth/login.html",
        form=form
    )


# =========================================================
# REGISTER
# =========================================================

@auth_bp.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    form = RegistrationForm()

    if form.validate_on_submit():

        try:

            company_email = (
                form.company_email.data
                .lower()
                .strip()
            )

            user_email = (
                form.email.data
                .lower()
                .strip()
            )

            company = Company(
                name=form.company_name.data.strip(),

                email=company_email,

                phone=(
                    form.company_phone.data.strip()
                    if form.company_phone.data
                    else None
                ),

                address=(
                    form.company_address.data.strip()
                    if form.company_address.data
                    else None
                ),

                is_active=True
            )

            db.session.add(
                company
            )

            db.session.flush()

            user = User(
                company_id=company.id,

                username=form.username.data.strip(),

                # IMPORTANT:
                # This is the email that belongs
                # to the actual user.
                email=user_email,

                role="Company Administrator",

                is_active=True
            )

            user.set_password(
                form.password.data
            )

            db.session.add(
                user
            )

            db.session.flush()

            initialize_company_rbac(
                company=company,
                administrator=user
            )

            db.session.commit()

            current_app.logger.info(
                "REGISTRATION: Created user ID=%s with email=%s",
                user.id,
                user.email
            )

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "Company registration failed."
            )

            flash(
                "We could not create your company "
                "account. Please try again.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.register"
                )
            )

        flash(
            "Your company account has been "
            "created successfully.",
            "success"
        )

        login_user(
            user
        )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    return render_template(
        "auth/register.html",
        form=form
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@auth_bp.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    if request.method == "POST":

        # -------------------------------------------------
        # Get email entered by the person
        # -------------------------------------------------

        email = (
            request.form.get(
                "email",
                ""
            )
            .lower()
            .strip()
        )

        current_app.logger.info(
            "PASSWORD RESET: Forgot-password request "
            "received for email=%s",
            email
        )

        # -------------------------------------------------
        # Find user by THEIR email
        # -------------------------------------------------

        user = User.query.filter_by(
            email=email
        ).first()

        if user and user.is_active:

            current_app.logger.info(
                "PASSWORD RESET: User found."
            )

            current_app.logger.info(
                "PASSWORD RESET: User ID=%s",
                user.id
            )

            current_app.logger.info(
                "PASSWORD RESET: Username=%s",
                user.username
            )

            current_app.logger.info(
                "PASSWORD RESET: DATABASE EMAIL=%s",
                user.email
            )

            try:

                # -----------------------------------------
                # Generate secure reset token
                # -----------------------------------------

                token = generate_password_reset_token(
                    user
                )

                # -----------------------------------------
                # Build reset URL
                # -----------------------------------------

                reset_url = url_for(
                    "auth.reset_password",
                    token=token,
                    _external=True
                )

                current_app.logger.info(
                    "PASSWORD RESET: Reset URL generated."
                )

                # -----------------------------------------
                # Send to user's email
                # -----------------------------------------

                email_sent = send_password_reset_email(
                    user,
                    reset_url
                )

                if email_sent:

                    current_app.logger.info(
                        "PASSWORD RESET: "
                        "Reset email sent successfully."
                    )

                    current_app.logger.info(
                        "PASSWORD RESET: "
                        "FINAL RECIPIENT=%s",
                        user.email
                    )

                else:

                    current_app.logger.error(
                        "PASSWORD RESET: "
                        "Failed to send reset email."
                    )

            except Exception:

                current_app.logger.exception(
                    "PASSWORD RESET: "
                    "Unexpected error processing request."
                )

        else:

            current_app.logger.info(
                "PASSWORD RESET: "
                "No active account found for requested email."
            )

        # -------------------------------------------------
        # Always keep response generic
        # -------------------------------------------------

        flash(
            "If an account exists for that email, "
            "a password reset link has been sent.",
            "success"
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    return render_template(
        "auth/forgot_password.html"
    )


# =========================================================
# RESET PASSWORD
# =========================================================

@auth_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    user = verify_password_reset_token(
        token
    )

    if not user:

        return render_template(
            "auth/reset_password.html",
            invalid_token=True
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if len(password) < 8:

            flash(
                "Password must be at least 8 "
                "characters long.",
                "danger"
            )

            return render_template(
                "auth/reset_password.html",
                invalid_token=False
            )

        if password != confirm_password:

            flash(
                "The passwords do not match.",
                "danger"
            )

            return render_template(
                "auth/reset_password.html",
                invalid_token=False
            )

        user.set_password(
            password
        )

        db.session.commit()

        current_app.logger.info(
            "PASSWORD RESET: Password successfully "
            "changed for user ID=%s",
            user.id
        )

        flash(
            "Your password has been reset successfully. "
            "You can now sign in.",
            "success"
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    return render_template(
        "auth/reset_password.html",
        invalid_token=False
    )


# =========================================================
# PROFILE
# =========================================================

@auth_bp.route(
    "/profile",
    methods=["GET", "POST"]
)
@login_required
def profile():

    if request.method == "POST":

        action = request.form.get(
            "action",
            ""
        ).strip()

        # =====================================================
        # UPDATE PROFILE INFORMATION
        # =====================================================

        if action == "update_profile":

            username = (
                request.form.get(
                    "username",
                    ""
                )
                .strip()
            )

            email = (
                request.form.get(
                    "email",
                    ""
                )
                .lower()
                .strip()
            )

            if not username:

                flash(
                    "Username is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            if not email:

                flash(
                    "Email address is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            existing_user = User.query.filter(
                User.email == email,
                User.id != current_user.id
            ).first()

            if existing_user:

                flash(
                    "That email address is already "
                    "being used by another account.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            current_user.username = username
            current_user.email = email

            db.session.commit()

            flash(
                "Your profile has been updated successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "auth.profile"
                )
            )

        # =====================================================
        # CHANGE PASSWORD
        # =====================================================

        if action == "change_password":

            current_password = request.form.get(
                "current_password",
                ""
            )

            new_password = request.form.get(
                "new_password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            if not current_user.check_password(
                current_password
            ):

                flash(
                    "Your current password is incorrect.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            if len(new_password) < 8:

                flash(
                    "Your new password must be at least "
                    "8 characters long.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            if new_password != confirm_password:

                flash(
                    "The new passwords do not match.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            if current_user.check_password(
                new_password
            ):

                flash(
                    "Your new password must be different "
                    "from your current password.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            current_user.set_password(
                new_password
            )

            db.session.commit()

            flash(
                "Your password has been changed successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "auth.profile"
                )
            )

        # =====================================================
        # APPEARANCE
        # =====================================================

        if action == "update_appearance":

            theme = request.form.get(
                "theme",
                "system"
            ).strip().lower()

            allowed_themes = {
                "light",
                "dark",
                "system"
            }

            if theme not in allowed_themes:

                flash(
                    "Invalid theme selected.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "auth.profile"
                    )
                )

            current_user.theme = theme

            db.session.commit()

            flash(
                "Appearance settings have been updated.",
                "success"
            )

            return redirect(
                url_for(
                    "auth.profile"
                )
            )

        # =====================================================
        # NOTIFICATION PREFERENCES
        # =====================================================

        if action == "update_notifications":

            current_user.notification_enabled = (
                request.form.get(
                    "notification_enabled"
                ) == "on"
            )

            current_user.browser_notification_enabled = (
                request.form.get(
                    "browser_notification_enabled"
                ) == "on"
            )

            current_user.email_notification_enabled = (
                request.form.get(
                    "email_notification_enabled"
                ) == "on"
            )

            current_user.sound_notification_enabled = (
                request.form.get(
                    "sound_notification_enabled"
                ) == "on"
            )

            db.session.commit()

            flash(
                "Notification preferences have been updated.",
                "success"
            )

            return redirect(
                url_for(
                    "auth.profile"
                )
            )

        # =====================================================
        # SOUND PREFERENCES
        # =====================================================

        if action == "update_sounds":

            current_user.success_sound_enabled = (
                request.form.get(
                    "success_sound_enabled"
                ) == "on"
            )

            current_user.system_sound_enabled = (
                request.form.get(
                    "system_sound_enabled"
                ) == "on"
            )

            current_user.error_sound_enabled = (
                request.form.get(
                    "error_sound_enabled"
                ) == "on"
            )

            current_user.low_stock_sound_enabled = (
                request.form.get(
                    "low_stock_sound_enabled"
                ) == "on"
            )

            current_user.gross_loss_sound_enabled = (
                request.form.get(
                    "gross_loss_sound_enabled"
                ) == "on"
            )

            current_user.net_loss_sound_enabled = (
                request.form.get(
                    "net_loss_sound_enabled"
                ) == "on"
            )

            db.session.commit()

            flash(
                "Sound preferences have been updated.",
                "success"
            )

            return redirect(
                url_for(
                    "auth.profile"
                )
            )

        flash(
            "Invalid profile action.",
            "danger"
        )

        return redirect(
            url_for(
                "auth.profile"
            )
        )

    # =========================================================
    # GET
    # =========================================================

    company = None

    if current_user.company_id:

        company = db.session.get(
            Company,
            current_user.company_id
        )

    return render_template(
        "auth/profile.html",
        user=current_user,
        company=company
    )


# =========================================================
# LOGOUT
# =========================================================

@auth_bp.route(
    "/logout"
)
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for(
            "auth.welcome"
        )
    )
