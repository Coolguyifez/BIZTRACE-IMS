import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import current_app, url_for

from app.extensions import db
from app.models import (
    Notification,
    NotificationRecipient,
    NotificationAssignment,
    PushSubscription,
    User,
    Sale,
    SaleItem,
    Product,
    Expense,
)
from app.utils.company_settings import (
    company_now,
    format_currency,
    get_company_timezone,
)

logger = logging.getLogger(__name__)


# =========================================================
# NOTIFICATION CATEGORIES
# =========================================================
#
# These control NOTIFICATION DELIVERY.
#
# NotificationAssignment uses these values.
#
# IMPORTANT:
#
# Sound names are NOT notification categories.
#
# Sound-only values:
#
#     success
#     system
#     error
#     low_stock
#     gross_loss
#     net_loss
#
# must NEVER be used as Notification.category.
# =========================================================

NOTIFICATION_CATEGORIES = [
    ("sale", "Sales"),
    ("purchase", "Purchases"),
    ("inventory", "Inventory"),
    ("expense", "Expenses"),
    ("cash_deposit", "Cash Deposits"),
    ("financial", "Financial"),

]


VALID_NOTIFICATION_CATEGORIES = {
    category
    for category, label in NOTIFICATION_CATEGORIES
}


# =========================================================
# SOUND TYPES
# =========================================================
#
# These control ONLY the sound.
#
# They do NOT control:
#
#     NotificationAssignment
#     NotificationRecipient
#     browser delivery
#     email delivery
#
# Example:
#
#     category = "sale"
#     sound = "success"
#
# means:
#
#     Sales assignment controls WHO receives it.
#     Success sound preference controls WHETHER the sound
#     is played.
# =========================================================

SOUND_TYPES = {
    "success": {
        "sound": "success",
    },

    "system": {
        "sound": "system",
    },

    "error": {
        "sound": "error",
    },

    "net_loss": {
        "sound": "net-loss",
    },

    "gross_loss": {
        "sound": "gross-loss",
    },

    "low_stock": {
        "sound": "low-stock",
    },
}


VALID_SOUND_TYPES = set(SOUND_TYPES.keys())

# Backward-compatible alias.
SOUND_CATEGORIES = VALID_SOUND_TYPES


# =========================================================
# NOTIFICATION TYPE CONFIGURATION
# =========================================================
#
# These are DELIVERY categories.
#
# "sound" is only the optional default sound.
# =========================================================

NOTIFICATION_TYPES = {
    "sale": {
        "priority": "normal",
        "sound": None,
    },

    "payment": {
        "priority": "normal",
        "sound": None,
    },

    "purchase": {
        "priority": "normal",
        "sound": None,
    },

    "inventory": {
        "priority": "normal",
        "sound": None,
    },

    "expense": {
        "priority": "normal",
        "sound": None,
    },

    "cash_deposit": {
        "priority": "normal",
        "sound": None,
    },

    "receivable": {
        "priority": "high",
        "sound": None,
    },

    "payable": {
        "priority": "high",
        "sound": None,
    },

    "financial": {
        "priority": "critical",
        "sound": None,
    },

    "security": {
        "priority": "high",
        "sound": None,
    },
}


# =========================================================
# TIME HELPERS
# =========================================================

def utc_now():
    """
    Return current UTC datetime.

    Database timestamps remain UTC.
    """
    return datetime.now(timezone.utc)


def normalize_utc_datetime(value):
    """
    Convert a datetime to timezone-aware UTC.

    Naive datetimes are treated as UTC.
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


def to_company_datetime(value):
    """
    Convert UTC datetime into the current company's
    configured timezone.
    """

    value = normalize_utc_datetime(value)

    if value is None:
        return None

    return value.astimezone(
        get_company_timezone()
    )


def company_day_boundaries(target_date=None):
    """
    Return company-local day boundaries converted to UTC.

    The end boundary is exclusive.
    """

    company_timezone = get_company_timezone()

    if target_date is None:
        target_date = company_now().date()

    local_start = datetime.combine(
        target_date,
        datetime.min.time(),
        tzinfo=company_timezone,
    )

    local_end = (
        local_start
        + timedelta(days=1)
    )

    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


# =========================================================
# SOUND HELPERS
# =========================================================

def normalize_sound(sound):
    """
    Normalize sound names.

    Examples:

        low_stock  -> low-stock
        gross_loss -> gross-loss
        net_loss   -> net-loss
    """

    if not sound:
        return None

    return (
        str(sound)
        .strip()
        .lower()
        .replace("_", "-")
    )


def is_sound_type(sound):
    """
    Check whether a value is a valid sound type.

    This does NOT check notification delivery.
    """

    if not sound:
        return False

    normalized = (
        str(sound)
        .strip()
        .lower()
        .replace("-", "_")
    )

    return normalized in VALID_SOUND_TYPES


def get_sound_config(sound):
    """
    Return sound configuration.
    """

    if not sound:
        return None

    normalized = (
        str(sound)
        .strip()
        .lower()
        .replace("-", "_")
    )

    return SOUND_TYPES.get(
        normalized
    )


# =========================================================
# NOTIFICATION CATEGORY HELPERS
# =========================================================

def is_notification_category(category):
    """
    Check whether a value is a valid notification-delivery
    category.
    """

    if not category:
        return False

    return (
        str(category)
        .strip()
        .lower()
        in VALID_NOTIFICATION_CATEGORIES
    )


def normalize_notification_category(category):
    """
    Normalize and validate a notification-delivery category.

    Sound-only values are rejected.
    """

    if not category:
        return None

    category = (
        str(category)
        .strip()
        .lower()
        .replace("-", "_")
    )

    if category not in VALID_NOTIFICATION_CATEGORIES:

        logger.warning(
            "BIZFLOW NOTIFICATION: "
            "invalid delivery category=%s",
            category,
        )

        return None

    return category


# =========================================================
# NOTIFICATION ASSIGNMENT HELPERS
# =========================================================

def get_company_notification_users(
    company_id,
    notification_category=None,
):
    """
    Return active company users.

    If notification_category is provided, only users
    assigned to that category are returned.

    Sound preferences are NEVER checked here.
    """

    if not company_id:
        return []

    query = (
        User.query
        .filter(
            User.company_id == company_id,
            User.is_active.is_(True),
            User.notification_enabled.is_(True),
        )
    )

    if notification_category:

        notification_category = (
            normalize_notification_category(
                notification_category
            )
        )

        if not notification_category:
            return []

        query = (
            query
            .join(
                NotificationAssignment,
                NotificationAssignment.user_id
                == User.id,
            )
            .filter(
                NotificationAssignment.company_id
                == company_id,

                NotificationAssignment.notification_category
                == notification_category,

                NotificationAssignment.enabled.is_(True),
            )
            .distinct()
        )

    return query.all()


def user_has_notification_assignment(
    user_id,
    company_id,
    notification_category,
):
    """
    Check whether a user is assigned to a delivery category.

    Sound preferences are NOT checked.
    """

    if not user_id or not company_id:
        return False

    notification_category = (
        normalize_notification_category(
            notification_category
        )
    )

    if not notification_category:
        return False

    assignment = (
        NotificationAssignment.query
        .filter(
            NotificationAssignment.company_id
            == company_id,

            NotificationAssignment.user_id
            == user_id,

            NotificationAssignment.notification_category
            == notification_category,

            NotificationAssignment.enabled.is_(True),
        )
        .first()
    )

    return assignment is not None


def get_user_notification_categories(
    user_id,
    company_id,
):
    """
    Return all enabled notification-delivery categories
    assigned to a user.
    """

    if not user_id or not company_id:
        return []

    assignments = (
        NotificationAssignment.query
        .filter(
            NotificationAssignment.company_id
            == company_id,

            NotificationAssignment.user_id
            == user_id,

            NotificationAssignment.enabled.is_(True),
        )
        .order_by(
            NotificationAssignment
            .notification_category
            .asc()
        )
        .all()
    )

    return [
        assignment.notification_category
        for assignment in assignments
        if assignment.notification_category
        in VALID_NOTIFICATION_CATEGORIES
    ]


# =========================================================
# CREATE NOTIFICATION RECIPIENTS
# =========================================================

def create_notification_recipients(
    notification,
    users=None,
):
    """
    Create NotificationRecipient records.

    NotificationAssignment is the ONLY category-level
    delivery control.

    Sound preferences are completely ignored.
    """

    if notification is None:
        return 0

    notification_category = (
        normalize_notification_category(
            notification.category
        )
    )

    if not notification_category:

        logger.error(
            "BIZFLOW NOTIFICATION: "
            "cannot create recipients because "
            "category=%s is not valid.",
            notification.category,
        )

        return 0

    # -----------------------------------------------------
    # GET USERS
    # -----------------------------------------------------

    if users is None:

        users = get_company_notification_users(
            notification.company_id,
            notification_category,
        )

    created_count = 0

    # -----------------------------------------------------
    # CREATE RECIPIENTS
    # -----------------------------------------------------

    for user in users:

        if user is None:
            continue

        # Company isolation
        if user.company_id != notification.company_id:

            logger.warning(
                "BIZFLOW NOTIFICATION: "
                "company mismatch. "
                "user=%s user_company=%s "
                "notification_company=%s",
                user.id,
                user.company_id,
                notification.company_id,
            )

            continue

        # Active user
        if not user.is_active:
            continue

        # Master in-app notification switch
        if not user.notification_enabled:
            continue

        # Category assignment
        if not user_has_notification_assignment(
            user.id,
            notification.company_id,
            notification_category,
        ):
            continue

        # Duplicate protection
        existing = (
            NotificationRecipient.query
            .filter(
                NotificationRecipient.notification_id
                == notification.id,

                NotificationRecipient.user_id
                == user.id,
            )
            .first()
        )

        if existing:
            continue

        recipient = NotificationRecipient(
            notification_id=notification.id,
            user_id=user.id,
            is_read=False,
        )

        db.session.add(recipient)

        created_count += 1

    logger.info(
        "BIZFLOW NOTIFICATION: "
        "created=%s notification=%s category=%s",
        created_count,
        notification.id,
        notification_category,
    )

    return created_count


# =========================================================
# CREATE NOTIFICATION
# =========================================================

def create_notification(
    company_id,
    title,
    message,
    category=None,
    user_id=None,
    priority=None,
    link=None,
    reference_type=None,
    reference_id=None,
    sound=None,
    send_browser=True,
    send_email=False,
    dedupe_key=None,
    commit=True,
):
    """
    Create a notification.

    CATEGORY controls DELIVERY.

    SOUND controls ONLY SOUND.

    Example:

        category="sale"
        sound="success"

    means:

        Sales assignment controls recipients.
        Success sound controls audio.
    """

    # -----------------------------------------------------
    # COMPANY
    # -----------------------------------------------------

    if not company_id:

        logger.warning(
            "BIZTRACE NOTIFICATION: "
            "notification attempted without company_id."
        )

        return None

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    category = (
        normalize_notification_category(
            category
        )
    )

    if not category:

        logger.error(
            "BIZTRACE NOTIFICATION: "
            "notification rejected because "
            "delivery category is invalid. "
            "title=%s",
            title,
        )

        return None

    config = NOTIFICATION_TYPES.get(
        category
    )

    if config is None:

        logger.error(
            "BIZTRACE NOTIFICATION: "
            "missing configuration for category=%s",
            category,
        )

        return None

    # -----------------------------------------------------
    # PRIORITY
    # -----------------------------------------------------

    if priority is None:
        priority = config["priority"]

    # -----------------------------------------------------
    # SOUND
    # -----------------------------------------------------

    if sound is not None:

        normalized_sound = normalize_sound(
            sound
        )

        if not is_sound_type(
            normalized_sound
        ):

            logger.warning(
                "BIZTRACE NOTIFICATION: "
                "unknown sound=%s. "
                "No sound attached.",
                sound,
            )

            sound = None

        else:

            sound = normalized_sound

    else:

        sound = normalize_sound(
            config.get("sound")
        )

    # -----------------------------------------------------
    # DEDUPE
    # -----------------------------------------------------

    if dedupe_key:

        existing = (
            Notification.query
            .filter(
                Notification.dedupe_key
                == dedupe_key
            )
            .first()
        )

        if existing:

            logger.info(
                "BIZTRACE NOTIFICATION: "
                "duplicate prevented. "
                "existing=%s dedupe_key=%s",
                existing.id,
                dedupe_key,
            )

            return existing

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    notification = Notification(
        company_id=company_id,

        user_id=user_id,

        title=title,

        message=message,

        category=category,

        priority=priority,

        sound=sound,

        reference_type=reference_type,

        reference_id=reference_id,

        link=link,

        dedupe_key=dedupe_key,

        is_read=False,
    )

    db.session.add(notification)

    # Get notification ID.
    db.session.flush()

    logger.info(
        "BIZTRACE NOTIFICATION: "
        "created id=%s category=%s sound=%s company=%s",
        notification.id,
        notification.category,
        notification.sound,
        company_id,
    )

    # -----------------------------------------------------
    # RECIPIENTS
    # -----------------------------------------------------

    recipient_count = (
        create_notification_recipients(
            notification
        )
    )

    logger.info(
        "BIZTRACE NOTIFICATION: "
        "notification=%s recipients=%s",
        notification.id,
        recipient_count,
    )

    # -----------------------------------------------------
    # COMMIT
    # -----------------------------------------------------

    if commit:
        db.session.commit()

    # -----------------------------------------------------
    # BROWSER PUSH
    # -----------------------------------------------------

    if (
        send_browser
        and recipient_count > 0
    ):

        try:

            send_browser_push(
                notification
            )

        except Exception:

            logger.exception(
                "BIZTRACE PUSH: "
                "failed notification=%s",
                notification.id,
            )

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    if (
        send_email
        and recipient_count > 0
    ):

        try:

            send_email_notification(
                notification
            )

        except Exception:

            logger.exception(
                "BIZTRACE EMAIL: "
                "failed notification=%s",
                notification.id,
            )

    return notification


# =========================================================
# GET ACTUAL RECIPIENT IDS
# =========================================================

def get_notification_recipient_user_ids(
    notification,
):
    """
    NotificationRecipient is the source of truth for
    actual notification recipients.
    """

    if notification is None:
        return set()

    recipients = (
        NotificationRecipient.query
        .filter(
            NotificationRecipient.notification_id
            == notification.id,
        )
        .all()
    )

    return {
        recipient.user_id
        for recipient in recipients
    }


# =========================================================
# BROWSER PUSH
# =========================================================

def send_browser_push(notification):
    """
    Send Web Push only to users who actually received
    the notification.

    Sound preferences are NOT checked here.

    The browser/client receives the sound identifier and
    decides whether the user's sound preference allows it.
    """

    logger.info(
        "================================================="
    )

    logger.info(
        "BIZTRACE PUSH: starting "
        "notification=%s "
        "company=%s "
        "category=%s "
        "sound=%s",
        notification.id,
        notification.company_id,
        notification.category,
        notification.sound,
    )

    # -----------------------------------------------------
    # IMPORT
    # -----------------------------------------------------

    try:

        from pywebpush import (
            webpush,
            WebPushException,
        )

    except ImportError:

        logger.error(
            "BIZTRACE PUSH: "
            "pywebpush is not installed."
        )

        return

    # -----------------------------------------------------
    # ACTUAL RECIPIENTS
    # -----------------------------------------------------

    recipient_user_ids = (
        get_notification_recipient_user_ids(
            notification
        )
    )

    if not recipient_user_ids:

        logger.info(
            "BIZTRACE PUSH: "
            "no recipients notification=%s",
            notification.id,
        )

        return

    # -----------------------------------------------------
    # SUBSCRIPTIONS
    # -----------------------------------------------------

    subscriptions = (
        PushSubscription.query
        .filter(
            PushSubscription.company_id
            == notification.company_id,

            PushSubscription.user_id.in_(
                recipient_user_ids
            ),
        )
        .all()
    )

    if not subscriptions:

        logger.info(
            "BIZTRACE PUSH: "
            "no browser subscriptions "
            "notification=%s",
            notification.id,
        )

        return

    # -----------------------------------------------------
    # VAPID
    # -----------------------------------------------------

    vapid_private_key = (
        current_app.config.get(
            "VAPID_PRIVATE_KEY"
        )
    )

    vapid_subject = (
        current_app.config.get(
            "VAPID_SUBJECT"
        )
    )

    if not vapid_private_key:

        logger.error(
            "BIZTRACE PUSH: "
            "VAPID_PRIVATE_KEY is missing."
        )

        return

    if not vapid_subject:

        logger.error(
            "BIZTRACE PUSH: "
            "VAPID_SUBJECT is missing."
        )

        return

    # -----------------------------------------------------
    # PAYLOAD
    # -----------------------------------------------------

    payload = {
        "id": notification.id,

        "title": notification.title,

        "message": notification.message,

        # DELIVERY CATEGORY
        "category": notification.category,

        "priority": notification.priority,

        # SOUND ONLY
        "sound": normalize_sound(
            notification.sound
        ),

        # Backward compatibility
        "sound_type": normalize_sound(
            notification.sound
        ),

        "link": notification.link,

        "details_url": (
            f"/notifications/"
            f"{notification.id}"
        ),

        "created_at": (
            normalize_utc_datetime(
                notification.created_at
            ).isoformat()
            if notification.created_at
            else None
        ),
    }

    logger.info(
        "BIZTRACE PUSH PAYLOAD: %s",
        payload,
    )

    # -----------------------------------------------------
    # SEND
    # -----------------------------------------------------

    successful_sends = 0
    failed_sends = 0

    for subscription in subscriptions:

        subscription_info = {
            "endpoint": subscription.endpoint,

            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:

            webpush(
                subscription_info,

                json.dumps(
                    payload
                ),

                vapid_private_key=
                    vapid_private_key,

                vapid_claims={
                    "sub":
                        vapid_subject
                },
            )

            successful_sends += 1

            subscription.updated_at = (
                utc_now()
            )

        except WebPushException as exc:

            failed_sends += 1

            response = getattr(
                exc,
                "response",
                None,
            )

            status_code = getattr(
                response,
                "status_code",
                None,
            )

            logger.error(
                "BIZTRACE PUSH: "
                "WebPushException "
                "subscription=%s "
                "user=%s "
                "status=%s "
                "error=%s",
                subscription.id,
                subscription.user_id,
                status_code,
                exc,
            )

            if status_code in {
                404,
                410,
            }:

                db.session.delete(
                    subscription
                )

        except Exception as exc:

            failed_sends += 1

            logger.exception(
                "BIZTRACE PUSH: "
                "unexpected error "
                "subscription=%s "
                "user=%s: %s",
                subscription.id,
                subscription.user_id,
                exc,
            )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if successful_sends > 0:

        notification.browser_sent = True

    db.session.commit()

    logger.info(
        "BIZTRACE PUSH: completed "
        "notification=%s "
        "successful=%s "
        "failed=%s",
        notification.id,
        successful_sends,
        failed_sends,
    )

    logger.info(
        "================================================="
    )


# =========================================================
# EMAIL
# =========================================================

def send_email_notification(
    notification,
):
    """
    Send email only to users with NotificationRecipient.

    Therefore email follows notification assignment.

    Sound preferences have no effect on email.
    """

    try:

        from flask_mail import Message
        from app.extensions import mail

    except ImportError:

        logger.warning(
            "Flask-Mail is not installed."
        )

        return

    # -----------------------------------------------------
    # ACTUAL RECIPIENTS
    # -----------------------------------------------------

    users = (
        User.query
        .join(
            NotificationRecipient,
            NotificationRecipient.user_id
            == User.id,
        )
        .filter(
            NotificationRecipient.notification_id
            == notification.id,

            User.company_id
            == notification.company_id,

            User.is_active.is_(True),

            User.email.isnot(None),
        )
        .distinct()
        .all()
    )

    sent_count = 0

    # -----------------------------------------------------
    # SEND
    # -----------------------------------------------------

    for user in users:

        if not user.email_notification_enabled:
            continue

        message = Message(
            subject=notification.title,

            recipients=[
                user.email
            ],
        )

        message.body = (
            f"{notification.title}\n\n"
            f"{notification.message}\n\n"
            f"BizTrace IMS"
        )

        message.html = f"""
        <div style="
            font-family:Arial,sans-serif;
            max-width:600px;
            margin:auto;
            padding:30px;
        ">

            <h2>
                {notification.title}
            </h2>

            <p>
                {notification.message}
            </p>

            <p>
                <a href="{notification.link or '#'}">
                    Open BizTrace IMS
                </a>
            </p>

        </div>
        """

        try:

            mail.send(
                message
            )

            sent_count += 1

        except Exception:

            logger.exception(
                "Unable to send notification "
                "email to %s",
                user.email,
            )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if sent_count > 0:

        notification.email_sent = True

    db.session.commit()

    logger.info(
        "BIZTRACE EMAIL: "
        "notification=%s sent=%s",
        notification.id,
        sent_count,
    )


# =========================================================
# SUCCESS
# =========================================================

def notify_success(
    company_id,
    title,
    message,
    notification_category,
    user_id=None,
    link=None,
    reference_type=None,
    reference_id=None,
):
    """
    Create a notification with SUCCESS sound.

    Delivery:
        notification_category

    Sound:
        success

    Example:

        category = sale
        sound    = success
    """

    return create_notification(
        company_id=company_id,

        user_id=user_id,

        title=title,

        message=message,

        category=notification_category,

        priority="normal",

        sound="success",

        link=link,

        reference_type=reference_type,

        reference_id=reference_id,

        send_browser=True,

        send_email=False,
    )


# =========================================================
# ERROR
# =========================================================

def notify_error(
    company_id,
    title,
    message,
    notification_category,
    user_id=None,
    link=None,
    reference_type=None,
    reference_id=None,
):
    """
    Create a notification with ERROR sound.

    Delivery:
        notification_category

    Sound:
        error
    """

    return create_notification(
        company_id=company_id,

        user_id=user_id,

        title=title,

        message=message,

        category=notification_category,

        priority="high",

        sound="error",

        link=link,

        reference_type=reference_type,

        reference_id=reference_id,

        send_browser=True,

        send_email=True,
    )


# =========================================================
# LOW STOCK
# =========================================================

def notify_low_stock(
    product,
    user_id=None,
):
    """
    Create a low-stock notification.

    DELIVERY CATEGORY:
        inventory

    SOUND:
        low-stock

    Therefore:

        Inventory assignment controls delivery.

        Low Stock sound preference controls audio.

    Sound preferences do NOT create recipients.
    """

    if not product:

        logger.warning(
            "BIZTRACE LOW STOCK: "
            "notify_low_stock called without product."
        )

        return None

    company_id = product.company_id

    # -----------------------------------------------------
    # STOCK
    # -----------------------------------------------------

    quantity = Decimal(
        str(
            product.quantity or 0
        )
    )

    minimum_stock = Decimal(
        str(
            product.minimum_stock or 0
        )
    )

    # -----------------------------------------------------
    # LOW STOCK CHECK
    # -----------------------------------------------------

    if quantity > minimum_stock:
        return None

    # -----------------------------------------------------
    # COMPANY DAY
    # -----------------------------------------------------

    company_today = (
        company_now().date()
    )

    today_start, tomorrow_start = (
        company_day_boundaries(
            company_today
        )
    )

    # -----------------------------------------------------
    # DAILY DUPLICATE
    # -----------------------------------------------------

    existing = (
        Notification.query
        .filter(
            Notification.company_id
            == company_id,

            Notification.category
            == "inventory",

            Notification.reference_type
            == "Product",

            Notification.reference_id
            == product.id,

            Notification.created_at
            >= today_start,

            Notification.created_at
            < tomorrow_start,
        )
        .order_by(
            Notification.created_at.desc()
        )
        .first()
    )

    if existing:
        return existing

    # -----------------------------------------------------
    # LINK
    # -----------------------------------------------------

    try:

        link = url_for(
            "products.view_product",
            product_id=product.id,
        )

    except Exception:

        link = None

        logger.exception(
            "BIZTRACE LOW STOCK: "
            "unable to create product URL."
        )

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    notification = create_notification(
        company_id=company_id,

        user_id=user_id,

        title="Low Stock Warning",

        message=(
            f"{product.name} is low on stock. "
            f"Current quantity: "
            f"{quantity:g}. "
            f"Minimum stock: "
            f"{minimum_stock:g}."
        ),

        # DELIVERY CATEGORY
        category="inventory",

        priority="high",

        # SOUND ONLY
        sound="low-stock",

        reference_type="Product",

        reference_id=product.id,

        link=link,

        send_browser=True,

        send_email=True,
    )

    if notification:

        logger.warning(
            "BIZTRACE LOW STOCK: "
            "created notification=%s "
            "category=inventory "
            "sound=low-stock",
            notification.id,
        )

    return notification


# =========================================================
# FINANCIAL ALERTS
# =========================================================

def check_financial_alerts(
    company_id,
    start_datetime,
    end_datetime,
    user_id=None,
):
    """
    Calculate:

        Sales
        COGS
        Expenses
        Gross Profit
        Net Profit

    Creates financial notifications when losses occur.

    DELIVERY CATEGORY:
        financial

    SOUNDS:
        gross-loss
        net-loss
    """

    from sqlalchemy import func

    # -----------------------------------------------------
    # NORMALIZE
    # -----------------------------------------------------

    start_datetime = (
        normalize_utc_datetime(
            start_datetime
        )
    )

    end_datetime = (
        normalize_utc_datetime(
            end_datetime
        )
    )

    # -----------------------------------------------------
    # VALIDATE
    # -----------------------------------------------------

    if (
        start_datetime is None
        or end_datetime is None
        or end_datetime <= start_datetime
    ):

        logger.error(
            "BIZTRACE FINANCIAL ALERT: "
            "invalid financial period."
        )

        return {
            "sales": Decimal("0"),
            "cogs": Decimal("0"),
            "expenses": Decimal("0"),
            "gross_profit": Decimal("0"),
            "net_profit": Decimal("0"),
        }

    # -----------------------------------------------------
    # SALES
    # -----------------------------------------------------

    sales = (
        db.session.query(
            func.coalesce(
                func.sum(
                    Sale.total
                ),
                0,
            )
        )
        .filter(
            Sale.company_id
            == company_id,

            Sale.sale_date
            >= start_datetime,

            Sale.sale_date
            < end_datetime,
        )
        .scalar()
        or 0
    )

    # -----------------------------------------------------
    # COGS
    # -----------------------------------------------------

    cogs = (
        db.session.query(
            func.coalesce(
                func.sum(
                    SaleItem.quantity
                    * Product.purchase_price
                ),
                0,
            )
        )
        .join(
            Sale,
            Sale.id
            == SaleItem.sale_id,
        )
        .join(
            Product,
            Product.id
            == SaleItem.product_id,
        )
        .filter(
            Sale.company_id
            == company_id,

            Sale.sale_date
            >= start_datetime,

            Sale.sale_date
            < end_datetime,
        )
        .scalar()
        or 0
    )

    # -----------------------------------------------------
    # EXPENSES
    # -----------------------------------------------------

    expenses = (
        db.session.query(
            func.coalesce(
                func.sum(
                    Expense.amount
                ),
                0,
            )
        )
        .filter(
            Expense.company_id
            == company_id,

            Expense.expense_date
            >= start_datetime,

            Expense.expense_date
            < end_datetime,
        )
        .scalar()
        or 0
    )

    # -----------------------------------------------------
    # DECIMAL
    # -----------------------------------------------------

    sales = Decimal(
        str(sales)
    )

    cogs = Decimal(
        str(cogs)
    )

    expenses = Decimal(
        str(expenses)
    )

    # -----------------------------------------------------
    # CALCULATIONS
    # -----------------------------------------------------

    gross_profit = (
        sales - cogs
    )

    net_profit = (
        gross_profit - expenses
    )

    # -----------------------------------------------------
    # GROSS LOSS
    # -----------------------------------------------------

    if gross_profit < 0:

        create_loss_notification(
            company_id=company_id,

            user_id=user_id,

            loss_type="gross_loss",

            title="Gross Loss Detected",

            amount=abs(
                gross_profit
            ),

            start_datetime=start_datetime,

            end_datetime=end_datetime,
        )

    # -----------------------------------------------------
    # NET LOSS
    # -----------------------------------------------------

    if net_profit < 0:

        create_loss_notification(
            company_id=company_id,

            user_id=user_id,

            loss_type="net_loss",

            title="Net Loss Detected",

            amount=abs(
                net_profit
            ),

            start_datetime=start_datetime,

            end_datetime=end_datetime,
        )

    return {
        "sales": sales,
        "cogs": cogs,
        "expenses": expenses,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
    }


# =========================================================
# LOSS NOTIFICATION
# =========================================================

def create_loss_notification(
    company_id,
    user_id,
    loss_type,
    title,
    amount,
    start_datetime,
    end_datetime,
):
    """
    Create a financial loss notification.

    DELIVERY CATEGORY:
        financial

    SOUND:
        gross-loss OR net-loss

    IMPORTANT:

    Notification.reference_id is an INTEGER.

    Therefore the financial period is stored in dedupe_key
    instead of incorrectly placing a string into reference_id.
    """

    # -----------------------------------------------------
    # NORMALIZE DATES
    # -----------------------------------------------------

    start_datetime = (
        normalize_utc_datetime(
            start_datetime
        )
    )

    end_datetime = (
        normalize_utc_datetime(
            end_datetime
        )
    )

    # -----------------------------------------------------
    # COMPANY PERIOD
    # -----------------------------------------------------

    company_start = (
        to_company_datetime(
            start_datetime
        )
    )

    company_end = (
        to_company_datetime(
            end_datetime
        )
    )

    if (
        company_start is None
        or company_end is None
    ):
        return None

    start_date = (
        company_start.date()
    )

    end_date = (
        company_end
        - timedelta(
            microseconds=1
        )
    ).date()

    period_key = (
        f"{start_date}"
        f"_"
        f"{end_date}"
    )

    # -----------------------------------------------------
    # LOSS TYPE
    # -----------------------------------------------------

    loss_type = (
        str(loss_type)
        .strip()
        .lower()
        .replace("-", "_")
    )

    if loss_type not in {
        "gross_loss",
        "net_loss",
    }:

        logger.error(
            "BIZTRACE FINANCIAL ALERT: "
            "invalid loss type=%s",
            loss_type,
        )

        return None

    # -----------------------------------------------------
    # SOUND
    # -----------------------------------------------------

    if loss_type == "gross_loss":

        sound = "gross-loss"

    else:

        sound = "net-loss"

    # -----------------------------------------------------
    # DEDUPE KEY
    # -----------------------------------------------------
    #
    # Notification.dedupe_key is String(255).
    #
    # This is the correct place to store the unique
    # financial-period identifier.
    # -----------------------------------------------------

    dedupe_key = (
        f"financial:"
        f"{company_id}:"
        f"{loss_type}:"
        f"{start_datetime.isoformat()}:"
        f"{end_datetime.isoformat()}"
    )

    # -----------------------------------------------------
    # MESSAGE
    # -----------------------------------------------------

    formatted_amount = (
        format_currency(
            amount
        )
    )

    if loss_type == "gross_loss":

        message = (
            f"Gross loss of "
            f"{formatted_amount} "
            f"was detected for "
            f"{period_key}."
        )

    else:

        message = (
            f"Net loss of "
            f"{formatted_amount} "
            f"was detected for "
            f"{period_key}."
        )

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------
    #
    # DELIVERY:
    #
    #     financial
    #
    # SOUND:
    #
    #     gross-loss / net-loss
    # -----------------------------------------------------

    notification = create_notification(
        company_id=company_id,

        user_id=user_id,

        title=title,

        message=message,

        category="financial",

        priority="critical",

        sound=sound,

        reference_type="FinancialPeriod",

        # reference_id MUST remain an integer.
        # No specific database object is being referenced.
        reference_id=None,

        link=None,

        dedupe_key=dedupe_key,

        send_browser=True,

        send_email=True,
    )

    if notification:

        logger.warning(
            "BIZTRACE FINANCIAL ALERT: "
            "created notification=%s "
            "category=financial "
            "sound=%s "
            "period=%s",
            notification.id,
            sound,
            period_key,
        )

    return notification