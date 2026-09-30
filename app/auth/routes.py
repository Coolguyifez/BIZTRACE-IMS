from datetime import datetime, timezone
from hashlib import sha256
import hmac

import resend

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)

from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired,
)

from app.extensions import db
from app.models import User, Company
from app.auth.forms import LoginForm, RegistrationForm
from app.rbac import initialize_company_rbac


# ============================================================
# BLUEPRINT
# ============================================================

auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
)


# ============================================================
# PASSWORD RESET SETTINGS
# ============================================================

RESET_TOKEN_SALT = "bizflow-password-reset-v1"
RESET_TOKEN_MAX_AGE = 7200  # 2 hours


# ============================================================
# PASSWORD RESET HELPERS
# ============================================================

def get_reset_serializer():

    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )


def get_password_fingerprint(user):

    password_hash = user.password_hash or ""

    return hmac.new(
        current_app.config["SECRET_KEY"].encode(),
        password_hash.encode(),
        sha256,
    ).hexdigest()


def generate_password_reset_token(user):

    serializer = get_reset_serializer()

    return serializer.dumps(
        {
            "user_id": user.id,
            "fingerprint": get_password_fingerprint(user),
        },
        salt=RESET_TOKEN_SALT,
    )


def verify_password_reset_token(token):

    serializer = get_reset_serializer()

    try:

        data = serializer.loads(
            token,
            salt=RESET_TOKEN_SALT,
            max_age=RESET_TOKEN_MAX_AGE,
        )

    except SignatureExpired:

        return None

    except BadSignature:

        return None

    if not isinstance(data, dict):

        return None

    user_id = data.get("user_id")
    fingerprint = data.get("fingerprint")

    if not user_id or not fingerprint:

        return None

    user = db.session.get(
        User,
        user_id,
    )

    if not user:

        return None

    current_fingerprint = get_password_fingerprint(
        user
    )

    if not hmac.compare_digest(
        fingerprint,
        current_fingerprint,
    ):

        return None

    return user


# ============================================================
# SEND PASSWORD RESET EMAIL
# RESEND
# ============================================================

def send_password_reset_email(
    user,
    reset_url,
):

    resend_api_key = current_app.config.get(
        "RESEND_API_KEY"
    )

    sender_email = current_app.config.get(
        "RESEND_FROM_EMAIL"
    )

    # --------------------------------------------------------
    # RESEND API KEY
    # --------------------------------------------------------

    if not resend_api_key:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "RESEND_API_KEY is not configured."
        )

        current_app.logger.error(
            "PASSWORD RESET URL: %s",
            reset_url,
        )

        return False

    # --------------------------------------------------------
    # SENDER EMAIL
    # --------------------------------------------------------

    if not sender_email:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "RESEND_FROM_EMAIL is not configured."
        )

        current_app.logger.error(
            "PASSWORD RESET URL: %s",
            reset_url,
        )

        return False

    # --------------------------------------------------------
    # RECIPIENT
    # --------------------------------------------------------

    recipient_email = (
        user.email or ""
    ).strip().lower()

    if not recipient_email:

        current_app.logger.error(
            "PASSWORD RESET EMAIL ERROR: "
            "User ID=%s has no email address.",
            user.id,
        )

        return False

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    current_app.logger.info(
        "=================================================="
    )

    current_app.logger.info(
        "PASSWORD RESET EMAIL"
    )

    current_app.logger.info(
        "User ID: %s",
        user.id,
    )

    current_app.logger.info(
        "Username: %s",
        user.username,
    )

    current_app.logger.info(
        "DATABASE EMAIL / RECIPIENT: %s",
        recipient_email,
    )

    current_app.logger.info(
        "RESEND SENDER: %s",
        sender_email,
    )

    current_app.logger.info(
        "=================================================="
    )

    # --------------------------------------------------------
    # CONFIGURE RESEND
    # --------------------------------------------------------

    resend.api_key = resend_api_key

    # --------------------------------------------------------
    # EMAIL HTML
    # --------------------------------------------------------

    html_content = f"""
<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Reset your BizTrace IMS password</title>

</head>

<body
    style="
        margin:0;
        padding:0;
        background:#f5f7fb;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            'Segoe UI',
            Roboto,
            Helvetica,
            Arial,
            sans-serif;
    "
>

    <div
        style="
            max-width:600px;
            margin:40px auto;
            padding:20px;
        "
    >

        <div
            style="
                background:#ffffff;
                border-radius:16px;
                padding:40px 30px;
                box-shadow:
                    0 4px 20px
                    rgba(0,0,0,0.06);
            "
        >

            <!-- BRAND -->

            <div
                style="
                    text-align:center;
                    margin-bottom:30px;
                "
            >

                <h1
                    style="
                        margin:0;
                        color:#0a84ff;
                        font-size:28px;
                        font-weight:700;
                    "
                >
                    BizTrace IMS
                </h1>

                <p
                    style="
                        margin:8px 0 0;
                        color:#6b7280;
                        font-size:14px;
                    "
                >
                    Inventory Management System
                </p>

            </div>

            <!-- CONTENT -->

            <h2
                style="
                    margin:0 0 16px;
                    color:#111827;
                    font-size:22px;
                "
            >
                Reset your password
            </h2>

            <p
                style="
                    color:#374151;
                    font-size:15px;
                    line-height:1.7;
                "
            >
                Hello {user.username},
            </p>

            <p
                style="
                    color:#374151;
                    font-size:15px;
                    line-height:1.7;
                "
            >
                We received a request to reset the password
                for your BizTrace IMS account.
            </p>

            <p
                style="
                    color:#374151;
                    font-size:15px;
                    line-height:1.7;
                "
            >
                Click the button below to create a new password.
            </p>

            <!-- BUTTON -->

            <div
                style="
                    text-align:center;
                    margin:30px 0;
                "
            >

                <a
                    href="{reset_url}"
                    style="
                        display:inline-block;
                        padding:14px 26px;
                        background:#0a84ff;
                        color:#ffffff;
                        text-decoration:none;
                        border-radius:10px;
                        font-size:15px;
                        font-weight:600;
                    "
                >
                    Reset Password
                </a>

            </div>

            <!-- FALLBACK LINK -->

            <p
                style="
                    color:#6b7280;
                    font-size:13px;
                    line-height:1.6;
                "
            >
                If the button does not work, copy and paste
                the following link into your browser:
            </p>

            <p
                style="
                    word-break:break-all;
                    background:#f3f4f6;
                    padding:12px;
                    border-radius:8px;
                    color:#374151;
                    font-size:12px;
                "
            >
                {reset_url}
            </p>

            <!-- SECURITY -->

            <div
                style="
                    margin-top:30px;
                    padding:16px;
                    background:#f8fafc;
                    border-radius:10px;
                "
            >

                <p
                    style="
                        margin:0;
                        color:#4b5563;
                        font-size:13px;
                        line-height:1.6;
                    "
                >
                    <strong>Security notice:</strong>
                    This password reset link expires in
                    2 hours. If you did not request a
                    password reset, you can safely ignore
                    this email.
                </p>

            </div>

            <!-- FOOTER -->

            <div
                style="
                    margin-top:35px;
                    padding-top:20px;
                    border-top:1px solid #e5e7eb;
                    text-align:center;
                "
            >

                <p
                    style="
                        margin:0;
                        color:#9ca3af;
                        font-size:12px;
                    "
                >
                    Regards,<br>
                    <strong>BizTrace IMS</strong>
                </p>

            </div>

        </div>

    </div>

</body>

</html>
"""

    # --------------------------------------------------------
    # SEND EMAIL
    # --------------------------------------------------------

    try:

        current_app.logger.info(
            "PASSWORD RESET: Sending email through Resend."
        )

        current_app.logger.info(
            "PASSWORD RESET: FINAL RECIPIENT = %s",
            recipient_email,
        )

        params = {
            "from": sender_email,
            "to": [recipient_email],
            "subject": "Reset your BizTrace IMS password",
            "html": html_content,
        }

        response = resend.Emails.send(
            params
        )

        current_app.logger.info(
            "PASSWORD RESET: Resend accepted email."
        )

        current_app.logger.info(
            "PASSWORD RESET: Recipient = %s",
            recipient_email,
        )

        current_app.logger.info(
            "PASSWORD RESET: Resend response = %s",
            response,
        )

        return True

    except Exception:

        current_app.logger.exception(
            "PASSWORD RESET EMAIL ERROR: "
            "Resend failed to send email."
        )

        return False


# ============================================================
# WELCOME
# ============================================================

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


# ============================================================
# LOGIN
# ============================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    # --------------------------------------------------------
    # ALREADY LOGGED IN
    # --------------------------------------------------------

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        # Do not redirect based on company status here.
        # The global before_request handler handles access.

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    form = LoginForm()

    if form.validate_on_submit():

        email = (
            form.email.data or ""
        ).lower().strip()

        password = form.password.data or ""

        user = User.query.filter_by(
            email=email
        ).first()

        # ----------------------------------------------------
        # INVALID LOGIN
        # ----------------------------------------------------

        if (
            not user
            or not user.check_password(password)
        ):

            flash(
                "Invalid email or password.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ----------------------------------------------------
        # USER DEACTIVATED
        # ----------------------------------------------------

        if not user.is_active:

            flash(
                "Your account has been deactivated. "
                "Please contact your administrator.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ----------------------------------------------------
        # SYSTEM ADMIN
        # ----------------------------------------------------

        if user.is_system_admin:

            login_user(
                user,
                remember=form.remember.data,
            )

            next_page = request.args.get(
                "next"
            )

            if next_page:
                return redirect(next_page)

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        # ----------------------------------------------------
        # COMPANY REQUIRED
        # ----------------------------------------------------

        if user.company_id is None:

            flash(
                "Your account is not associated "
                "with a company.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ----------------------------------------------------
        # GET COMPANY
        # ----------------------------------------------------

        company = db.session.get(
            Company,
            user.company_id,
        )

        if company is None:

            flash(
                "Your company account could not "
                "be found. Please contact support.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ----------------------------------------------------
        # COMPANY DEACTIVATED
        # ----------------------------------------------------
        #
        # IMPORTANT:
        #
        # We DO NOT login the user.
        #
        # We render the login page directly instead of
        # redirecting to /login again.
        #
        # This prevents:
        #
        # /login -> /login -> /login
        #
        # ----------------------------------------------------

        if not company.is_active:

            flash(
                "COMPANY_DEACTIVATED",
                "company_deactivated"
            )

            return render_template(
                "auth/login.html",
                form=form,
                company_deactivated=True,
            )

        # ----------------------------------------------------
        # LOGIN
        # ----------------------------------------------------

        login_user(
            user,
            remember=form.remember.data,
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

    # ========================================================
    # GET / INVALID POST
    # ========================================================

    return render_template(
        "auth/login.html",
        form=form,
        company_deactivated=False,
    )


# ============================================================
# REGISTER
# ============================================================

@auth_bp.route(
    "/register",
    methods=["GET", "POST"],
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

            company = Company(
                name=(
                    form.company_name.data or ""
                ).strip(),

                email=(
                    form.company_email.data or ""
                ).lower().strip(),

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

                is_active=True,
            )

            db.session.add(
                company
            )

            db.session.flush()

            user = User(
                company_id=company.id,

                username=(
                    form.username.data or ""
                ).strip(),

                email=(
                    form.email.data or ""
                ).lower().strip(),

                role="Company Administrator",

                is_active=True,
            )

            user.set_password(
                form.password.data
            )

            db.session.add(
                user
            )

            db.session.flush()

            # ------------------------------------------------
            # INITIALIZE COMPANY RBAC
            # ------------------------------------------------

            initialize_company_rbac(
                company=company,
                administrator=user,
            )

            db.session.commit()

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "Company registration failed."
            )

            flash(
                "We could not create your company "
                "account. Please try again.",
                "danger",
            )

            return redirect(
                url_for("auth.register")
            )

        # ----------------------------------------------------
        # LOGIN NEW COMPANY ADMIN
        # ----------------------------------------------------

        login_user(
            user
        )

        flash(
            "Your company account has been "
            "created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    return render_template(
        "auth/register.html",
        form=form,
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth_bp.route(
    "/forgot-password",
    methods=["GET", "POST"],
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

        email = (
            request.form.get(
                "email",
                "",
            )
            .lower()
            .strip()
        )

        current_app.logger.info(
            "PASSWORD RESET: "
            "Forgot-password request received "
            "for email=%s",
            email,
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if user and user.is_active:

            current_app.logger.info(
                "PASSWORD RESET: User found."
            )

            current_app.logger.info(
                "PASSWORD RESET: User ID=%s",
                user.id,
            )

            current_app.logger.info(
                "PASSWORD RESET: DATABASE EMAIL=%s",
                user.email,
            )

            try:

                token = generate_password_reset_token(
                    user
                )

                reset_url = url_for(
                    "auth.reset_password",
                    token=token,
                    _external=True,
                )

                email_sent = send_password_reset_email(
                    user,
                    reset_url,
                )

                if email_sent:

                    current_app.logger.info(
                        "PASSWORD RESET: "
                        "Reset email sent successfully."
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
                "No active account found."
            )

        # ----------------------------------------------------
        # GENERIC RESPONSE
        # ----------------------------------------------------

        flash(
            "If an account exists for that email, "
            "a password reset link has been sent.",
            "success",
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    return render_template(
        "auth/forgot_password.html"
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@auth_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"],
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
            invalid_token=True,
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        # ----------------------------------------------------
        # PASSWORD LENGTH
        # ----------------------------------------------------

        if len(password) < 8:

            flash(
                "Password must be at least 8 "
                "characters long.",
                "danger",
            )

            return render_template(
                "auth/reset_password.html",
                invalid_token=False,
            )

        # ----------------------------------------------------
        # CONFIRM PASSWORD
        # ----------------------------------------------------

        if password != confirm_password:

            flash(
                "The passwords do not match.",
                "danger",
            )

            return render_template(
                "auth/reset_password.html",
                invalid_token=False,
            )

        # ----------------------------------------------------
        # UPDATE PASSWORD
        # ----------------------------------------------------

        user.set_password(
            password
        )

        db.session.commit()

        flash(
            "Your password has been reset successfully. "
            "You can now sign in.",
            "success",
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "auth/reset_password.html",
        invalid_token=False,
    )


# ============================================================
# PROFILE
# ============================================================

@auth_bp.route(
    "/profile",
    methods=["GET", "POST"],
)
@login_required
def profile():

    if request.method == "POST":

        action = request.form.get(
            "action",
            "",
        ).strip()

        # ====================================================
        # UPDATE PROFILE
        # ====================================================

        if action == "update_profile":

            username = (
                request.form.get(
                    "username",
                    "",
                )
                .strip()
            )

            email = (
                request.form.get(
                    "email",
                    "",
                )
                .lower()
                .strip()
            )

            if not username:

                flash(
                    "Username is required.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            if not email:

                flash(
                    "Email address is required.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            existing_user = User.query.filter(
                User.email == email,
                User.id != current_user.id,
            ).first()

            if existing_user:

                flash(
                    "That email address is already "
                    "being used by another account.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            current_user.username = username
            current_user.email = email

            db.session.commit()

            flash(
                "Your profile has been updated successfully.",
                "success",
            )

            return redirect(
                url_for("auth.profile")
            )

        # ====================================================
        # CHANGE PASSWORD
        # ====================================================

        if action == "change_password":

            current_password = request.form.get(
                "current_password",
                "",
            )

            new_password = request.form.get(
                "new_password",
                "",
            )

            confirm_password = request.form.get(
                "confirm_password",
                "",
            )

            if not current_user.check_password(
                current_password
            ):

                flash(
                    "Your current password is incorrect.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            if len(new_password) < 8:

                flash(
                    "Your new password must be at least "
                    "8 characters long.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            if new_password != confirm_password:

                flash(
                    "The new passwords do not match.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            if current_user.check_password(
                new_password
            ):

                flash(
                    "Your new password must be different "
                    "from your current password.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            current_user.set_password(
                new_password
            )

            db.session.commit()

            flash(
                "Your password has been changed successfully.",
                "success",
            )

            return redirect(
                url_for("auth.profile")
            )

        # ====================================================
        # APPEARANCE
        # ====================================================

        if action == "update_appearance":

            theme = request.form.get(
                "theme",
                "system",
            ).strip().lower()

            allowed_themes = {
                "light",
                "dark",
                "system",
            }

            if theme not in allowed_themes:

                flash(
                    "Invalid theme selected.",
                    "danger",
                )

                return redirect(
                    url_for("auth.profile")
                )

            current_user.theme = theme

            db.session.commit()

            flash(
                "Appearance settings have been updated.",
                "success",
            )

            return redirect(
                url_for("auth.profile")
            )

        # ====================================================
        # NOTIFICATION PREFERENCES
        # ====================================================

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
                "success",
            )

            return redirect(
                url_for("auth.profile")
            )

        # ====================================================
        # SOUND PREFERENCES
        # ====================================================

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
                "success",
            )

            return redirect(
                url_for("auth.profile")
            )

        # ====================================================
        # INVALID ACTION
        # ====================================================

        flash(
            "Invalid profile action.",
            "danger",
        )

        return redirect(
            url_for("auth.profile")
        )

    # ========================================================
    # GET
    # ========================================================

    company = None

    if current_user.company_id:

        company = db.session.get(
            Company,
            current_user.company_id,
        )

    return render_template(
        "auth/profile.html",
        user=current_user,
        company=company,
    )


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out successfully.",
        "success",
    )

    return redirect(
        url_for("auth.welcome")
    )


# ============================================================
# TERMS & CONDITIONS
# ============================================================

@auth_bp.route("/terms")
def terms():

    return render_template(
        "legal/terms.html"
    )


# ============================================================
# PRIVACY POLICY
# ============================================================

@auth_bp.route("/privacy")
def privacy():

    return render_template(
        "legal/privacy.html"
    )


# ============================================================
# WELCOME GUIDE
# ============================================================

@auth_bp.route("/welcome-guide")
def welcome_guide():

    return render_template(
        "auth/welcome_guide.html"
    )

