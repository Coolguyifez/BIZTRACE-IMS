# ============================================================
# BIZTRACE IMS - PAYSTACK SUBSCRIPTION ROUTES
# ============================================================

import json
import secrets
import hmac
import hashlib
import uuid

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import requests

from flask import (
    current_app,
    flash,
    redirect,
    request,
    session,
    url_for,
)

from flask_login import (
    current_user,
)

from app.extensions import (
    db,
    csrf,
)

from app.models import (
    Company,
    Subscription,
    User,
)

from . import subscription_bp


# ============================================================
# SUBSCRIPTION CONSTANTS
# ============================================================

MONTHLY_AMOUNT = Decimal("15000.00")

ANNUAL_AMOUNT = Decimal("135000.00")

MAINTENANCE_FEE_PER_DAY = Decimal("500.00")

TRIAL_DURATION_DAYS = 7

GRACE_PERIOD_DAYS = 30

TAKEDOWN_PERIOD_DAYS = 60


# ============================================================
# SUBSCRIPTION PLANS
# ============================================================

SUBSCRIPTION_PLANS = {

    "monthly": {
        "name": "Monthly",
        "amount": MONTHLY_AMOUNT,
        "duration_days": 30,
    },

    "annual": {
        "name": "Annual",
        "amount": ANNUAL_AMOUNT,
        "duration_days": 365,
    },

}


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now():
    """
    Return the current UTC datetime.
    """

    return datetime.now(
        timezone.utc
    )


# ============================================================
# PAYSTACK CONFIGURATION
# ============================================================

def get_paystack_secret_key():

    secret_key = current_app.config.get(
        "PAYSTACK_SECRET_KEY"
    )

    if not secret_key:

        raise RuntimeError(
            "PAYSTACK_SECRET_KEY is not configured."
        )

    return secret_key


def get_paystack_base_url():

    return current_app.config.get(
        "PAYSTACK_BASE_URL",
        "https://api.paystack.co",
    ).rstrip("/")


# ============================================================
# TRANSACTION REFERENCE
# ============================================================

def generate_transaction_reference():

    return (
        "BIZTRACE_"
        + utc_now().strftime(
            "%Y%m%d%H%M%S"
        )
        + "_"
        + secrets.token_hex(8).upper()
    )


# ============================================================
# PLAN HELPER
# ============================================================

def get_plan(plan):

    return SUBSCRIPTION_PLANS.get(
        plan
    )


# ============================================================
# GET LATEST COMPANY SUBSCRIPTION
# ============================================================

def get_latest_subscription(company_id):

    return (
        Subscription.query
        .filter_by(
            company_id=company_id
        )
        .order_by(
            Subscription.created_at.desc()
        )
        .first()
    )


# ============================================================
# GET ORIGINAL TRIAL SUBSCRIPTION
# ============================================================

def get_trial_subscription(company_id):

    return (
        Subscription.query
        .filter_by(
            company_id=company_id,
            plan="trial",
        )
        .order_by(
            Subscription.created_at.asc()
        )
        .first()
    )


# ============================================================
# MAINTENANCE CALCULATION
# ============================================================

def calculate_maintenance_days(
    subscription,
    now=None,
):
    """
    Maintenance starts 30 days after the trial expires.

    Example:

        Trial expires:
            January 1

        Grace period:
            January 1 - January 31

        Maintenance starts:
            February 1

        Maintenance:
            ₦500 per day
    """

    if now is None:

        now = utc_now()

    if not subscription:

        return 0

    trial_expiry = (
        subscription.trial_expires_at
    )

    if not trial_expiry:

        return 0

    maintenance_start = (
        trial_expiry
        + timedelta(
            days=GRACE_PERIOD_DAYS
        )
    )

    if now <= maintenance_start:

        return 0

    days = (
        now.date()
        - maintenance_start.date()
    ).days

    if days < 0:

        return 0

    return days


# ============================================================
# MAINTENANCE FEE
# ============================================================

def calculate_maintenance_fee(
    subscription,
    now=None,
):
    """
    Calculate the current maintenance fee.

    ₦500 per maintenance day.
    """

    days = calculate_maintenance_days(
        subscription,
        now,
    )

    return (
        Decimal(days)
        * MAINTENANCE_FEE_PER_DAY
    )


# ============================================================
# UPDATE MAINTENANCE INFORMATION
# ============================================================

def update_maintenance_information(
    subscription,
    now=None,
):
    """
    Update maintenance_days and maintenance_fee
    using backend-controlled dates.

    The browser never supplies these values.
    """

    if now is None:

        now = utc_now()

    maintenance_days = (
        calculate_maintenance_days(
            subscription,
            now,
        )
    )

    maintenance_fee = (
        Decimal(
            maintenance_days
        )
        * MAINTENANCE_FEE_PER_DAY
    )

    subscription.maintenance_days = (
        maintenance_days
    )

    subscription.maintenance_fee = (
        maintenance_fee
    )

    return (
        maintenance_days,
        maintenance_fee,
    )


# ============================================================
# TWO-MONTH TAKEDOWN CHECK
# ============================================================

def is_company_due_for_takedown(
    subscription,
    now=None,
):
    """
    Determine whether the company has passed the
    two-month period after trial expiry.

    IMPORTANT:
    This function does NOT delete data.

    Actual permanent deletion should be handled separately
    after reviewing all company-related models and records.
    """

    if now is None:

        now = utc_now()

    if not subscription:

        return False

    trial_expiry = (
        subscription.trial_expires_at
    )

    if not trial_expiry:

        return False

    takedown_date = (
        trial_expiry
        + timedelta(
            days=TAKEDOWN_PERIOD_DAYS
        )
    )

    return now >= takedown_date


# ============================================================
# UPDATE SUBSCRIPTION LIFECYCLE
# ============================================================

def update_subscription_lifecycle(
    subscription,
    company=None,
    now=None,
):
    """
    Apply automatic subscription lifecycle rules.

    Rules:

        1. Trial remains active for 7 days.
        2. After trial expiry, company enters a 30-day
           grace period.
        3. After the grace period, maintenance is ₦500/day.
        4. After 60 days from trial expiry, company is due
           for takedown.
        5. Manual activation bypasses automatic expiry.
    """

    if now is None:

        now = utc_now()

    if not subscription:

        return {
            "state": "none",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # MANUAL ACTIVATION
    # ========================================================

    if subscription.manually_activated:

        subscription.status = (
            "manually_active"
        )

        subscription.maintenance_days = 0

        subscription.maintenance_fee = (
            Decimal("0.00")
        )

        if company is not None:

            company.is_active = True

        return {
            "state": "manually_active",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # CURRENT ACTIVE PAID SUBSCRIPTION
    # ========================================================

    if (
        subscription.status == "active"
        and subscription.end_date
        and subscription.end_date > now
    ):

        subscription.maintenance_days = 0

        subscription.maintenance_fee = (
            Decimal("0.00")
        )

        if company is not None:

            company.is_active = True

        return {
            "state": "active",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # ACTIVE TRIAL
    # ========================================================

    if (
        subscription.plan == "trial"
        and subscription.trial_expires_at
        and subscription.trial_expires_at > now
    ):

        subscription.status = "trial"

        subscription.maintenance_days = 0

        subscription.maintenance_fee = (
            Decimal("0.00")
        )

        if company is not None:

            company.is_active = True

        return {
            "state": "trial",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # TRIAL HAS EXPIRED
    # ========================================================

    trial_expiry = (
        subscription.trial_expires_at
    )

    if not trial_expiry:

        return {
            "state": subscription.status,
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # TWO-MONTH TAKEDOWN CHECK
    # ========================================================

    due_for_takedown = (
        is_company_due_for_takedown(
            subscription,
            now,
        )
    )

    # ========================================================
    # MAINTENANCE
    # ========================================================

    maintenance_days = (
        calculate_maintenance_days(
            subscription,
            now,
        )
    )

    maintenance_fee = (
        Decimal(
            maintenance_days
        )
        * MAINTENANCE_FEE_PER_DAY
    )

    subscription.maintenance_days = (
        maintenance_days
    )

    subscription.maintenance_fee = (
        maintenance_fee
    )

    # ========================================================
    # GRACE PERIOD
    # ========================================================

    grace_end = (
        trial_expiry
        + timedelta(
            days=GRACE_PERIOD_DAYS
        )
    )

    if now < grace_end:

        subscription.status = "expired"

        if company is not None:

            company.is_active = False

        return {
            "state": "grace_period",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # MAINTENANCE PERIOD
    # ========================================================

    subscription.status = "maintenance"

    if company is not None:

        company.is_active = False

    return {
        "state": (
            "takedown_due"
            if due_for_takedown
            else "maintenance"
        ),
        "maintenance_days": maintenance_days,
        "maintenance_fee": maintenance_fee,
        "due_for_takedown": due_for_takedown,
    }


# ============================================================
# CALCULATE TOTAL PAYMENT
# ============================================================

def calculate_payment_total(
    plan_code,
    subscription,
    now=None,
):
    """
    Calculate the complete amount the company must pay.

    Monthly:
        ₦30,000

    Annual:
        ₦288,000

    Maintenance:
        ₦500 per maintenance day
    """

    if now is None:

        now = utc_now()

    plan = get_plan(
        plan_code
    )

    if plan is None:

        raise ValueError(
            "Invalid subscription plan."
        )

    base_amount = (
        Decimal(
            str(
                plan["amount"]
            )
        )
    )

    maintenance_fee = (
        calculate_maintenance_fee(
            subscription,
            now,
        )
    )

    total_amount = (
        base_amount
        + maintenance_fee
    )

    return (
        base_amount,
        maintenance_fee,
        total_amount,
    )


# ============================================================
# CLEAR DEACTIVATED PAYMENT SESSION
# ============================================================

def clear_deactivated_payment_session():

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


# ============================================================
# DEACTIVATED COMPANY PAYMENT SESSION
# ============================================================

def get_deactivated_payment_session():

    user_id = session.get(
        "subscription_payment_user_id"
    )

    company_id = session.get(
        "subscription_payment_company_id"
    )

    email = session.get(
        "subscription_payment_email"
    )

    created_at = session.get(
        "subscription_payment_created_at"
    )

    if not user_id:

        return None

    if not company_id:

        return None

    if not email:

        return None

    if not created_at:

        return None

    # ========================================================
    # CHECK SESSION TIMESTAMP
    # ========================================================

    try:

        created_datetime = (
            datetime.fromisoformat(
                created_at
            )
        )

    except (
        ValueError,
        TypeError,
    ):

        clear_deactivated_payment_session()

        return None

    # ========================================================
    # MAKE SURE DATETIME IS TIMEZONE-AWARE
    # ========================================================

    if created_datetime.tzinfo is None:

        created_datetime = (
            created_datetime.replace(
                tzinfo=timezone.utc
            )
        )

    # ========================================================
    # SESSION EXPIRES AFTER 15 MINUTES
    # ========================================================

    now = utc_now()

    age = (
        now - created_datetime
    )

    if age > timedelta(
        minutes=15
    ):

        clear_deactivated_payment_session()

        return None

    # ========================================================
    # LOAD USER
    # ========================================================

    user = db.session.get(
        User,
        user_id,
    )

    if user is None:

        clear_deactivated_payment_session()

        return None

    # ========================================================
    # USER MUST STILL BE ACTIVE
    # ========================================================

    if not user.is_active:

        clear_deactivated_payment_session()

        return None

    # ========================================================
    # USER MUST BELONG TO SAME COMPANY
    # ========================================================

    if user.company_id != company_id:

        clear_deactivated_payment_session()

        return None

    # ========================================================
    # EMAIL MUST MATCH DATABASE
    # ========================================================

    database_email = (
        (user.email or "")
        .strip()
        .lower()
    )

    session_email = (
        email
        .strip()
        .lower()
    )

    if database_email != session_email:

        clear_deactivated_payment_session()

        return None

    # ========================================================
    # LOAD COMPANY
    # ========================================================

    company = db.session.get(
        Company,
        company_id,
    )

    if company is None:

        clear_deactivated_payment_session()

        return None

    return {
        "user": user,
        "company": company,
    }


# ============================================================
# INITIALIZE PAYSTACK PAYMENT
# ============================================================

@subscription_bp.route(
    "/initialize",
    methods=["POST"],
)
def initialize_payment():

    # ========================================================
    # DETERMINE PAYMENT CUSTOMER
    # ========================================================

    payment_user = None
    company = None

    # ========================================================
    # NORMAL AUTHENTICATED USER
    # ========================================================

    if current_user.is_authenticated:

        # ----------------------------------------------------
        # SYSTEM ADMINISTRATOR
        # ----------------------------------------------------

        if current_user.is_system_admin:

            flash(
                "System Administrators cannot purchase subscriptions.",
                "warning",
            )

            return redirect(
                url_for(
                    "system_admin.dashboard"
                )
            )

        # ----------------------------------------------------
        # COMPANY CHECK
        # ----------------------------------------------------

        if current_user.company_id is None:

            flash(
                "Your account is not associated with a company.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        payment_user = current_user

        company = db.session.get(
            Company,
            current_user.company_id,
        )

        if company is None:

            flash(
                "Your company account could not be found.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        # ----------------------------------------------------
        # USER CHECK
        # ----------------------------------------------------

        if not current_user.is_active:

            flash(
                "Your user account has been deactivated.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

    # ========================================================
    # DEACTIVATED COMPANY PAYMENT SESSION
    # ========================================================

    else:

        payment_session = (
            get_deactivated_payment_session()
        )

        if payment_session is None:

            flash(
                "Your payment session has expired. "
                "Please enter your login details again.",
                "warning",
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        payment_user = (
            payment_session["user"]
        )

        company = (
            payment_session["company"]
        )

    # ========================================================
    # PLAN
    # ========================================================

    plan_code = (
        request.form.get(
            "plan",
            "",
        )
        .strip()
        .lower()
    )

    plan = get_plan(
        plan_code
    )

    if plan is None:

        flash(
            "Invalid subscription plan selected.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # CUSTOMER EMAIL
    # ========================================================

    customer_email = (
        payment_user.email
        or ""
    ).strip().lower()

    if not customer_email:

        flash(
            "A valid customer email address is required.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # UPDATE EXISTING SUBSCRIPTION LIFECYCLE
    # ========================================================

    try:

        latest_subscription = (
            get_latest_subscription(
                company.id
            )
        )

        update_subscription_lifecycle(
            latest_subscription,
            company=company,
        )

        db.session.flush()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "SUBSCRIPTION LIFECYCLE ERROR"
        )

        flash(
            "We could not prepare your subscription payment. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # GET ORIGINAL TRIAL
    # ========================================================

    trial_subscription = (
        get_trial_subscription(
            company.id
        )
    )

    # ========================================================
    # MAINTENANCE CALCULATION
    # ========================================================

    maintenance_days = 0

    maintenance_fee = (
        Decimal("0.00")
    )

    try:

        if trial_subscription:

            maintenance_days = (
                calculate_maintenance_days(
                    trial_subscription
                )
            )

            maintenance_fee = (
                calculate_maintenance_fee(
                    trial_subscription
                )
            )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "MAINTENANCE CALCULATION ERROR"
        )

        flash(
            "We could not calculate your subscription balance. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # BASE PLAN AMOUNT
    # ========================================================

    try:

        base_amount = Decimal(
            str(
                plan["amount"]
            )
        ).quantize(
            Decimal("0.01")
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):

        current_app.logger.exception(
            "INVALID SUBSCRIPTION PLAN AMOUNT"
        )

        flash(
            "The selected subscription plan has an invalid amount.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # TOTAL PAYMENT
    # ========================================================

    total_amount = (
        base_amount
        + maintenance_fee
    ).quantize(
        Decimal("0.01")
    )

    if total_amount <= Decimal("0.00"):

        flash(
            "The subscription payment amount is invalid.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # GENERATE UNIQUE REFERENCES
    # ========================================================

    transaction_reference = (
        generate_transaction_reference()
    )

    order_id = (
        "BIZTRACE-"
        + uuid.uuid4().hex.upper()
    )

    # ========================================================
    # CREATE PENDING SUBSCRIPTION
    # ========================================================

    subscription = Subscription(

        company_id=company.id,

        plan=plan_code,

        # Store the exact amount that Paystack will charge.
        # This includes maintenance where applicable.
        amount=total_amount,

        currency="NGN",

        status="pending",

        payment_status="pending",

        transaction_reference=(
            transaction_reference
        ),

        order_id=order_id,

        paystack_reference=None,

        paystack_transaction_id=None,

        paystack_access_code=None,

        payment_method=None,

        gateway_response=None,

        start_date=None,

        end_date=None,

        trial_started_at=None,

        trial_expires_at=None,

        paid_at=None,

        verified_at=None,

        activation_source=None,

        manually_activated=False,

        manually_activated_by=None,

        manually_activated_at=None,

        maintenance_fee=maintenance_fee,

        maintenance_days=maintenance_days,
    )

    db.session.add(
        subscription
    )

    # ========================================================
    # FLUSH SO SUBSCRIPTION GETS ID
    # ========================================================

    try:

        db.session.flush()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "SUBSCRIPTION CREATION ERROR"
        )

        flash(
            "We could not create your payment request. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # PAYSTACK CONFIGURATION
    # ========================================================

    try:

        secret_key = (
            get_paystack_secret_key()
        )

        paystack_base_url = (
            get_paystack_base_url()
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "PAYSTACK CONFIGURATION ERROR"
        )

        flash(
            "Payment service is currently unavailable. "
            "Please try again later.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # CONVERT NGN TO KOBO
    # ========================================================

    amount_in_kobo = int(
        (
            total_amount
            * Decimal("100")
        ).quantize(
            Decimal("1")
        )
    )

    # ========================================================
    # PAYSTACK CALLBACK URL
    # ========================================================

    callback_url = url_for(
        "subscription.payment_callback",
        _external=True,
    )

    # ========================================================
    # PAYSTACK INITIALIZATION PAYLOAD
    # ========================================================

    payload = {

        "email": customer_email,

        "amount": str(
            amount_in_kobo
        ),

        "currency": "NGN",

        "reference": (
            transaction_reference
        ),

        "callback_url": callback_url,

        "metadata": {

            "company_id": str(
                company.id
            ),

            "user_id": str(
                payment_user.id
            ),

            "subscription_id": str(
                subscription.id
            ),

            "order_id": order_id,

            "plan": plan_code,

            "base_amount": str(
                base_amount
            ),

            "maintenance_fee": str(
                maintenance_fee
            ),

            "maintenance_days": (
                maintenance_days
            ),

            "total_amount": str(
                total_amount
            ),

            "product": (
                "BizTrace IMS Subscription"
            ),
        },
    }

    # ========================================================
    # CALL PAYSTACK
    # ========================================================

    try:

        response = requests.post(

            f"{paystack_base_url}/transaction/initialize",

            json=payload,

            headers={
                "Authorization": (
                    f"Bearer {secret_key}"
                ),
                "Content-Type": (
                    "application/json"
                ),
                "Cache-Control": (
                    "no-cache"
                ),
            },

            timeout=30,
        )

    except requests.RequestException:

        db.session.rollback()

        current_app.logger.exception(
            "PAYSTACK INITIALIZATION REQUEST FAILED"
        )

        flash(
            "Unable to connect to the payment service. "
            "Please check your internet connection and try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # PARSE PAYSTACK RESPONSE
    # ========================================================

    try:

        paystack_response = (
            response.json()
        )

    except ValueError:

        db.session.rollback()

        current_app.logger.error(
            "PAYSTACK RETURNED INVALID JSON. "
            "HTTP STATUS: %s",
            response.status_code,
        )

        flash(
            "The payment service returned an invalid response. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # CHECK PAYSTACK RESPONSE
    # ========================================================

    if (
        response.status_code != 200
        or not paystack_response.get(
            "status"
        )
    ):

        error_message = (
            paystack_response.get(
                "message"
            )
            or "Payment initialization failed."
        )

        db.session.rollback()

        current_app.logger.error(
            "PAYSTACK INITIALIZATION FAILED: %s",
            paystack_response,
        )

        flash(
            error_message,
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # EXTRACT PAYSTACK DATA
    # ========================================================

    paystack_data = (
        paystack_response.get(
            "data"
        )
        or {}
    )

    authorization_url = (
        paystack_data.get(
            "authorization_url"
        )
    )

    paystack_reference = (
        paystack_data.get(
            "reference"
        )
    )

    access_code = (
        paystack_data.get(
            "access_code"
        )
    )

    if not authorization_url:

        db.session.rollback()

        current_app.logger.error(
            "PAYSTACK DID NOT RETURN AN AUTHORIZATION URL: %s",
            paystack_response,
        )

        flash(
            "Payment checkout could not be created. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # SAVE PAYSTACK INFORMATION
    # ========================================================

    subscription.paystack_reference = (
        paystack_reference
    )

    subscription.paystack_access_code = (
        access_code
    )

    subscription.payment_method = (
        "paystack"
    )

    subscription.gateway_response = (
        paystack_response.get(
            "message"
        )
    )

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "SUBSCRIPTION PAYMENT DATABASE COMMIT FAILED"
        )

        flash(
            "We could not save your payment request. "
            "Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # CLEAR PAYMENT AUTHORIZATION SESSION
    # ========================================================

    clear_deactivated_payment_session()

    # ========================================================
    # REDIRECT TO PAYSTACK CHECKOUT
    # ========================================================

    return redirect(
        authorization_url
    )


# ============================================================
# PAYMENT CALLBACK
# ============================================================

@subscription_bp.route(
    "/callback",
    methods=["GET"],
)
def payment_callback():

    reference = (
        request.args.get(
            "reference"
        )
        or request.args.get(
            "trxref"
        )
    )

    if not reference:

        flash(
            "Payment reference was not provided.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # ========================================================
    # FIND SUBSCRIPTION
    # ========================================================

    subscription = Subscription.query.filter(
        (
            Subscription.paystack_reference
            == reference
        )
        |
        (
            Subscription.transaction_reference
            == reference
        )
    ).first()

    if subscription is None:

        flash(
            "The payment record could not be found.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    try:

        # ====================================================
        # VERIFY WITH PAYSTACK
        # ====================================================

        verified = (
            verify_paystack_transaction(
                reference
            )
        )

        if not verified:

            flash(
                "Payment could not be verified.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        # ====================================================
        # PROCESS PAYMENT
        # ====================================================

        success = (
            process_successful_payment(
                subscription,
                verified,
            )
        )

        if not success:

            db.session.rollback()

            flash(
                "Payment verification failed.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )

        db.session.commit()

        flash(
            "Payment successful. "
            "Your company account has been reactivated.",
            "success",
        )

        # ====================================================
        # AUTHENTICATED USER
        # ====================================================

        if current_user.is_authenticated:

            return redirect(
                url_for(
                    "dashboard.dashboard"
                )
            )

        # ====================================================
        # DEACTIVATED USER WAS NOT LOGGED IN
        # ====================================================

        return redirect(
            url_for(
                "auth.login"
            )
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "PAYSTACK CALLBACK ERROR"
        )

        flash(
            "Your payment could not be processed automatically. "
            "Please contact support.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )


# ============================================================
# VERIFY PAYSTACK TRANSACTION
# ============================================================

def verify_paystack_transaction(
    reference,
):

    secret_key = (
        get_paystack_secret_key()
    )

    base_url = (
        get_paystack_base_url()
    )

    try:

        response = requests.get(

            f"{base_url}/transaction/verify/"
            f"{reference}",

            headers={
                "Authorization": (
                    f"Bearer {secret_key}"
                ),
                "Cache-Control": (
                    "no-cache"
                ),
            },

            timeout=30,
        )

    except requests.RequestException:

        current_app.logger.exception(
            "PAYSTACK VERIFICATION REQUEST FAILED"
        )

        return None

    try:

        result = response.json()

    except ValueError:

        current_app.logger.error(
            "PAYSTACK VERIFICATION RETURNED INVALID JSON"
        )

        return None

    if (
        response.status_code != 200
        or not result.get(
            "status"
        )
    ):

        current_app.logger.error(
            "PAYSTACK VERIFICATION FAILED: %s",
            result,
        )

        return None

    data = result.get(
        "data"
    )

    if not data:

        return None

    return data


# ============================================================
# PROCESS SUCCESSFUL PAYMENT
# ============================================================

def process_successful_payment(
    subscription,
    payment_data,
):

    # ========================================================
    # PAYMENT STATUS
    # ========================================================

    payment_status = (
        payment_data.get(
            "status"
        )
    )

    if payment_status != "success":

        subscription.payment_status = (
            "failed"
        )

        subscription.status = (
            "failed"
        )

        subscription.gateway_response = (
            json.dumps(
                payment_data
            )
        )

        return False

    # ========================================================
    # EXPECTED AMOUNT
    # ========================================================

    try:

        expected_amount = int(
            (
                Decimal(
                    str(
                        subscription.amount
                    )
                )
                * Decimal("100")
            ).quantize(
                Decimal("1")
            )
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):

        current_app.logger.exception(
            "INVALID SUBSCRIPTION AMOUNT DURING PAYMENT VERIFICATION"
        )

        return False

    # ========================================================
    # ACTUAL PAYSTACK AMOUNT
    # ========================================================

    try:

        paid_amount = int(
            payment_data.get(
                "amount",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        paid_amount = 0

    # ========================================================
    # AMOUNT SECURITY CHECK
    # ========================================================

    if paid_amount != expected_amount:

        current_app.logger.error(
            "PAYSTACK AMOUNT MISMATCH: "
            "expected=%s paid=%s subscription_id=%s",
            expected_amount,
            paid_amount,
            subscription.id,
        )

        subscription.payment_status = (
            "failed"
        )

        subscription.status = (
            "failed"
        )

        subscription.gateway_response = (
            json.dumps(
                payment_data
            )
        )

        return False

    # ========================================================
    # CURRENCY SECURITY CHECK
    # ========================================================

    payment_currency = (
        payment_data.get(
            "currency"
        )
        or ""
    ).upper()

    if payment_currency != "NGN":

        current_app.logger.error(
            "PAYSTACK CURRENCY MISMATCH: "
            "expected=NGN paid=%s",
            payment_currency,
        )

        subscription.payment_status = (
            "failed"
        )

        subscription.status = (
            "failed"
        )

        subscription.gateway_response = (
            json.dumps(
                payment_data
            )
        )

        return False

    # ========================================================
    # REFERENCE SECURITY CHECK
    # ========================================================

    payment_reference = (
        payment_data.get(
            "reference"
        )
    )

    if (
        payment_reference
        and subscription.paystack_reference
        and payment_reference
        != subscription.paystack_reference
    ):

        current_app.logger.error(
            "PAYSTACK REFERENCE MISMATCH: "
            "expected=%s paid=%s",
            subscription.paystack_reference,
            payment_reference,
        )

        return False

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    if (
        subscription.payment_status
        == "paid"
        and subscription.status
        in (
            "active",
            "manually_active",
        )
    ):

        return True

    # ========================================================
    # COMPANY
    # ========================================================

    company = db.session.get(
        Company,
        subscription.company_id,
    )

    if company is None:

        current_app.logger.error(
            "PAYSTACK PAYMENT COMPANY NOT FOUND: "
            "subscription_id=%s",
            subscription.id,
        )

        return False

    # ========================================================
    # CURRENT TIME
    # ========================================================

    now = utc_now()

    # ========================================================
    # PLAN
    # ========================================================

    plan = get_plan(
        subscription.plan
    )

    if plan is None:

        current_app.logger.error(
            "PAYSTACK INVALID SUBSCRIPTION PLAN: "
            "subscription_id=%s plan=%s",
            subscription.id,
            subscription.plan,
        )

        return False

    # ========================================================
    # SUBSCRIPTION DURATION
    # ========================================================

    duration_days = (
        plan["duration_days"]
    )

    # ========================================================
    # START DATE
    # ========================================================

    current_end = (
        subscription.end_date
    )

    if (
        current_end
        and current_end > now
    ):

        start_date = (
            current_end
        )

    else:

        start_date = (
            now
        )

    # ========================================================
    # END DATE
    # ========================================================

    end_date = (
        start_date
        + timedelta(
            days=duration_days
        )
    )

    # ========================================================
    # UPDATE SUBSCRIPTION
    # ========================================================

    subscription.start_date = (
        start_date
    )

    subscription.end_date = (
        end_date
    )

    subscription.payment_status = (
        "paid"
    )

    subscription.status = (
        "active"
    )

    subscription.paid_at = (
        now
    )

    subscription.verified_at = (
        now
    )

    subscription.activation_source = (
        "paystack"
    )

    # ========================================================
    # SAVE COMPLETE PAYSTACK RESPONSE
    # ========================================================

    subscription.gateway_response = (
        json.dumps(
            payment_data
        )
    )

    # ========================================================
    # PAYSTACK TRANSACTION ID
    # ========================================================

    paystack_transaction_id = (
        payment_data.get(
            "id"
        )
    )

    if paystack_transaction_id:

        subscription.paystack_transaction_id = (
            str(
                paystack_transaction_id
            )
        )

    # ========================================================
    # PAYMENT CHANNEL
    # ========================================================

    payment_channel = (
        payment_data.get(
            "channel"
        )
    )

    if payment_channel:

        subscription.payment_method = (
            f"paystack_{payment_channel}"
        )

    else:

        subscription.payment_method = (
            "paystack"
        )

    # ========================================================
    # REACTIVATE COMPANY
    # ========================================================

    company.is_active = True

    # ========================================================
    # RESET MAINTENANCE
    # ========================================================

    subscription.maintenance_fee = (
        Decimal("0.00")
    )

    subscription.maintenance_days = 0

    # ========================================================
    # REMOVE MANUAL ACTIVATION OVERRIDE
    # ========================================================

    subscription.manually_activated = (
        False
    )

    subscription.manually_activated_by = (
        None
    )

    subscription.manually_activated_at = (
        None
    )

    db.session.add(
        subscription
    )

    db.session.add(
        company
    )

    return True


# ============================================================
# PAYSTACK WEBHOOK
# ============================================================

@subscription_bp.route(
    "/webhook",
    methods=["POST"],
)
@csrf.exempt
def paystack_webhook():

    # ========================================================
    # SECRET KEY
    # ========================================================

    try:

        secret_key = (
            get_paystack_secret_key()
        )

    except Exception:

        current_app.logger.exception(
            "PAYSTACK WEBHOOK SECRET ERROR"
        )

        return (
            "Server Error",
            500,
        )

    # ========================================================
    # SIGNATURE
    # ========================================================

    signature = (
        request.headers.get(
            "x-paystack-signature"
        )
    )

    if not signature:

        return (
            "Unauthorized",
            401,
        )

    # ========================================================
    # VERIFY RAW REQUEST SIGNATURE
    # ========================================================

    raw_body = (
        request.get_data()
    )

    expected_signature = (
        hmac.new(

            secret_key.encode(
                "utf-8"
            ),

            raw_body,

            hashlib.sha512,

        ).hexdigest()
    )

    if not hmac.compare_digest(
        expected_signature,
        signature,
    ):

        current_app.logger.warning(
            "INVALID PAYSTACK WEBHOOK SIGNATURE"
        )

        return (
            "Unauthorized",
            401,
        )

    # ========================================================
    # PARSE EVENT
    # ========================================================

    try:

        event = (
            request.get_json(
                silent=True
            )
            or {}
        )

    except Exception:

        return (
            "Bad Request",
            400,
        )

    event_name = (
        event.get(
            "event"
        )
    )

    data = (
        event.get(
            "data"
        )
        or {}
    )

    # ========================================================
    # ONLY PROCESS SUCCESSFUL CHARGES
    # ========================================================

    if event_name != "charge.success":

        return (
            "OK",
            200,
        )

    # ========================================================
    # PAYMENT REFERENCE
    # ========================================================

    reference = (
        data.get(
            "reference"
        )
    )

    if not reference:

        return (
            "OK",
            200,
        )

    # ========================================================
    # FIND SUBSCRIPTION
    # ========================================================

    subscription = Subscription.query.filter(
        (
            Subscription.paystack_reference
            == reference
        )
        |
        (
            Subscription.transaction_reference
            == reference
        )
    ).first()

    if subscription is None:

        current_app.logger.warning(
            "PAYSTACK WEBHOOK SUBSCRIPTION "
            "NOT FOUND: %s",
            reference,
        )

        return (
            "OK",
            200,
        )

    # ========================================================
    # VERIFY AND PROCESS
    # ========================================================

    try:

        # ----------------------------------------------------
        # RE-VERIFY WITH PAYSTACK
        # ----------------------------------------------------

        verified = (
            verify_paystack_transaction(
                reference
            )
        )

        if not verified:

            current_app.logger.warning(
                "PAYSTACK WEBHOOK VERIFICATION "
                "FAILED: %s",
                reference,
            )

            return (
                "OK",
                200,
            )

        # ----------------------------------------------------
        # PROCESS PAYMENT
        # ----------------------------------------------------

        success = (
            process_successful_payment(
                subscription,
                verified,
            )
        )

        if success:

            db.session.commit()

            current_app.logger.info(
                "PAYSTACK WEBHOOK PAYMENT "
                "SUCCESSFUL: reference=%s "
                "subscription_id=%s",
                reference,
                subscription.id,
            )

        else:

            db.session.rollback()

            current_app.logger.warning(
                "PAYSTACK WEBHOOK PAYMENT "
                "REJECTED: reference=%s "
                "subscription_id=%s",
                reference,
                subscription.id,
            )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "PAYSTACK WEBHOOK PROCESSING ERROR"
        )

    # ========================================================
    # ALWAYS ACKNOWLEDGE PAYSTACK
    # ========================================================

    return (
        "OK",
        200,
    )
