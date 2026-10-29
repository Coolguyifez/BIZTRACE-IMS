# ============================================================
# BIZTRACE IMS - PAYSTACK SUBSCRIPTION ROUTES
# ============================================================

import json
import secrets
import hmac
import hashlib
import uuid
import click

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

from flask_login import current_user

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

MONTHLY_AMOUNT = Decimal("8000.00")

ANNUAL_AMOUNT = Decimal("86400.00")

MAINTENANCE_FEE_PER_DAY = Decimal("150.00")

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
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(
        timezone.utc
    )


def ensure_utc_datetime(value):
    """
    Normalize a datetime value to a timezone-aware UTC datetime.

    SQLite may return DateTime values without timezone information,
    even when the SQLAlchemy column was defined with timezone=True.

    PostgreSQL may return timezone-aware values.

    This helper makes both database backends behave consistently.
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
    """
    Return the most recently created subscription record.

    Useful for displaying the latest payment/subscription record.

    Do NOT use this alone for lifecycle decisions because a newer
    pending payment can exist while an older paid subscription
    is still the valid lifecycle subscription.
    """

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
# GET LATEST PAID SUBSCRIPTION
# ============================================================

def get_latest_paid_subscription(company_id):
    """
    Return the most recent successfully paid monthly or annual
    subscription.

    Trial, pending, failed and cancelled subscriptions are
    excluded.

    This record is the basis for maintenance calculations.
    """

    return (
        Subscription.query
        .filter(
            Subscription.company_id == company_id,
            Subscription.plan.in_(
                (
                    "monthly",
                    "annual",
                )
            ),
            Subscription.payment_status == "paid",
            Subscription.end_date.isnot(None),
        )
        .order_by(
            Subscription.end_date.desc(),
            Subscription.created_at.desc(),
        )
        .first()
    )


# ============================================================
# GET LIFECYCLE SUBSCRIPTION
# ============================================================

def get_lifecycle_subscription(company_id):
    """
    Return the subscription record that should control the
    company's automatic subscription lifecycle.

    Priority:

    1. Manual activation
    2. Manual deactivation
    3. Currently active paid subscription
    4. Currently active trial
    5. Most recent expired paid subscription
    6. Most recent expired trial

    Pending, failed and cancelled payment records do not
    automatically take control of the company's lifecycle.
    """

    subscriptions = (
        Subscription.query
        .filter_by(
            company_id=company_id
        )
        .order_by(
            Subscription.created_at.desc()
        )
        .all()
    )

    if not subscriptions:
        return None

    now = utc_now()

    # ========================================================
    # 1. MANUAL ACTIVATION
    # ========================================================

    for subscription in subscriptions:

        if subscription.manually_activated:

            return subscription

    # ========================================================
    # 2. MANUAL DEACTIVATION
    # ========================================================

    for subscription in subscriptions:

        if subscription.manually_deactivated:

            return subscription

    # ========================================================
    # 3. CURRENTLY ACTIVE PAID SUBSCRIPTION
    # ========================================================

    active_paid = []

    for subscription in subscriptions:

        if subscription.plan not in (
            "monthly",
            "annual",
        ):
            continue

        if subscription.payment_status != "paid":
            continue

        if subscription.status not in (
            "active",
            "manually_active",
        ):
            continue

        end_date = ensure_utc_datetime(
            subscription.end_date
        )

        if end_date is None:
            continue

        if end_date > now:

            active_paid.append(
                subscription
            )

    if active_paid:

        return max(
            active_paid,
            key=lambda subscription: (
                ensure_utc_datetime(
                    subscription.end_date
                )
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            )
        )

    # ========================================================
    # 4. CURRENTLY ACTIVE TRIAL
    # ========================================================

    active_trials = []

    for subscription in subscriptions:

        if subscription.plan != "trial":
            continue

        if subscription.status not in (
            "trial",
            "active",
        ):
            continue

        trial_expires_at = ensure_utc_datetime(
            subscription.trial_expires_at
        )

        if trial_expires_at is None:
            continue

        if trial_expires_at > now:

            active_trials.append(
                subscription
            )

    if active_trials:

        return max(
            active_trials,
            key=lambda subscription: (
                ensure_utc_datetime(
                    subscription.trial_expires_at
                )
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            )
        )

    # ========================================================
    # 5. MOST RECENT EXPIRED PAID SUBSCRIPTION
    # ========================================================

    expired_paid = []

    for subscription in subscriptions:

        if subscription.plan not in (
            "monthly",
            "annual",
        ):
            continue

        if subscription.payment_status != "paid":
            continue

        end_date = ensure_utc_datetime(
            subscription.end_date
        )

        if end_date is None:
            continue

        if end_date <= now:

            expired_paid.append(
                subscription
            )

    if expired_paid:

        return max(
            expired_paid,
            key=lambda subscription: (
                ensure_utc_datetime(
                    subscription.end_date
                )
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            )
        )

    # ========================================================
    # 6. MOST RECENT EXPIRED TRIAL
    # ========================================================

    expired_trials = []

    for subscription in subscriptions:

        if subscription.plan != "trial":
            continue

        trial_expires_at = ensure_utc_datetime(
            subscription.trial_expires_at
        )

        if trial_expires_at is None:
            continue

        if trial_expires_at <= now:

            expired_trials.append(
                subscription
            )

    if expired_trials:

        return max(
            expired_trials,
            key=lambda subscription: (
                ensure_utc_datetime(
                    subscription.trial_expires_at
                )
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            )
        )

    return None


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
    Calculate maintenance days for an expired PAID subscription.

    Rules:

    - Trial subscriptions never incur maintenance.
    - Manual activation/deactivation never incurs maintenance.
    - Only successfully paid monthly/annual subscriptions qualify.
    - First 30 days after paid expiry = grace period.
    - Maintenance starts after the grace period.
    - Maintenance stops at the 60-day takedown point.
    - Maximum maintenance period = 30 days.
    """

    if subscription is None:

        return 0

    if now is None:

        now = utc_now()

    now = ensure_utc_datetime(
        now
    )

    # ========================================================
    # MANUAL OVERRIDES
    # ========================================================

    if subscription.manually_activated:

        return 0

    if subscription.manually_deactivated:

        return 0

    # ========================================================
    # ONLY PAID MONTHLY/ANNUAL SUBSCRIPTIONS
    # ========================================================

    if subscription.plan not in (
        "monthly",
        "annual",
    ):

        return 0

    if subscription.payment_status != "paid":

        return 0

    # ========================================================
    # SUBSCRIPTION EXPIRY
    # ========================================================

    subscription_expiry = ensure_utc_datetime(
        subscription.end_date
    )

    if subscription_expiry is None:

        return 0

    # ========================================================
    # NOT YET EXPIRED
    # ========================================================

    if now <= subscription_expiry:

        return 0

    # ========================================================
    # GRACE PERIOD END
    # ========================================================

    grace_end = (
        subscription_expiry
        + timedelta(
            days=GRACE_PERIOD_DAYS
        )
    )

    # ========================================================
    # STILL IN GRACE PERIOD
    # ========================================================

    if now <= grace_end:

        return 0

    # ========================================================
    # TAKEDOWN DATE
    # ========================================================

    takedown_date = (
        subscription_expiry
        + timedelta(
            days=TAKEDOWN_PERIOD_DAYS
        )
    )

    # ========================================================
    # MAXIMUM MAINTENANCE DAYS
    # ========================================================

    max_maintenance_days = max(
        TAKEDOWN_PERIOD_DAYS
        - GRACE_PERIOD_DAYS,
        0,
    )

    # ========================================================
    # TAKEDOWN REACHED
    #
    # Freeze maintenance.
    # Do not allow the amount to increase any further.
    # ========================================================

    if now >= takedown_date:

        return max_maintenance_days

    # ========================================================
    # CALCULATE CURRENT MAINTENANCE DAYS
    # ========================================================

    maintenance_days = (
        now.date()
        - grace_end.date()
    ).days

    if maintenance_days < 0:

        maintenance_days = 0

    if maintenance_days > max_maintenance_days:

        maintenance_days = (
            max_maintenance_days
        )

    return maintenance_days


# ============================================================
# MAINTENANCE FEE
# ============================================================

def calculate_maintenance_fee(
    subscription,
    now=None,
):
    """
    Calculate maintenance fee.

    Maintenance fee is:

        maintenance_days × ₦500
    """

    maintenance_days = (
        calculate_maintenance_days(
            subscription,
            now=now,
        )
    )

    return (
        Decimal(
            maintenance_days
        )
        * MAINTENANCE_FEE_PER_DAY
    )


# ============================================================
# TAKEDOWN CHECK
# ============================================================

def is_company_due_for_takedown(
    subscription,
    now=None,
):
    """
    Determine whether a PAID subscription has reached
    the 60-day takedown point after paid subscription expiry.

    IMPORTANT:

    Trial expiry is NOT used here.

    Trial expiry does not start the takedown countdown.

    Only a successfully paid monthly/annual subscription
    can reach takedown.

    This function does NOT delete company data.
    """

    if subscription is None:

        return False

    if now is None:

        now = utc_now()

    now = ensure_utc_datetime(
        now
    )

    # ========================================================
    # MANUAL OVERRIDES
    # ========================================================

    if subscription.manually_activated:

        return False

    if subscription.manually_deactivated:

        return False

    # ========================================================
    # ONLY PAID MONTHLY/ANNUAL SUBSCRIPTIONS
    # ========================================================

    if subscription.plan not in (
        "monthly",
        "annual",
    ):

        return False

    if subscription.payment_status != "paid":

        return False

    # ========================================================
    # PAID EXPIRY
    # ========================================================

    subscription_expiry = ensure_utc_datetime(
        subscription.end_date
    )

    if subscription_expiry is None:

        return False

    # ========================================================
    # TAKEDOWN DATE
    # ========================================================

    takedown_date = (
        subscription_expiry
        + timedelta(
            days=TAKEDOWN_PERIOD_DAYS
        )
    )

    return (
        now >= takedown_date
    )


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

    ============================================================
    TRIAL
    ============================================================

    Trial:
        7 days active.

    After trial expiry:
        - company inactive
        - maintenance = ₦0
        - no grace period
        - no takedown countdown

    ============================================================
    PAID SUBSCRIPTION
    ============================================================

    Monthly/annual:

        Active
           ↓
        Expired
           ↓
        30-day grace
           ↓
        Maintenance
           ↓
        60-day takedown due

    Maximum maintenance:

        30 days × ₦500
        = ₦15,000

    After takedown due:
        - company remains inactive
        - maintenance stops increasing
        - accumulated maintenance remains
        - payment remains available
        - no automatic deletion

    ============================================================
    MANUAL OVERRIDES
    ============================================================

    Manual activation:
        company remains active.

    Manual deactivation:
        company remains inactive.

    Successful Paystack payment clears manual overrides.
    """

    if now is None:

        now = utc_now()

    now = ensure_utc_datetime(
        now
    )

    # ========================================================
    # NO SUBSCRIPTION
    # ========================================================

    if subscription is None:

        return {
            "state": "none",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # MANUAL DEACTIVATION
    # ========================================================

    if subscription.manually_deactivated:

        subscription.status = (
            "manually_deactivated"
        )

        subscription.maintenance_days = 0

        subscription.maintenance_fee = (
            Decimal("0.00")
        )

        if company is not None:

            company.is_active = False

        return {
            "state": "manually_deactivated",
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
    # TRIAL
    # ========================================================

    if subscription.plan == "trial":

        trial_expiry = ensure_utc_datetime(
            subscription.trial_expires_at
        )

        # ----------------------------------------------------
        # TRIAL HAS NO EXPIRY
        # ----------------------------------------------------

        if trial_expiry is None:

            subscription.maintenance_days = 0

            subscription.maintenance_fee = (
                Decimal("0.00")
            )

            return {
                "state": subscription.status,
                "maintenance_days": 0,
                "maintenance_fee": Decimal("0.00"),
                "due_for_takedown": False,
            }

        # ----------------------------------------------------
        # TRIAL ACTIVE
        # ----------------------------------------------------

        if trial_expiry > now:

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

        # ----------------------------------------------------
        # TRIAL EXPIRED
        #
        # STOP HERE.
        #
        # Trial expiry does NOT create:
        #
        # - maintenance
        # - maintenance debt
        # - grace period
        # - takedown
        # ----------------------------------------------------

        subscription.status = "expired"

        subscription.maintenance_days = 0

        subscription.maintenance_fee = (
            Decimal("0.00")
        )

        if company is not None:

            company.is_active = False

        return {
            "state": "trial_expired",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # ONLY MONTHLY / ANNUAL CONTINUE
    # ========================================================

    if subscription.plan not in (
        "monthly",
        "annual",
    ):

        return {
            "state": subscription.status,
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # ONLY SUCCESSFULLY PAID SUBSCRIPTIONS
    # ========================================================

    if subscription.payment_status != "paid":

        return {
            "state": subscription.status,
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # PAID EXPIRY
    # ========================================================

    subscription_expiry = ensure_utc_datetime(
        subscription.end_date
    )

    if subscription_expiry is None:

        return {
            "state": subscription.status,
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # PAID SUBSCRIPTION STILL ACTIVE
    # ========================================================

    if subscription_expiry > now:

        subscription.status = "active"

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
    # PAID SUBSCRIPTION HAS EXPIRED
    # ========================================================

    grace_end = (
        subscription_expiry
        + timedelta(
            days=GRACE_PERIOD_DAYS
        )
    )

    takedown_date = (
        subscription_expiry
        + timedelta(
            days=TAKEDOWN_PERIOD_DAYS
        )
    )

    due_for_takedown = (
        now >= takedown_date
    )

    # ========================================================
    # COMPANY MUST BE INACTIVE AFTER PAID EXPIRY
    # ========================================================

    if company is not None:

        company.is_active = False

    # ========================================================
    # GRACE PERIOD
    # ========================================================

    if now < grace_end:

        subscription.status = "expired"

        subscription.maintenance_days = 0

        subscription.maintenance_fee = (
            Decimal("0.00")
        )

        return {
            "state": "grace_period",
            "maintenance_days": 0,
            "maintenance_fee": Decimal("0.00"),
            "due_for_takedown": False,
        }

    # ========================================================
    # MAINTENANCE
    # ========================================================

    maintenance_days = (
        calculate_maintenance_days(
            subscription,
            now=now,
        )
    )

    maintenance_fee = (
        Decimal(
            maintenance_days
        )
        * MAINTENANCE_FEE_PER_DAY
    )

    subscription.status = "maintenance"

    subscription.maintenance_days = (
        maintenance_days
    )

    subscription.maintenance_fee = (
        maintenance_fee
    )

    # ========================================================
    # TAKEDOWN DUE
    # ========================================================

    if due_for_takedown:

        return {
            "state": "takedown_due",
            "maintenance_days": maintenance_days,
            "maintenance_fee": maintenance_fee,
            "due_for_takedown": True,
        }

    # ========================================================
    # NORMAL MAINTENANCE
    # ========================================================

    return {
        "state": "maintenance",
        "maintenance_days": maintenance_days,
        "maintenance_fee": maintenance_fee,
        "due_for_takedown": False,
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
    Calculate the total amount payable.

    Total:

        subscription plan
        +
        accumulated maintenance

    Maintenance is capped at the takedown point.
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

    base_amount = Decimal(
        str(
            plan["amount"]
        )
    ).quantize(
        Decimal("0.01")
    )

    maintenance_fee = (
        calculate_maintenance_fee(
            subscription,
            now=now,
        )
    )

    total_amount = (
        base_amount
        + maintenance_fee
    ).quantize(
        Decimal("0.01")
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
# GET DEACTIVATED COMPANY PAYMENT SESSION
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
    # SESSION TIMESTAMP
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

    created_datetime = ensure_utc_datetime(
        created_datetime
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
    # EMAIL SECURITY CHECK
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
    # PAYMENT CUSTOMER
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
        # COMPANY ID
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

        # ----------------------------------------------------
        # COMPANY
        # ----------------------------------------------------

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
        # USER ACTIVE CHECK
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
    # UPDATE CURRENT LIFECYCLE
    # ========================================================

    try:

        lifecycle_subscription = (
            get_lifecycle_subscription(
                company.id
            )
        )

        lifecycle_result = (
            update_subscription_lifecycle(
                lifecycle_subscription,
                company=company,
            )
        )

        db.session.flush()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "SUBSCRIPTION LIFECYCLE ERROR "
            "BEFORE PAYMENT INITIALIZATION"
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
    # GET LATEST SUCCESSFULLY PAID SUBSCRIPTION
    # ========================================================
    #
    # IMPORTANT:
    #
    # Maintenance is NEVER calculated from the trial.
    #
    # Only a successfully paid monthly/annual subscription
    # can create maintenance.
    # ========================================================

    paid_subscription = (
        get_latest_paid_subscription(
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

        if paid_subscription is not None:

            maintenance_days = (
                calculate_maintenance_days(
                    paid_subscription
                )
            )

            maintenance_fee = (
                calculate_maintenance_fee(
                    paid_subscription
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
    # GENERATE REFERENCES
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

        manually_deactivated=False,

        manually_deactivated_by=None,

        manually_deactivated_at=None,

        maintenance_fee=maintenance_fee,

        maintenance_days=maintenance_days,
    )

    db.session.add(
        subscription
    )

    # ========================================================
    # FLUSH
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
    # CALLBACK URL
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

            f"{paystack_base_url}"
            "/transaction/initialize",

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
    # PARSE RESPONSE
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
    # CHECK RESPONSE
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
    # PAYSTACK DATA
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
            "PAYSTACK DID NOT RETURN "
            "AN AUTHORIZATION URL: %s",
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
    # COMMIT
    # ========================================================

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "SUBSCRIPTION PAYMENT DATABASE "
            "COMMIT FAILED"
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
    # CLEAR PAYMENT SESSION
    # ========================================================

    clear_deactivated_payment_session()

    # ========================================================
    # REDIRECT TO PAYSTACK
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

    subscription = (
        Subscription.query.filter(
            (
                Subscription.paystack_reference
                == reference
            )
            |
            (
                Subscription.transaction_reference
                == reference
            )
        )
        .first()
    )

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
        # VERIFY PAYMENT
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

        clear_deactivated_payment_session()

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
        # DEACTIVATED COMPANY USER
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

            f"{base_url}"
            "/transaction/verify/"
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
            "PAYSTACK VERIFICATION "
            "RETURNED INVALID JSON"
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

    data = (
        result.get(
            "data"
        )
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
    """
    Process a verified successful Paystack payment.

    This function:

    - verifies transaction status
    - verifies amount
    - verifies currency
    - verifies reference
    - prevents duplicate fulfillment
    - activates the subscription
    - reactivates the company
    - clears maintenance
    - clears manual overrides
    """

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
            "INVALID SUBSCRIPTION AMOUNT "
            "DURING PAYMENT VERIFICATION"
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
    # PAYSTACK FEES
    # ========================================================

    try:

        paystack_fees = int(
            payment_data.get(
                "fees",
                0,
            )
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        paystack_fees = 0

    # ========================================================
    # NET BUSINESS AMOUNT
    # ========================================================

    net_paid_amount = (
        paid_amount
        - paystack_fees
    )

    # ========================================================
    # AMOUNT SECURITY CHECK
    # ========================================================
    #
    # Accept:
    #
    # 1. Exact amount
    #
    # OR
    #
    # 2. Customer-paid Paystack fee:
    #
    #     paid amount - Paystack fee
    #     =
    #     BizTrace amount
    #
    # ========================================================

    amount_is_valid = (
        paid_amount == expected_amount
        or
        net_paid_amount == expected_amount
    )

    if not amount_is_valid:

        current_app.logger.error(
            "PAYSTACK AMOUNT MISMATCH: "
            "expected=%s paid=%s fees=%s "
            "net_paid=%s subscription_id=%s",
            expected_amount,
            paid_amount,
            paystack_fees,
            net_paid_amount,
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
    # CURRENT END DATE
    # ========================================================

    current_end = ensure_utc_datetime(
        subscription.end_date
    )

    # ========================================================
    # START DATE
    # ========================================================

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
    # CLEAR MANUAL ACTIVATION
    # ========================================================

    subscription.manually_activated = False

    subscription.manually_activated_by = None

    subscription.manually_activated_at = None

    # ========================================================
    # CLEAR MANUAL DEACTIVATION
    # ========================================================

    subscription.manually_deactivated = False

    subscription.manually_deactivated_by = None

    subscription.manually_deactivated_at = None

    # ========================================================
    # SAVE
    # ========================================================

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
    # RAW REQUEST BODY
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

    event = (
        request.get_json(
            silent=True
        )
        or {}
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
    # ONLY SUCCESSFUL CHARGES
    # ========================================================

    if event_name != "charge.success":

        return (
            "OK",
            200,
        )

    # ========================================================
    # REFERENCE
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

    subscription = (
        Subscription.query.filter(
            (
                Subscription.paystack_reference
                == reference
            )
            |
            (
                Subscription.transaction_reference
                == reference
            )
        )
        .first()
    )

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
    # ACKNOWLEDGE PAYSTACK
    # ========================================================

    return (
        "OK",
        200,
    )


# ============================================================
# AUTOMATIC SUBSCRIPTION LIFECYCLE CHECKER
# ============================================================

def run_subscription_lifecycle():
    """
    Run the automatic subscription lifecycle checker.

    It checks every company and:

        - activates valid active subscriptions
        - deactivates expired subscriptions
        - starts maintenance after grace
        - freezes maintenance at takedown
        - reports takedown-due companies
        - respects manual activation
        - respects manual deactivation

    It does NOT delete company data.
    """

    now = utc_now()

    companies = (
        Company.query
        .order_by(
            Company.id.asc()
        )
        .all()
    )

    results = {

        "checked": 0,

        "activated": 0,

        "deactivated": 0,

        "maintenance": 0,

        "takedown_due": 0,

        "manual_active": 0,

        "manual_deactivated": 0,

        "no_subscription": 0,

        "errors": 0,
    }

    for company in companies:

        results["checked"] += 1

        try:

            subscription = (
                get_lifecycle_subscription(
                    company.id
                )
            )

            if subscription is None:

                results[
                    "no_subscription"
                ] += 1

                continue

            # ------------------------------------------------
            # PREVIOUS COMPANY STATUS
            # ------------------------------------------------

            previous_company_active = bool(
                company.is_active
            )

            # ------------------------------------------------
            # UPDATE LIFECYCLE
            # ------------------------------------------------

            result = (
                update_subscription_lifecycle(
                    subscription=subscription,
                    company=company,
                    now=now,
                )
            )

            state = (
                result.get(
                    "state"
                )
            )

            # ------------------------------------------------
            # COUNT RESULT
            # ------------------------------------------------

            if state == "manually_active":

                results[
                    "manual_active"
                ] += 1

            elif state == "manually_deactivated":

                results[
                    "manual_deactivated"
                ] += 1

            elif state in (
                "active",
                "trial",
            ):

                if not previous_company_active:

                    results[
                        "activated"
                    ] += 1

            elif state == "trial_expired":

                if previous_company_active:

                    results[
                        "deactivated"
                    ] += 1

            elif state == "grace_period":

                if previous_company_active:

                    results[
                        "deactivated"
                    ] += 1

            elif state == "maintenance":

                results[
                    "maintenance"
                ] += 1

                if previous_company_active:

                    results[
                        "deactivated"
                    ] += 1

            elif state == "takedown_due":

                results[
                    "takedown_due"
                ] += 1

                if previous_company_active:

                    results[
                        "deactivated"
                    ] += 1

            # ------------------------------------------------
            # SAVE
            # ------------------------------------------------

            db.session.add(
                company
            )

            db.session.add(
                subscription
            )

        except Exception:

            results[
                "errors"
            ] += 1

            db.session.rollback()

            current_app.logger.exception(
                "SUBSCRIPTION LIFECYCLE ERROR "
                "FOR COMPANY %s",
                company.id,
            )

    # ========================================================
    # COMMIT ALL CHANGES
    # ========================================================

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "SUBSCRIPTION LIFECYCLE COMMIT FAILED"
        )

        raise

    return results


# ============================================================
# CLI LIFECYCLE COMMAND
# ============================================================

@subscription_bp.cli.command(
    "lifecycle"
)
def subscription_lifecycle():
    """
    Manually run the automatic subscription lifecycle checker.
    """

    click.echo(
        "============================================================"
    )

    click.echo(
        "BizTrace IMS Subscription Lifecycle Checker"
    )

    click.echo(
        f"Started: {utc_now().isoformat()}"
    )

    try:

        results = (
            run_subscription_lifecycle()
        )

    except Exception as exc:

        click.echo(
            "============================================================"
        )

        click.echo(
            f"[FATAL ERROR] {exc}"
        )

        click.echo(
            "Lifecycle changes were rolled back."
        )

        click.echo(
            "============================================================"
        )

        raise click.ClickException(
            "Subscription lifecycle check failed."
        )

    click.echo(
        "============================================================"
    )

    click.echo(
        "Subscription Lifecycle Summary"
    )

    click.echo(
        "============================================================"
    )

    click.echo(
        f"Companies checked:       "
        f"{results['checked']}"
    )

    click.echo(
        f"Newly activated:         "
        f"{results['activated']}"
    )

    click.echo(
        f"Newly deactivated:       "
        f"{results['deactivated']}"
    )

    click.echo(
        f"Maintenance accounts:    "
        f"{results['maintenance']}"
    )

    click.echo(
        f"Takedown due:            "
        f"{results['takedown_due']}"
    )

    click.echo(
        f"Manual active:           "
        f"{results['manual_active']}"
    )

    click.echo(
        f"Manual deactivated:      "
        f"{results['manual_deactivated']}"
    )

    click.echo(
        f"No subscription:         "
        f"{results['no_subscription']}"
    )

    click.echo(
        f"Errors:                  "
        f"{results['errors']}"
    )

    click.echo(
        f"Finished: {utc_now().isoformat()}"
    )

    click.echo(
        "============================================================"
    )