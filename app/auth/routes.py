# app/auth/routes.py

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import secrets
from html import escape

import resend

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    session,
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

from werkzeug.security import generate_password_hash

from app.extensions import db

from app.models import (
    User,
    Company,
    Subscription,
    Role,
    UserRole,
    EmailVerificationCode,
    PendingCompanyRegistration,
)

from app.auth.forms import (
    LoginForm,
    RegistrationForm,
)

from app.rbac import (
    initialize_company_rbac,
    ensure_company_admin_role,
    is_company_administrator,
)


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
RESET_TOKEN_MAX_AGE = 7200


# ============================================================
# EMAIL VERIFICATION SETTINGS
# ============================================================

EMAIL_VERIFICATION_CODE_LENGTH = 6

EMAIL_VERIFICATION_EXPIRY_MINUTES = 10

EMAIL_VERIFICATION_MAX_ATTEMPTS = 5

EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60

EMAIL_VERIFICATION_TOKEN_SALT = (
    "bizflow-email-verification-v1"
)

EMAIL_VERIFICATION_TOKEN_MAX_AGE = 3600


# ============================================================
# PENDING REGISTRATION SETTINGS
# ============================================================

PENDING_REGISTRATION_TOKEN_SALT = (
    "biztrace-pending-registration-v1"
)

PENDING_REGISTRATION_TOKEN_MAX_AGE = 3600


# ============================================================
# COMPANY ADMIN ROLE
# ============================================================

COMPANY_ADMIN_ROLE_NAME = "Company Administrator"


# ============================================================
# GENERAL TIME HELPERS
# ============================================================

def utc_now():
    """
    Return current UTC datetime.
    """

    return datetime.now(timezone.utc)


def ensure_utc(value):
    """
    Ensure a datetime is timezone-aware UTC.

    SQLite may return naive datetime objects.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


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
            "fingerprint": get_password_fingerprint(
                user
            ),
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

    user_id = data.get(
        "user_id"
    )

    fingerprint = data.get(
        "fingerprint"
    )

    if not user_id or not fingerprint:

        return None

    user = db.session.get(
        User,
        user_id,
    )

    if not user:

        return None

    current_fingerprint = (
        get_password_fingerprint(
            user
        )
    )

    if not hmac.compare_digest(
        fingerprint,
        current_fingerprint,
    ):

        return None

    return user


# ============================================================
# EXISTING USER EMAIL VERIFICATION
# ============================================================

def get_email_verification_fingerprint(
    user,
):

    return hmac.new(
        current_app.config["SECRET_KEY"].encode(),
        f"{user.id}:{user.email}".encode(),
        sha256,
    ).hexdigest()


def hash_email_verification_code(
    user,
    code,
):

    fingerprint = (
        get_email_verification_fingerprint(
            user
        )
    )

    return hmac.new(
        fingerprint.encode(),
        code.encode(),
        sha256,
    ).hexdigest()


def generate_email_verification_code():

    minimum = 10 ** (
        EMAIL_VERIFICATION_CODE_LENGTH - 1
    )

    maximum = 10 ** (
        EMAIL_VERIFICATION_CODE_LENGTH
    )

    return str(
        secrets.randbelow(
            maximum - minimum
        ) + minimum
    )


def invalidate_existing_verification_codes(
    user,
):

    EmailVerificationCode.query.filter(
        EmailVerificationCode.user_id == user.id,
        EmailVerificationCode.used.is_(False),
    ).update(
        {
            EmailVerificationCode.used: True,
        },
        synchronize_session=False,
    )


def get_latest_verification_code(
    user,
):

    return (
        EmailVerificationCode.query
        .filter_by(
            user_id=user.id,
        )
        .order_by(
            EmailVerificationCode.created_at.desc()
        )
        .first()
    )


def can_resend_verification_code(
    user,
):

    latest = get_latest_verification_code(
        user
    )

    if not latest:

        return True, 0

    created_at = ensure_utc(
        latest.created_at
    )

    if not created_at:

        return True, 0

    elapsed = (
        utc_now() - created_at
    ).total_seconds()

    if elapsed >= (
        EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS
    ):

        return True, 0

    remaining = int(
        EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS
        - elapsed
    )

    if remaining < 1:

        remaining = 1

    return False, remaining


def create_email_verification_code(
    user,
):

    invalidate_existing_verification_codes(
        user
    )

    code = (
        generate_email_verification_code()
    )

    code_hash = (
        hash_email_verification_code(
            user,
            code,
        )
    )

    verification = EmailVerificationCode(
        user_id=user.id,
        code_hash=code_hash,
        expires_at=(
            utc_now()
            + timedelta(
                minutes=EMAIL_VERIFICATION_EXPIRY_MINUTES
            )
        ),
        attempts=0,
        used=False,
        created_at=utc_now(),
    )

    db.session.add(
        verification
    )

    db.session.flush()

    return code, verification


# ============================================================
# PENDING REGISTRATION OTP HELPERS
# ============================================================

def get_pending_verification_fingerprint(
    pending,
):

    return hmac.new(
        current_app.config["SECRET_KEY"].encode(),
        f"pending:{pending.id}:{pending.email}".encode(),
        sha256,
    ).hexdigest()


def hash_pending_verification_code(
    pending,
    code,
):

    fingerprint = (
        get_pending_verification_fingerprint(
            pending
        )
    )

    return hmac.new(
        fingerprint.encode(),
        code.encode(),
        sha256,
    ).hexdigest()


def create_pending_verification_code(pending):
    """
    Generate a new OTP for a pending company registration.
    Uses the existing PendingCompanyRegistration model fields.
    """

    code = generate_email_verification_code()

    now = utc_now()

    pending.code_hash = hash_pending_verification_code(
        pending,
        code
    )

    pending.attempts = 0

    pending.code_created_at = now

    pending.expires_at = (
        now
        + timedelta(
            minutes=EMAIL_VERIFICATION_EXPIRY_MINUTES
        )
    )

    db.session.flush()

    return code



def can_resend_pending_verification(pending):
    """
    Check whether the pending registration can receive
    another verification code.
    """

    created_at = ensure_utc(
        pending.code_created_at
    )

    if not created_at:
        return True, 0

    elapsed = (
        utc_now() - created_at
    ).total_seconds()

    if elapsed >= EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS:
        return True, 0

    remaining = int(
        EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS
        - elapsed
    )

    if remaining < 1:
        remaining = 1

    return False, remaining

# ============================================================
# PENDING REGISTRATION ATTEMPT STORAGE
# ============================================================
#
# Because the existing PendingCompanyRegistration model does
# not have verification_attempts, attempts are temporarily
# stored in the Flask session.
#
# The pending database record still contains the secure
# hashed OTP and expiration time.
#
# ============================================================

def get_pending_attempts(
    pending,
):

    key = (
        f"pending_attempts_{pending.id}"
    )

    value = session.get(
        key,
        0,
    )

    try:

        return int(value)

    except (
        TypeError,
        ValueError,
    ):

        return 0


def set_pending_attempts(
    pending,
    attempts,
):

    key = (
        f"pending_attempts_{pending.id}"
    )

    session[key] = int(
        attempts
    )

    session.modified = True


def clear_pending_attempts(
    pending,
):

    key = (
        f"pending_attempts_{pending.id}"
    )

    session.pop(
        key,
        None,
    )

    session.modified = True


# ============================================================
# EMAIL VERIFICATION TOKEN
# ============================================================

def get_email_verification_serializer():

    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )


def generate_email_verification_token(
    user,
):

    serializer = (
        get_email_verification_serializer()
    )

    return serializer.dumps(
        {
            "type": "user",
            "user_id": user.id,
        },
        salt=EMAIL_VERIFICATION_TOKEN_SALT,
    )


def generate_pending_registration_token(
    pending,
):

    serializer = (
        get_email_verification_serializer()
    )

    return serializer.dumps(
        {
            "type": "pending_registration",
            "pending_id": pending.id,
        },
        salt=EMAIL_VERIFICATION_TOKEN_SALT,
    )


def verify_email_verification_token(
    token,
):

    serializer = (
        get_email_verification_serializer()
    )

    try:

        data = serializer.loads(
            token,
            salt=EMAIL_VERIFICATION_TOKEN_SALT,
            max_age=EMAIL_VERIFICATION_TOKEN_MAX_AGE,
        )

    except SignatureExpired:

        return None

    except BadSignature:

        return None

    if not isinstance(data, dict):

        return None

    token_type = data.get(
        "type"
    )

    # ========================================================
    # PENDING REGISTRATION
    # ========================================================

    if token_type == "pending_registration":

        pending_id = data.get(
            "pending_id"
        )

        if not pending_id:

            return None

        pending = db.session.get(
            PendingCompanyRegistration,
            pending_id,
        )

        if not pending:

            return None

        return {
            "type": "pending_registration",
            "record": pending,
        }

    # ========================================================
    # USER
    # ========================================================

    user_id = data.get(
        "user_id"
    )

    if not user_id:

        return None

    user = db.session.get(
        User,
        user_id,
    )

    if not user:

        return None

    return {
        "type": "user",
        "record": user,
    }


# ============================================================
# SEND USER VERIFICATION EMAIL
# ============================================================

def send_email_verification_email(
    user,
    code,
):

    resend_api_key = current_app.config.get(
        "RESEND_API_KEY"
    )

    sender_email = current_app.config.get(
        "RESEND_FROM_EMAIL"
    )

    recipient_email = (
        user.email or ""
    ).strip().lower()

    if not resend_api_key:

        current_app.logger.error(
            "EMAIL VERIFICATION ERROR: "
            "RESEND_API_KEY is not configured."
        )

        return False

    if not sender_email:

        current_app.logger.error(
            "EMAIL VERIFICATION ERROR: "
            "RESEND_FROM_EMAIL is not configured."
        )

        return False

    if not recipient_email:

        return False

    resend.api_key = resend_api_key

    username = escape(
        user.username or "User"
    )

    safe_code = escape(
        code
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
content="width=device-width, initial-scale=1.0">
<title>Verify your BizTrace IMS email</title>
</head>

<body style="
margin:0;
padding:0;
background:#f5f7fb;
font-family:-apple-system,BlinkMacSystemFont,
'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
">

<div style="
max-width:600px;
margin:40px auto;
padding:20px;
">

<div style="
background:#ffffff;
border-radius:18px;
padding:40px 30px;
box-shadow:0 4px 20px rgba(0,0,0,0.06);
">

<div style="
text-align:center;
margin-bottom:30px;
">

<h1 style="
margin:0;
color:#0a84ff;
font-size:28px;
font-weight:700;
">
BizTrace IMS
</h1>

<p style="
margin:8px 0 0;
color:#6b7280;
font-size:14px;
">
Business Management System
</p>

</div>

<h2 style="
margin:0 0 16px;
color:#111827;
font-size:22px;
">
Verify your email address
</h2>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
">
Hello {username},
</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
">
Please use the verification code below to
confirm your BizTrace IMS email address.
</p>

<div style="
text-align:center;
margin:32px 0;
">

<div style="
display:inline-block;
padding:18px 30px;
background:#f0f7ff;
border:1px solid #dbeafe;
border-radius:14px;
color:#0a84ff;
font-size:34px;
font-weight:700;
letter-spacing:8px;
">
{safe_code}
</div>

</div>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
text-align:center;
">

This code expires in
<strong>{EMAIL_VERIFICATION_EXPIRY_MINUTES} minutes</strong>.

</p>

<div style="
margin-top:30px;
padding:16px;
background:#f8fafc;
border-radius:10px;
">

<p style="
margin:0;
color:#4b5563;
font-size:13px;
line-height:1.6;
">

<strong>Security notice:</strong>
Never share this verification code with anyone.

</p>

</div>

<div style="
margin-top:35px;
padding-top:20px;
border-top:1px solid #e5e7eb;
text-align:center;
">

<p style="
margin:0;
color:#9ca3af;
font-size:12px;
">

Regards,<br>
<strong>BizTrace IMS</strong>

</p>

</div>

</div>
</div>

</body>
</html>
"""

    try:

        response = resend.Emails.send(
            {
                "from": sender_email,
                "to": [recipient_email],
                "subject": (
                    "Your BizTrace IMS verification code"
                ),
                "html": html_content,
            }
        )

        current_app.logger.info(
            "EMAIL VERIFICATION: "
            "Resend accepted email. "
            "Recipient=%s Response=%s",
            recipient_email,
            response,
        )

        return True

    except Exception:

        current_app.logger.exception(
            "EMAIL VERIFICATION EMAIL ERROR"
        )

        return False


# ============================================================
# SEND PENDING REGISTRATION VERIFICATION EMAIL
# ============================================================

def send_pending_registration_verification_email(
    pending,
    code,
):

    resend_api_key = current_app.config.get(
        "RESEND_API_KEY"
    )

    sender_email = current_app.config.get(
        "RESEND_FROM_EMAIL"
    )

    recipient_email = (
        pending.email or ""
    ).strip().lower()

    if not resend_api_key:

        current_app.logger.error(
            "PENDING REGISTRATION EMAIL ERROR: "
            "RESEND_API_KEY is not configured."
        )

        return False

    if not sender_email:

        current_app.logger.error(
            "PENDING REGISTRATION EMAIL ERROR: "
            "RESEND_FROM_EMAIL is not configured."
        )

        return False

    if not recipient_email:

        return False

    resend.api_key = resend_api_key

    username = escape(
        pending.username or "User"
    )

    safe_code = escape(
        code
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>Verify your BizTrace IMS registration</title>

</head>

<body style="
margin:0;
padding:0;
background:#f5f7fb;
font-family:-apple-system,BlinkMacSystemFont,
'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
">

<div style="
max-width:600px;
margin:40px auto;
padding:20px;
">

<div style="
background:#ffffff;
border-radius:18px;
padding:40px 30px;
box-shadow:0 4px 20px rgba(0,0,0,0.06);
">

<div style="
text-align:center;
margin-bottom:30px;
">

<h1 style="
margin:0;
color:#0a84ff;
font-size:28px;
font-weight:700;
">
BizTrace IMS
</h1>

<p style="
margin:8px 0 0;
color:#6b7280;
font-size:14px;
">
Business Management System
</p>

</div>

<h2 style="
margin:0 0 16px;
color:#111827;
font-size:22px;
">
Verify your email address
</h2>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
">
Hello {username},
</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
">

Thank you for registering your company with
BizTrace IMS. Use the verification code below
to confirm your email address and complete
your registration.

</p>

<div style="
text-align:center;
margin:32px 0;
">

<div style="
display:inline-block;
padding:18px 30px;
background:#f0f7ff;
border:1px solid #dbeafe;
border-radius:14px;
color:#0a84ff;
font-size:34px;
font-weight:700;
letter-spacing:8px;
">

{safe_code}

</div>

</div>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
text-align:center;
">

This code expires in
<strong>
{EMAIL_VERIFICATION_EXPIRY_MINUTES}
minutes
</strong>.

</p>

<div style="
margin-top:30px;
padding:16px;
background:#f8fafc;
border-radius:10px;
">

<p style="
margin:0;
color:#4b5563;
font-size:13px;
line-height:1.6;
">

<strong>Security notice:</strong>
Never share this verification code with anyone.

</p>

</div>

<div style="
margin-top:35px;
padding-top:20px;
border-top:1px solid #e5e7eb;
text-align:center;
">

<p style="
margin:0;
color:#9ca3af;
font-size:12px;
">

Regards,<br>
<strong>BizTrace IMS</strong>

</p>

</div>

</div>
</div>

</body>
</html>
"""

    try:

        response = resend.Emails.send(
            {
                "from": sender_email,
                "to": [recipient_email],
                "subject": (
                    "Verify your BizTrace IMS registration"
                ),
                "html": html_content,
            }
        )

        current_app.logger.info(
            "PENDING REGISTRATION EMAIL: "
            "Resend accepted email. "
            "Recipient=%s Response=%s",
            recipient_email,
            response,
        )

        return True

    except Exception:

        current_app.logger.exception(
            "PENDING REGISTRATION EMAIL ERROR"
        )

        return False


# ============================================================
# SEND WELCOME EMAIL
# ============================================================

def send_welcome_email(
    user,
    company,
):

    resend_api_key = current_app.config.get(
        "RESEND_API_KEY"
    )

    sender_email = current_app.config.get(
        "RESEND_FROM_EMAIL"
    )

    recipient_email = (
        user.email or ""
    ).strip().lower()

    if not resend_api_key:

        current_app.logger.error(
            "WELCOME EMAIL ERROR: "
            "RESEND_API_KEY is not configured."
        )

        return False

    if not sender_email:

        current_app.logger.error(
            "WELCOME EMAIL ERROR: "
            "RESEND_FROM_EMAIL is not configured."
        )

        return False

    if not recipient_email:

        return False

    resend.api_key = resend_api_key

    welcome_guide_url = url_for(
        "auth.welcome_guide",
        _external=True,
    )

    safe_company_name = escape(
        company.name or "Your Company"
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>Welcome to BizTrace IMS</title>

</head>

<body style="
margin:0;
padding:0;
background:#f5f7fb;
font-family:-apple-system,BlinkMacSystemFont,
'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
">

<div style="
max-width:680px;
margin:30px auto;
padding:20px;
">

<div style="
background:#ffffff;
border-radius:20px;
padding:40px 32px;
box-shadow:0 4px 25px rgba(0,0,0,0.06);
">

<div style="
text-align:center;
margin-bottom:30px;
">

<h1 style="
margin:0;
color:#0a84ff;
font-size:30px;
font-weight:750;
">

🎉 WELCOME TO BIZTRACE IMS

</h1>

<p style="
margin:10px 0 0;
color:#6b7280;
font-size:14px;
">

Business Management. Simplified.

</p>

</div>

<h2 style="
color:#111827;
font-size:21px;
margin-bottom:18px;
">

Dear Company Admin,

</h2>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

Welcome to BizTrace IMS, your complete business
management system for managing sales, purchases,
inventory, expenses, customers, suppliers, payments, Cash deposits, 
payables, receivables, and reports in one place.

</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

After registration, please complete your company
settings, add your products and opening stock,
configure staff accounts and permissions, and enable
browser notifications from the Notifications section
so you can receive system alerts.

</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

For the best experience, use a PC, Desktop or Tablet
for major configuration and printing, or when it comes to printing sales invoice use mobile or Merchant terminal(POS). 
On mobile, use Landscape mode, especially for detailed pages and
settings.

</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

When clicking buttons, click once and allow the page
to load before clicking again. For reports and invoices,
use Light Mode before printing and always check the
print preview.

</p>

<div style="
margin:25px 0;
padding:18px;
background:#eff6ff;
border:1px solid #dbeafe;
border-radius:12px;
">

<p style="
margin:0;
color:#1e40af;
font-size:14px;
line-height:1.7;
">

Your new company receives a
<strong>7-days trial</strong>,
after which you need an active subscription.

</p>

</div>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

📖 For how to use BizTrace IMS, 
please review the Welcome Guide.

</p>

<div style="
text-align:center;
margin:30px 0;
">

<a
href="{welcome_guide_url}"
style="
display:inline-block;
padding:14px 24px;
background:#0a84ff;
color:#ffffff;
text-decoration:none;
border-radius:10px;
font-size:15px;
font-weight:600;
"
>

Open Welcome Guide

</a>

</div>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

If anything is unclear or you experience any problem,
please call us, chat with us on WhatsApp, or send us an
email, or visit the Support page.

</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.8;
">

When contacting us, include your company name,
registered email and a description or screenshot of
the issue where possible.

</p>

<div style="
margin-top:25px;
padding:20px;
background:#f8fafc;
border-radius:12px;
">

<p style="
margin:5px 0;
color:#374151;
font-size:14px;
">

📧 <strong>support@biztraceims.com</strong>
</p>

<p style="
margin:5px 0;
color:#374151;
font-size:14px;
">

📞 <strong>08154675347</strong>

</p>

<p style="
margin:5px 0;
color:#374151;
font-size:14px;
">

💬 WhatsApp:
<strong>08154675347</strong>

</p>

</div>

<div style="
margin-top:35px;
padding-top:20px;
border-top:1px solid #e5e7eb;
text-align:center;
">

<p style="
margin:0;
color:#6b7280;
font-size:14px;
">

<strong>
BizTrace IMS — Business Management. Simplified.
</strong>

</p>

</div>

</div>
</div>

</body>
</html>
"""

    try:

        response = resend.Emails.send(
            {
                "from": sender_email,
                "to": [recipient_email],
                "subject": (
                    "🎉 Welcome to BizTrace IMS"
                ),
                "html": html_content,
            }
        )

        current_app.logger.info(
            "WELCOME EMAIL: "
            "Resend accepted email. "
            "User ID=%s Recipient=%s Response=%s",
            user.id,
            recipient_email,
            response,
        )

        return True

    except Exception:

        current_app.logger.exception(
            "WELCOME EMAIL ERROR"
        )

        return False


# ============================================================
# SEND PASSWORD RESET EMAIL
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

    recipient_email = (
        user.email or ""
    ).strip().lower()

    if not resend_api_key:

        return False

    if not sender_email:

        return False

    if not recipient_email:

        return False

    resend.api_key = resend_api_key

    username = escape(
        user.username or "User"
    )

    safe_reset_url = escape(
        reset_url,
        quote=True,
    )

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

<body style="
margin:0;
padding:0;
background:#f5f7fb;
font-family:-apple-system,BlinkMacSystemFont,
'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
">

<div style="
max-width:600px;
margin:40px auto;
padding:20px;
">

<div style="
background:#ffffff;
border-radius:16px;
padding:40px 30px;
box-shadow:0 4px 20px rgba(0,0,0,0.06);
">

<div style="
text-align:center;
margin-bottom:30px;
">

<h1 style="
margin:0;
color:#0a84ff;
font-size:28px;
font-weight:700;
">

BizTrace IMS

</h1>

</div>

<h2 style="
color:#111827;
">

Reset your password

</h2>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
">

Hello {username},

</p>

<p style="
color:#374151;
font-size:15px;
line-height:1.7;
">

We received a request to reset the password
for your BizTrace IMS account.

</p>

<div style="
text-align:center;
margin:30px 0;
">

<a
href="{safe_reset_url}"
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

<p style="
word-break:break-all;
background:#f3f4f6;
padding:12px;
border-radius:8px;
color:#374151;
font-size:12px;
">

{safe_reset_url}

</p>

<p style="
color:#6b7280;
font-size:13px;
line-height:1.6;
">

This password reset link expires in 2 hours.
If you did not request a password reset,
you can safely ignore this email.

</p>

</div>
</div>

</body>
</html>
"""

    try:

        response = resend.Emails.send(
            {
                "from": sender_email,
                "to": [recipient_email],
                "subject": (
                    "Reset your BizTrace IMS password"
                ),
                "html": html_content,
            }
        )

        return True

    except Exception:

        current_app.logger.exception(
            "PASSWORD RESET EMAIL ERROR"
        )

        return False


# ============================================================
# ENSURE COMPANY ADMIN RBAC
# ============================================================

def ensure_company_admin_rbac(
    user,
    company,
):

    try:

        if user is None:

            return False

        if company is None:

            return False

        if user.company_id != company.id:

            return False

        if not is_company_administrator(
            user
        ):

            return True

        user.role = (
            COMPANY_ADMIN_ROLE_NAME
        )

        initialize_company_rbac(
            company=company,
            administrator=user,
            assigned_by=None,
        )

        db.session.flush()

        company_admin_role = (
            Role.query.filter_by(
                company_id=company.id,
                name=COMPANY_ADMIN_ROLE_NAME,
            ).first()
        )

        if company_admin_role is None:

            return False

        user_role = UserRole.query.filter_by(
            user_id=user.id,
            role_id=company_admin_role.id,
        ).first()

        if user_role is None:

            return False

        return True

    except Exception:

        current_app.logger.exception(
            "RBAC ERROR"
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

# ============================================================
# LOGIN
# ============================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
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
            form.email.data or ""
        ).lower().strip()

        password = (
            form.password.data or ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        # ====================================================
        # INVALID LOGIN
        # ====================================================

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

        # ====================================================
        # USER DEACTIVATED
        # ====================================================

        if not user.is_active:

            flash(
                "Your account has been deactivated. "
                "Please contact your administrator.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ====================================================
        # SYSTEM ADMINISTRATOR
        # ====================================================

        if user.is_system_admin:

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
                    "system_admin.dashboard"
                )
            )

        # ====================================================
        # EMAIL VERIFICATION
        # ====================================================

        if not user.email_verified:

            verification_token = (
                generate_email_verification_token(
                    user
                )
            )

            next_page = request.args.get(
                "next"
            )

            if next_page:

                session[
                    "email_verification_next"
                ] = next_page

            return redirect(
                url_for(
                    "auth.verify_email",
                    token=verification_token,
                )
            )

        # ====================================================
        # COMPANY ID CHECK
        # ====================================================

        if user.company_id is None:

            flash(
                "Your account is not associated "
                "with a company.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ====================================================
        # LOAD COMPANY
        # ====================================================

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

        # ====================================================
        # COMPANY DEACTIVATED
        # ====================================================

        if not company.is_active:

            # ------------------------------------------------
            # CREATE SECURE PAYMENT SESSION
            # ------------------------------------------------
            #
            # The user has successfully supplied the correct
            # email/password, but we deliberately DO NOT
            # login the user.
            #
            # This allows the deactivated-company Paystack
            # payment buttons to work without trusting a
            # company_id supplied by the browser.
            # ------------------------------------------------

            session[
                "subscription_payment_user_id"
            ] = user.id

            session[
                "subscription_payment_company_id"
            ] = company.id

            session[
                "subscription_payment_email"
            ] = user.email

            session[
                "subscription_payment_created_at"
            ] = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            flash(
                "COMPANY_DEACTIVATED",
                "company_deactivated",
            )

            return render_template(
                "auth/login.html",
                form=form,
                company_deactivated=True,
                company=company,
            )

        # ====================================================
        # COMPANY ADMIN RBAC
        # ====================================================

        if is_company_administrator(user):

            if not ensure_company_admin_rbac(
                user=user,
                company=company,
            ):

                db.session.rollback()

                flash(
                    "Your account permissions could not "
                    "be initialized. Please contact support.",
                    "danger",
                )

                return redirect(
                    url_for("auth.login")
                )

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                current_app.logger.exception(
                    "LOGIN ERROR: RBAC repair failed."
                )

                flash(
                    "Your account permissions could not "
                    "be saved. Please contact support.",
                    "danger",
                )

                return redirect(
                    url_for("auth.login")
                )

        # ====================================================
        # LOGIN USER
        # ====================================================

        login_user(
            user,
            remember=form.remember.data,
        )

        # ----------------------------------------------------
        # CLEAR PAYMENT SESSION
        # ----------------------------------------------------

        session.pop(
            "subscription_payment_user_id",
            None,
        )

        session.pop(
            "subscription_payment_company_id",
            None,
        )

        session.pop(
            "subscription_payment_email",
            None,
        )

        session.pop(
            "subscription_payment_created_at",
            None,
        )

        # ====================================================
        # NEXT PAGE
        # ====================================================

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
        form=form,
        company_deactivated=False,
        company=None,
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

        company_name = (
            form.company_name.data or ""
        ).strip()

        company_email = (
            form.company_email.data or ""
        ).lower().strip()

        company_phone = (
            form.company_phone.data.strip()
            if form.company_phone.data
            else None
        )

        company_address = (
            form.company_address.data.strip()
            if form.company_address.data
            else None
        )

        username = (
            form.username.data or ""
        ).strip()

        email = (
            form.email.data or ""
        ).lower().strip()

        # ----------------------------------------------------
        # EXISTING USER
        # ----------------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "An account with this email address "
                "already exists. Please sign in instead.",
                "danger",
            )

            return redirect(
                url_for("auth.login")
            )

        # ----------------------------------------------------
        # EXISTING PENDING REGISTRATION
        # ----------------------------------------------------

        existing_pending = (
            PendingCompanyRegistration.query
            .filter_by(
                email=email
            )
            .first()
        )

        if existing_pending:

            verification_token = (
                generate_pending_registration_token(
                    existing_pending
                )
            )

            flash(
                "A registration is already waiting for "
                "email verification. Please check your "
                "email for the verification code.",
                "warning",
            )

            return redirect(
                url_for(
                    "auth.verify_email",
                    token=verification_token,
                )
            )

        # ----------------------------------------------------
        # CREATE PENDING REGISTRATION ONLY
        # ----------------------------------------------------

        try:

            password_hash = (
                generate_password_hash(
                    form.password.data
                )
            )

            pending = PendingCompanyRegistration(
                company_name=company_name,
                company_email=company_email,
                company_phone=company_phone,
                company_address=company_address,
                username=username,
                email=email,
                password_hash=password_hash,
                code_hash="",
                attempts=0,
                expires_at=(
                        utc_now()
                        + timedelta(
                    minutes=EMAIL_VERIFICATION_EXPIRY_MINUTES
                )
                ),
                code_created_at=utc_now(),
            )

            db.session.add(
                pending
            )

            db.session.flush()

            verification_code = (
                create_pending_verification_code(
                    pending
                )
            )

            # Reset browser/session attempts.
            set_pending_attempts(
                pending,
                0,
            )

            db.session.commit()

            current_app.logger.info(
                "REGISTRATION: Pending registration created. "
                "Pending ID=%s Email=%s",
                pending.id,
                pending.email,
            )

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "REGISTRATION: Failed to create pending "
                "registration."
            )

            flash(
                "We could not start your registration. "
                "Please try again.",
                "danger",
            )

            return redirect(
                url_for("auth.register")
            )

        # ----------------------------------------------------
        # SEND OTP
        # ----------------------------------------------------

        email_sent = (
            send_pending_registration_verification_email(
                pending,
                verification_code,
            )
        )

        verification_token = (
            generate_pending_registration_token(
                pending
            )
        )

        if email_sent:

            flash(
                "Your registration has been started. "
                "We sent a verification code to your email.",
                "success",
            )

        else:

            flash(
                "Your registration has been saved, but "
                "we could not send the verification email. "
                "Use the resend option.",
                "warning",
            )

        return redirect(
            url_for(
                "auth.verify_email",
                token=verification_token,
            )
        )

    return render_template(
        "auth/register.html",
        form=form,
    )


# ============================================================
# VERIFY EMAIL
# ============================================================

@auth_bp.route(
    "/verify-email/<token>",
    methods=["GET", "POST"],
)
def verify_email(token):

    verification_session = (
        verify_email_verification_token(
            token
        )
    )

    if not verification_session:

        flash(
            "This email verification link is invalid "
            "or has expired.",
            "danger",
        )

        return redirect(
            url_for("auth.login")
        )

    token_type = verification_session[
        "type"
    ]

    record = verification_session[
        "record"
    ]

    # ========================================================
    # PENDING REGISTRATION
    # ========================================================

    if token_type == "pending_registration":

        pending = record

        if request.method == "POST":

            code = (
                request.form.get(
                    "code",
                    "",
                )
                .strip()
            )

            if (
                not code.isdigit()
                or len(code)
                != EMAIL_VERIFICATION_CODE_LENGTH
            ):

                flash(
                    "Please enter the 6-digit verification code.",
                    "danger",
                )

                return render_template(
                    "auth/verify_email.html",
                    user=None,
                    pending=pending,
                    token=token,
                    email=pending.email,
                    cooldown=0,
                )

            # ------------------------------------------------
            # EXPIRATION
            # ------------------------------------------------

            expires_at = ensure_utc(
                pending.expires_at
            )

            if (
                not expires_at
                or utc_now() > expires_at
            ):

                flash(
                    "This verification code has expired. "
                    "Please request a new code.",
                    "warning",
                )

                return render_template(
                    "auth/verify_email.html",
                    user=None,
                    pending=pending,
                    token=token,
                    email=pending.email,
                    cooldown=0,
                )

            # ------------------------------------------------
            # ATTEMPTS
            # ------------------------------------------------

            attempts = get_pending_attempts(
                pending
            )

            if attempts >= (
                EMAIL_VERIFICATION_MAX_ATTEMPTS
            ):

                flash(
                    "Too many incorrect attempts. "
                    "Please request a new verification code.",
                    "danger",
                )

                return render_template(
                    "auth/verify_email.html",
                    user=None,
                    pending=pending,
                    token=token,
                    email=pending.email,
                    cooldown=0,
                )

            # ------------------------------------------------
            # VERIFY HASH
            # ------------------------------------------------

            submitted_hash = (
                hash_pending_verification_code(
                    pending,
                    code,
                )
            )

            if not hmac.compare_digest(
                submitted_hash,
                pending.code_hash or "",
            ):

                attempts += 1

                set_pending_attempts(
                    pending,
                    attempts,
                )

                if attempts >= (
                    EMAIL_VERIFICATION_MAX_ATTEMPTS
                ):

                    flash(
                        "Too many incorrect attempts. "
                        "Please request a new verification code.",
                        "danger",
                    )

                else:

                    remaining = (
                        EMAIL_VERIFICATION_MAX_ATTEMPTS
                        - attempts
                    )

                    flash(
                        f"Incorrect verification code. "
                        f"{remaining} attempt(s) remaining.",
                        "danger",
                    )

                return render_template(
                    "auth/verify_email.html",
                    user=None,
                    pending=pending,
                    token=token,
                    email=pending.email,
                    cooldown=0,
                )

            # =================================================
            # OTP SUCCESS
            # =================================================

            try:

                # ---------------------------------------------
                # CREATE COMPANY
                # ---------------------------------------------

                company = Company(
                    name=pending.company_name,
                    email=pending.company_email,
                    phone=pending.company_phone,
                    address=pending.company_address,
                    is_active=True,
                )

                db.session.add(
                    company
                )

                db.session.flush()

                # ---------------------------------------------
                # CREATE ADMIN USER
                # ---------------------------------------------

                user = User(
                    company_id=company.id,
                    username=pending.username,
                    email=pending.email,
                    password_hash=pending.password_hash,
                    role=COMPANY_ADMIN_ROLE_NAME,
                    is_active=True,
                    email_verified=True,
                    email_verified_at=utc_now(),
                )

                db.session.add(
                    user
                )

                db.session.flush()

                # ---------------------------------------------
                # INITIALIZE RBAC
                # ---------------------------------------------

                rbac_ready = (
                    ensure_company_admin_rbac(
                        user=user,
                        company=company,
                    )
                )

                if not rbac_ready:

                    raise RuntimeError(
                        "Failed to initialize "
                        "Company Administrator RBAC."
                    )

                # ---------------------------------------------
                # VERIFY ADMIN ROLE
                # ---------------------------------------------

                company_admin_role = (
                    Role.query.filter_by(
                        company_id=company.id,
                        name=COMPANY_ADMIN_ROLE_NAME,
                    ).first()
                )

                if company_admin_role is None:

                    raise RuntimeError(
                        "Company Administrator role "
                        "was not created."
                    )

                user_role = UserRole.query.filter_by(
                    user_id=user.id,
                    role_id=company_admin_role.id,
                ).first()

                if user_role is None:

                    raise RuntimeError(
                        "Company Administrator UserRole "
                        "was not created."
                    )

                # ---------------------------------------------
                # CREATE 7-DAY FREE TRIAL
                # ---------------------------------------------

                trial_started_at = utc_now()

                trial_expires_at = (
                        trial_started_at
                        + timedelta(days=7)
                )

                trial_subscription = Subscription(
                    company_id=company.id,
                    plan="trial",
                    amount=0,
                    currency="NGN",
                    status="trial",
                    payment_status="not_required",

                    transaction_reference=None,
                    order_id=None,

                    paystack_reference=None,
                    paystack_transaction_id=None,
                    paystack_access_code=None,

                    payment_method=None,
                    gateway_response=None,

                    start_date=trial_started_at,
                    end_date=trial_expires_at,

                    trial_started_at=trial_started_at,
                    trial_expires_at=trial_expires_at,

                    paid_at=None,
                    verified_at=None,

                    activation_source="trial",

                    manually_activated=False,
                    manually_activated_by=None,
                    manually_activated_at=None,

                    maintenance_fee=0,
                    maintenance_days=0,
                )

                db.session.add(
                    trial_subscription
                )

                # ---------------------------------------------
                # DELETE PENDING REGISTRATION
                # ---------------------------------------------

                db.session.delete(
                    pending
                )

                # ---------------------------------------------
                # COMMIT EVERYTHING
                # ---------------------------------------------

                db.session.commit()

                clear_pending_attempts(
                    pending
                )

                current_app.logger.info(
                    "REGISTRATION COMPLETE: "
                    "Company ID=%s User ID=%s Email=%s",
                    company.id,
                    user.id,
                    user.email,
                )

            except Exception:

                db.session.rollback()

                current_app.logger.exception(
                    "REGISTRATION VERIFICATION ERROR"
                )

                flash(
                    "Your email was verified, but we could "
                    "not complete the company account creation. "
                    "Please try again.",
                    "danger",
                )

                return render_template(
                    "auth/verify_email.html",
                    user=None,
                    pending=pending,
                    token=token,
                    email=pending.email,
                    cooldown=0,
                )

            # ------------------------------------------------
            # WELCOME EMAIL
            # ------------------------------------------------

            welcome_email_sent = (
                send_welcome_email(
                    user,
                    company,
                )
            )

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            login_user(
                user,
                remember=False,
            )

            if welcome_email_sent:

                flash(
                    "Your email has been verified successfully. "
                    "Your BizTrace IMS company account has been "
                    "created. Welcome to BizTrace IMS! Please follow the welcome guide sent to you via email or WhatsApp to get started. "
                    "If you don't understand anything, feel free to reach us via the support page or official channels.",
                    "success",
                )

            else:

                flash(
                    "Your email has been verified and your "
                    "BizTrace IMS company account has been "
                    "created successfully. However, the welcome "
                    "email could not be sent.",
                    "success",
                )

            return redirect(
                url_for(
                    "dashboard.dashboard"
                )
            )

        # ====================================================
        # GET
        # ====================================================

        can_resend, cooldown = (
            can_resend_pending_verification(
                pending
            )
        )

        return render_template(
            "auth/verify_email.html",
            user=None,
            pending=pending,
            token=token,
            email=pending.email,
            cooldown=cooldown,
        )

    # ========================================================
    # EXISTING USER
    # ========================================================

    user = record

    if not user:

        flash(
            "This verification session is invalid.",
            "danger",
        )

        return redirect(
            url_for("auth.login")
        )

    if not user.is_active:

        flash(
            "This account has been deactivated.",
            "danger",
        )

        return redirect(
            url_for("auth.login")
        )

    if user.email_verified:

        if not current_user.is_authenticated:

            login_user(
                user,
                remember=False,
            )

        next_page = session.pop(
            "email_verification_next",
            None,
        )

        flash(
            "Your email address is already verified.",
            "success",
        )

        if next_page:

            return redirect(
                next_page
            )

        if user.is_system_admin:

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

    # ========================================================
    # EXISTING USER POST
    # ========================================================

    if request.method == "POST":

        code = (
            request.form.get(
                "code",
                "",
            )
            .strip()
        )

        if (
            not code.isdigit()
            or len(code)
            != EMAIL_VERIFICATION_CODE_LENGTH
        ):

            flash(
                "Please enter the 6-digit verification code.",
                "danger",
            )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        verification = (
            get_latest_verification_code(
                user
            )
        )

        if not verification:

            flash(
                "No active verification code was found. "
                "Please request a new code.",
                "warning",
            )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        if verification.used:

            flash(
                "This verification code has already been used. "
                "Please request a new code.",
                "warning",
            )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        expires_at = ensure_utc(
            verification.expires_at
        )

        if (
            not expires_at
            or utc_now() > expires_at
        ):

            verification.used = True

            db.session.commit()

            flash(
                "This verification code has expired. "
                "Please request a new code.",
                "warning",
            )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        if (
            verification.attempts
            >= EMAIL_VERIFICATION_MAX_ATTEMPTS
        ):

            verification.used = True

            db.session.commit()

            flash(
                "Too many incorrect attempts. "
                "Please request a new verification code.",
                "danger",
            )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        submitted_hash = (
            hash_email_verification_code(
                user,
                code,
            )
        )

        if not hmac.compare_digest(
            submitted_hash,
            verification.code_hash,
        ):

            verification.attempts += 1

            if (
                verification.attempts
                >= EMAIL_VERIFICATION_MAX_ATTEMPTS
            ):

                verification.used = True

                db.session.commit()

                flash(
                    "Too many incorrect attempts. "
                    "Please request a new verification code.",
                    "danger",
                )

            else:

                db.session.commit()

                remaining = (
                    EMAIL_VERIFICATION_MAX_ATTEMPTS
                    - verification.attempts
                )

                flash(
                    f"Incorrect verification code. "
                    f"{remaining} attempt(s) remaining.",
                    "danger",
                )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        user.email_verified = True

        user.email_verified_at = utc_now()

        verification.used = True

        EmailVerificationCode.query.filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.id != verification.id,
            EmailVerificationCode.used.is_(False),
        ).update(
            {
                EmailVerificationCode.used: True,
            },
            synchronize_session=False,
        )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "EMAIL VERIFICATION SAVE ERROR"
            )

            flash(
                "We could not complete email verification. "
                "Please try again.",
                "danger",
            )

            return render_template(
                "auth/verify_email.html",
                user=user,
                pending=None,
                token=token,
                email=user.email,
                cooldown=0,
            )

        if not current_user.is_authenticated:

            login_user(
                user,
                remember=False,
            )

        next_page = session.pop(
            "email_verification_next",
            None,
        )

        flash(
            "Your email has been verified successfully. "
            "Welcome to BizTrace IMS.",
            "success",
        )

        if user.is_system_admin:

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
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
    # GET EXISTING USER
    # ========================================================

    can_resend, cooldown = (
        can_resend_verification_code(
            user
        )
    )

    return render_template(
        "auth/verify_email.html",
        user=user,
        pending=None,
        token=token,
        email=user.email,
        cooldown=cooldown,
    )


# ============================================================
# RESEND VERIFICATION
# ============================================================

@auth_bp.route(
    "/resend-verification/<token>",
    methods=["POST"],
)
def resend_verification(token):

    verification_session = (
        verify_email_verification_token(
            token
        )
    )

    if not verification_session:

        flash(
            "This verification session is invalid "
            "or has expired.",
            "danger",
        )

        return redirect(
            url_for("auth.login")
        )

    token_type = verification_session[
        "type"
    ]

    record = verification_session[
        "record"
    ]

    # ========================================================
    # PENDING REGISTRATION
    # ========================================================

    if token_type == "pending_registration":

        pending = record

        allowed, remaining = (
            can_resend_pending_verification(
                pending
            )
        )

        if not allowed:

            flash(
                f"Please wait {remaining} seconds before "
                f"requesting another verification code.",
                "warning",
            )

            return redirect(
                url_for(
                    "auth.verify_email",
                    token=token,
                )
            )

        try:

            code = (
                create_pending_verification_code(
                    pending
                )
            )

            set_pending_attempts(
                pending,
                0,
            )

            db.session.commit()

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "PENDING REGISTRATION: "
                "Failed to create verification code."
            )

            flash(
                "We could not generate a new verification "
                "code. Please try again.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.verify_email",
                    token=token,
                )
            )

        email_sent = (
            send_pending_registration_verification_email(
                pending,
                code,
            )
        )

        if email_sent:

            flash(
                "A new verification code has been sent "
                "to your email address.",
                "success",
            )

        else:

            flash(
                "We generated a new verification code, "
                "but could not send the email.",
                "danger",
            )

        return redirect(
            url_for(
                "auth.verify_email",
                token=token,
            )
        )

    # ========================================================
    # EXISTING USER
    # ========================================================

    user = record

    if user.email_verified:

        flash(
            "This email address has already been verified.",
            "success",
        )

        return redirect(
            url_for("auth.login")
        )

    if not user.is_active:

        flash(
            "This account has been deactivated.",
            "danger",
        )

        return redirect(
            url_for("auth.login")
        )

    allowed, remaining = (
        can_resend_verification_code(
            user
        )
    )

    if not allowed:

        flash(
            f"Please wait {remaining} seconds before "
            f"requesting another verification code.",
            "warning",
        )

        return redirect(
            url_for(
                "auth.verify_email",
                token=token,
            )
        )

    try:

        code, verification = (
            create_email_verification_code(
                user
            )
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "EMAIL VERIFICATION: "
            "Failed to create verification code."
        )

        flash(
            "We could not generate a new verification code. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.verify_email",
                token=token,
            )
        )

    email_sent = (
        send_email_verification_email(
            user,
            code,
        )
    )

    if email_sent:

        flash(
            "A new verification code has been sent "
            "to your email address.",
            "success",
        )

    else:

        flash(
            "We generated a new verification code, "
            "but could not send the email.",
            "danger",
        )

    return redirect(
        url_for(
            "auth.verify_email",
            token=token,
        )
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

        user = User.query.filter_by(
            email=email
        ).first()

        if user and user.is_active:

            try:

                token = (
                    generate_password_reset_token(
                        user
                    )
                )

                reset_url = url_for(
                    "auth.reset_password",
                    token=token,
                    _external=True,
                )

                send_password_reset_email(
                    user,
                    reset_url,
                )

            except Exception:

                current_app.logger.exception(
                    "PASSWORD RESET ERROR"
                )

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

        if password != confirm_password:

            flash(
                "The passwords do not match.",
                "danger",
            )

            return render_template(
                "auth/reset_password.html",
                invalid_token=False,
            )

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

            old_email = (
                current_user.email or ""
            ).strip().lower()

            current_user.username = username

            if email != old_email:

                current_user.email = email

                current_user.email_verified = False

                current_user.email_verified_at = None

                invalidate_existing_verification_codes(
                    current_user
                )

                verification_code, verification = (
                    create_email_verification_code(
                        current_user
                    )
                )

                db.session.commit()

                email_sent = (
                    send_email_verification_email(
                        current_user,
                        verification_code,
                    )
                )

                verification_token = (
                    generate_email_verification_token(
                        current_user
                    )
                )

                if email_sent:

                    flash(
                        "Your email address was changed. "
                        "We sent a verification code to "
                        "your new email address.",
                        "success",
                    )

                else:

                    flash(
                        "Your email address was changed, "
                        "but we could not send the verification "
                        "email. Use the resend option.",
                        "warning",
                    )

                return redirect(
                    url_for(
                        "auth.verify_email",
                        token=verification_token,
                    )
                )

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

        flash(
            "Invalid profile action.",
            "danger",
        )

        return redirect(
            url_for("auth.profile")
        )

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
# TERMS
# ============================================================

@auth_bp.route("/terms")
def terms():

    return render_template(
        "legal/terms.html"
    )


# ============================================================
# PRIVACY
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
