from datetime import datetime, timezone

from flask import (
    render_template,
    jsonify,
    request,
    url_for,
    current_app,
)
from flask_login import login_required, current_user

from app.extensions import db, csrf
from app.models import (
    Notification,
    NotificationRecipient,
    PushSubscription,
)
from app.utils.company_settings import (
    get_company_timezone,
)

from app.notifications.service import (
    normalize_sound,
    get_user_notification_categories,
)

from . import notifications_bp


# ============================================================
# HELPERS
# ============================================================

def visible_notifications_query():
    """
    Return notifications visible to the current user.

    NotificationRecipient is the source of truth for
    notification delivery and read/unread state.

    A user can only see notifications for their own company
    for which a NotificationRecipient row exists.
    """

    if not current_user.company_id:
        return Notification.query.filter(False)

    return (
        Notification.query
        .join(
            NotificationRecipient,
            NotificationRecipient.notification_id
            == Notification.id
        )
        .filter(
            Notification.company_id
            == current_user.company_id,

            NotificationRecipient.user_id
            == current_user.id
        )
    )


def normalize_utc_datetime(value):
    """
    Normalize a datetime value to timezone-aware UTC.

    Naive database timestamps are treated as UTC.
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
    Convert a UTC datetime into the current company's
    configured timezone.

    Database timestamps remain UTC.
    Conversion is only for presentation/API output.
    """

    value = normalize_utc_datetime(
        value
    )

    if value is None:
        return None

    return value.astimezone(
        get_company_timezone()
    )


def is_sound_enabled_for_current_user(sound):
    """
    Determine whether the current user has enabled the
    sound associated with a notification.

    IMPORTANT:

    This function controls SOUND ONLY.

    It does NOT control:

        - notification delivery
        - NotificationAssignment
        - NotificationRecipient
        - browser push delivery
        - email delivery
    """

    if not sound:
        return False

    if not getattr(
        current_user,
        "sound_notification_enabled",
        True,
    ):
        return False

    sound_key = (
        str(sound)
        .strip()
        .lower()
        .replace("-", "_")
    )

    sound_preferences = {
        "success": getattr(
            current_user,
            "success_sound_enabled",
            True,
        ),

        "system": getattr(
            current_user,
            "system_sound_enabled",
            True,
        ),

        "error": getattr(
            current_user,
            "error_sound_enabled",
            True,
        ),

        "low_stock": getattr(
            current_user,
            "low_stock_sound_enabled",
            True,
        ),

        "gross_loss": getattr(
            current_user,
            "gross_loss_sound_enabled",
            True,
        ),

        "net_loss": getattr(
            current_user,
            "net_loss_sound_enabled",
            True,
        ),
    }

    return bool(
        sound_preferences.get(
            sound_key,
            False,
        )
    )


# ============================================================
# GET NOTIFICATION
# ============================================================

def get_notification_or_404(notification_id):
    """
    Return a notification only if the current user is
    one of its actual recipients.
    """

    return (
        visible_notifications_query()
        .filter(
            Notification.id == notification_id
        )
        .first_or_404()
    )


# ============================================================
# GET RECIPIENT
# ============================================================

def get_notification_recipient(notification_id):
    """
    Return the current user's recipient record for a
    notification.
    """

    return (
        NotificationRecipient.query
        .filter(
            NotificationRecipient.notification_id
            == notification_id,

            NotificationRecipient.user_id
            == current_user.id
        )
        .first()
    )


# ============================================================
# SERIALIZE NOTIFICATION
# ============================================================

def serialize_notification(notification):
    """
    Convert a Notification model into JSON-safe data.

    IMPORTANT:

    notification.category
        = DELIVERY CATEGORY

    notification.sound
        = SOUND TYPE

    They are intentionally independent.

    Read/unread state belongs to NotificationRecipient.
    """

    created_at = to_company_datetime(
        notification.created_at
    )

    # --------------------------------------------------------
    # RECIPIENT
    # --------------------------------------------------------

    recipient = get_notification_recipient(
        notification.id
    )

    is_read = (
        bool(recipient.is_read)
        if recipient
        else False
    )

    # --------------------------------------------------------
    # READ AT
    # --------------------------------------------------------

    read_at = None

    if recipient and recipient.read_at:
        read_at = to_company_datetime(
            recipient.read_at
        )

    # --------------------------------------------------------
    # SOURCE LINK
    # --------------------------------------------------------

    source_link = notification.link

    if source_link in (
        "",
        "#",
    ):
        source_link = None

    # --------------------------------------------------------
    # DELIVERY CATEGORY
    # --------------------------------------------------------
    #
    # This is controlled by NotificationAssignment.
    #
    # Examples:
    #
    #     sale
    #     payment
    #     purchase
    #     inventory
    #     expense
    #     cash_deposit
    #     receivable
    #     payable
    #     financial
    #     security
    #
    # IMPORTANT:
    #
    # This is NOT a sound category.
    # --------------------------------------------------------

    category = (
        notification.category
        or "system"
    )

    category = (
        str(category)
        .strip()
        .lower()
    )

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    priority = (
        notification.priority
        or "normal"
    )

    priority = (
        str(priority)
        .strip()
        .lower()
    )

    # --------------------------------------------------------
    # SOUND
    # --------------------------------------------------------
    #
    # Sound is completely independent from delivery category.
    #
    # Examples:
    #
    #     sale      + success
    #     sale      + error
    #     inventory + low-stock
    #     financial + gross-loss
    #     financial + net-loss
    #     system    + system
    #
    # Sound preferences do NOT determine whether the
    # notification exists for the user.
    # --------------------------------------------------------

    sound = normalize_sound(
        notification.sound
    )

    sound_enabled = (
        is_sound_enabled_for_current_user(
            sound
        )
    )

    # --------------------------------------------------------
    # DETAILS URL
    # --------------------------------------------------------

    details_url = url_for(
        "notifications.detail",
        notification_id=notification.id,
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "id":
            notification.id,

        "title":
            notification.title
            or "BizTrace IMS",

        "message":
            notification.message
            or "You have a new notification.",

        # ----------------------------------------------------
        # DELIVERY CATEGORY
        # ----------------------------------------------------

        "category":
            category,

        # ----------------------------------------------------
        # PRIORITY
        # ----------------------------------------------------

        "priority":
            priority,

        # ----------------------------------------------------
        # SOUND ONLY
        # ----------------------------------------------------

        "sound":
            sound,

        "sound_enabled":
            sound_enabled,

        # ----------------------------------------------------
        # READ STATE
        # ----------------------------------------------------

        "is_read":
            is_read,

        "read_at": (
            read_at.isoformat()
            if read_at
            else None
        ),

        # ----------------------------------------------------
        # DELIVERY STATUS
        # ----------------------------------------------------

        "browser_sent":
            bool(
                notification.browser_sent
            ),

        "email_sent":
            bool(
                notification.email_sent
            ),

        # ----------------------------------------------------
        # REFERENCE
        # ----------------------------------------------------

        "reference_type":
            notification.reference_type,

        "reference_id":
            notification.reference_id,

        # ----------------------------------------------------
        # LINKS
        # ----------------------------------------------------

        "source_link":
            source_link,

        "details_url":
            details_url,

        # ----------------------------------------------------
        # CREATED AT
        # ----------------------------------------------------

        "created_at": (
            created_at.isoformat()
            if created_at
            else None
        ),
    }


# ============================================================
# UNREAD COUNT
# ============================================================

def get_unread_count():
    """
    Return unread notification count for the current user.

    NotificationRecipient is the source of truth.
    """

    if not current_user.company_id:
        return 0

    return (
        NotificationRecipient.query
        .join(
            Notification,
            Notification.id
            == NotificationRecipient.notification_id
        )
        .filter(
            Notification.company_id
            == current_user.company_id,

            NotificationRecipient.user_id
            == current_user.id,

            NotificationRecipient.is_read.is_(False)
        )
        .count()
    )


# ============================================================
# NOTIFICATION PAGE
# ============================================================

@notifications_bp.route("/")
@login_required
def index():

    filter_type = request.args.get(
        "filter",
        "all"
    ).lower()

    # --------------------------------------------------------
    # VALID FILTER
    # --------------------------------------------------------

    if filter_type not in {
        "all",
        "unread",
        "read",
    }:

        filter_type = "all"

    # --------------------------------------------------------
    # BASE QUERY
    # --------------------------------------------------------

    query = (
        NotificationRecipient.query
        .join(
            Notification,
            Notification.id
            == NotificationRecipient.notification_id
        )
        .filter(
            Notification.company_id
            == current_user.company_id,

            NotificationRecipient.user_id
            == current_user.id
        )
    )

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    total_count = query.count()

    # --------------------------------------------------------
    # UNREAD
    # --------------------------------------------------------

    unread_count = (
        query
        .filter(
            NotificationRecipient.is_read.is_(False)
        )
        .count()
    )

    # --------------------------------------------------------
    # IMPORTANT UNREAD
    # --------------------------------------------------------

    important_count = (
        query
        .filter(
            NotificationRecipient.is_read.is_(False),

            Notification.priority.in_(
                [
                    "high",
                    "critical",
                ]
            )
        )
        .count()
    )

    # --------------------------------------------------------
    # APPLY FILTER
    # --------------------------------------------------------

    if filter_type == "unread":

        query = query.filter(
            NotificationRecipient.is_read.is_(False)
        )

    elif filter_type == "read":

        query = query.filter(
            NotificationRecipient.is_read.is_(True)
        )

    # --------------------------------------------------------
    # PAGINATION
    # --------------------------------------------------------

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1

    pagination = (
        query
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc()
        )
        .paginate(
            page=page,
            per_page=20,
            error_out=False,
        )
    )

    # --------------------------------------------------------
    # RENDER
    # --------------------------------------------------------

    return render_template(
        "notifications/index.html",

        recipients=
            pagination.items,

        pagination=
            pagination,

        filter_type=
            filter_type,

        total_count=
            total_count,

        unread_count=
            unread_count,

        important_count=
            important_count,
    )


# ============================================================
# NOTIFICATION DETAILS
# ============================================================

@notifications_bp.route(
    "/<int:notification_id>"
)
@login_required
def detail(notification_id):

    notification = get_notification_or_404(
        notification_id
    )

    # --------------------------------------------------------
    # GET CURRENT USER'S RECIPIENT
    # --------------------------------------------------------

    recipient = get_notification_recipient(
        notification.id
    )

    # --------------------------------------------------------
    # MARK CURRENT USER'S COPY AS READ
    # --------------------------------------------------------

    if (
        recipient
        and not recipient.is_read
    ):

        recipient.is_read = True

        # Database storage remains UTC.
        recipient.read_at = (
            datetime.now(timezone.utc)
        )

        db.session.commit()

    # --------------------------------------------------------
    # RENDER
    # --------------------------------------------------------

    return render_template(
        "notifications/detail.html",

        notification=
            notification,

        recipient=
            recipient,
    )


# ============================================================
# RECENT NOTIFICATIONS API
# ============================================================

@notifications_bp.route(
    "/api/recent"
)
@login_required
def recent():

    notifications = (
        visible_notifications_query()
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc()
        )
        .limit(20)
        .all()
    )

    # ========================================================
    # SOUND PREFERENCES
    # ========================================================
    #
    # These ONLY control sound.
    #
    # They do NOT control:
    #
    #     NotificationAssignment
    #     NotificationRecipient
    #     notification delivery
    #     browser push delivery
    #     email delivery
    # ========================================================

    sound_preferences = {

        # Master sound switch
        "enabled": bool(
            getattr(
                current_user,
                "sound_notification_enabled",
                True,
            )
        ),

        # Success sound
        "success": bool(
            getattr(
                current_user,
                "success_sound_enabled",
                True,
            )
        ),

        # System sound
        "system": bool(
            getattr(
                current_user,
                "system_sound_enabled",
                True,
            )
        ),

        # Error sound
        "error": bool(
            getattr(
                current_user,
                "error_sound_enabled",
                True,
            )
        ),

        # Low-stock sound
        "low_stock": bool(
            getattr(
                current_user,
                "low_stock_sound_enabled",
                True,
            )
        ),

        # Gross-loss sound
        "gross_loss": bool(
            getattr(
                current_user,
                "gross_loss_sound_enabled",
                True,
            )
        ),

        # Net-loss sound
        "net_loss": bool(
            getattr(
                current_user,
                "net_loss_sound_enabled",
                True,
            )
        ),
    }

    # ========================================================
    # NOTIFICATION ASSIGNMENTS
    # ========================================================
    #
    # These are DELIVERY categories.
    #
    # They are completely separate from sound preferences.
    #
    # Example:
    #
    #     notification_categories = ["sale", "inventory"]
    #
    # means the user is assigned Sales and Inventory
    # notifications.
    #
    # It does NOT mean that success/low-stock sounds are
    # enabled or disabled.
    # ========================================================

    notification_categories = (
        get_user_notification_categories(
            current_user.id,
            current_user.company_id,
        )
        if current_user.company_id
        else []
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return jsonify(
        {
            "success": True,

            "notifications": [
                serialize_notification(
                    notification
                )
                for notification in notifications
            ],

            "unread_count":
                get_unread_count(),

            # SOUND SETTINGS ONLY
            "sound_preferences":
                sound_preferences,

            # DELIVERY CATEGORIES ONLY
            "notification_categories":
                notification_categories,

            # TRANSPORT SETTINGS
            "browser_notification_enabled":
                bool(
                    getattr(
                        current_user,
                        "browser_notification_enabled",
                        True,
                    )
                ),

            "email_notification_enabled":
                bool(
                    getattr(
                        current_user,
                        "email_notification_enabled",
                        True,
                    )
                ),
        }
    )


# ============================================================
# MARK ONE NOTIFICATION AS READ
# ============================================================

@notifications_bp.route(
    "/<int:notification_id>/read",
    methods=["POST"],
)
@login_required
@csrf.exempt
def mark_read(notification_id):

    notification = get_notification_or_404(
        notification_id
    )

    recipient = get_notification_recipient(
        notification.id
    )

    if (
        recipient
        and not recipient.is_read
    ):

        recipient.is_read = True

        recipient.read_at = (
            datetime.now(timezone.utc)
        )

        db.session.commit()

    return jsonify(
        {
            "success": True,

            "notification_id":
                notification.id,

            "is_read":
                True,

            "unread_count":
                get_unread_count(),
        }
    )


# ============================================================
# MARK ALL AS READ
# ============================================================

@notifications_bp.route(
    "/mark-all-read",
    methods=["POST"],
)
@login_required
@csrf.exempt
def mark_all_read():

    if not current_user.company_id:
        return jsonify(
            {
                "success": True,
                "unread_count": 0,
                "count": 0,
            }
        )

    # --------------------------------------------------------
    # ONLY CURRENT USER'S RECIPIENT ROWS
    # --------------------------------------------------------

    recipients = (
        NotificationRecipient.query
        .join(
            Notification,
            Notification.id
            == NotificationRecipient.notification_id
        )
        .filter(
            Notification.company_id
            == current_user.company_id,

            NotificationRecipient.user_id
            == current_user.id,

            NotificationRecipient.is_read.is_(False)
        )
        .all()
    )

    # --------------------------------------------------------
    # CURRENT UTC TIME
    # --------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # MARK READ
    # --------------------------------------------------------

    for recipient in recipients:

        recipient.is_read = True
        recipient.read_at = now

    # --------------------------------------------------------
    # COMMIT
    # --------------------------------------------------------

    db.session.commit()

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify(
        {
            "success": True,

            "unread_count":
                0,

            "count":
                len(recipients),
        }
    )


# ============================================================
# DELETE ONE NOTIFICATION
# ============================================================

@notifications_bp.route(
    "/api/<int:notification_id>/delete",
    methods=["POST"]
)
@login_required
@csrf.exempt
def delete_notification(notification_id):

    # --------------------------------------------------------
    # FIND CURRENT USER'S RECIPIENT ROW
    # --------------------------------------------------------

    recipient = (
        NotificationRecipient.query
        .join(
            Notification,
            Notification.id
            == NotificationRecipient.notification_id
        )
        .filter(
            NotificationRecipient.notification_id
            == notification_id,

            NotificationRecipient.user_id
            == current_user.id,

            Notification.company_id
            == current_user.company_id,
        )
        .first()
    )

    # --------------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------------

    if not recipient:

        return jsonify(
            {
                "success": False,

                "message":
                    "Notification not found.",
            }
        ), 404

    # --------------------------------------------------------
    # DELETE ONLY THIS USER'S COPY
    # --------------------------------------------------------

    try:

        db.session.delete(
            recipient
        )

        db.session.commit()

        return jsonify(
            {
                "success": True,

                "message":
                    "Notification deleted successfully.",

                "notification_id":
                    notification_id,

                "unread_count":
                    get_unread_count(),
            }
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete notification %s "
            "for user %s",
            notification_id,
            current_user.id,
        )

        return jsonify(
            {
                "success": False,

                "message":
                    "Unable to delete notification.",
            }
        ), 500


# ============================================================
# DELETE ALL NOTIFICATIONS
# ============================================================

@notifications_bp.route(
    "/api/delete-all",
    methods=["POST"]
)
@login_required
@csrf.exempt
def delete_all_notifications():

    if not current_user.company_id:
        return jsonify(
            {
                "success": True,
                "message":
                    "All notifications deleted successfully.",
                "count": 0,
                "unread_count": 0,
            }
        )

    # --------------------------------------------------------
    # FIND CURRENT USER'S RECIPIENT ROWS
    # --------------------------------------------------------

    recipients = (
        NotificationRecipient.query
        .join(
            Notification,
            Notification.id
            == NotificationRecipient.notification_id
        )
        .filter(
            Notification.company_id
            == current_user.company_id,

            NotificationRecipient.user_id
            == current_user.id,
        )
        .all()
    )

    # --------------------------------------------------------
    # DELETE ONLY CURRENT USER'S COPIES
    # --------------------------------------------------------

    try:

        count = len(
            recipients
        )

        for recipient in recipients:

            db.session.delete(
                recipient
            )

        db.session.commit()

        return jsonify(
            {
                "success": True,

                "message":
                    "All notifications deleted successfully.",

                "count":
                    count,

                "unread_count":
                    0,
            }
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete all notifications "
            "for user %s",
            current_user.id,
        )

        return jsonify(
            {
                "success": False,

                "message":
                    "Unable to delete notifications.",
            }
        ), 500


# ============================================================
# PUSH SUBSCRIPTION
# ============================================================

@notifications_bp.route(
    "/api/push/subscribe",
    methods=["POST"],
)
@login_required
@csrf.exempt
def subscribe_push():

    # --------------------------------------------------------
    # COMPANY REQUIRED
    # --------------------------------------------------------

    if not current_user.company_id:

        return jsonify(
            {
                "success": False,

                "message":
                    "A company account is required.",
            }
        ), 400

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    # --------------------------------------------------------
    # GET SUBSCRIPTION DATA
    # --------------------------------------------------------

    endpoint = data.get(
        "endpoint"
    )

    keys = (
        data.get("keys")
        or {}
    )

    p256dh = keys.get(
        "p256dh"
    )

    auth = keys.get(
        "auth"
    )

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    if (
        not endpoint
        or not p256dh
        or not auth
    ):

        return jsonify(
            {
                "success": False,

                "message":
                    "Invalid push subscription data.",
            }
        ), 400

    # --------------------------------------------------------
    # FIND EXISTING SUBSCRIPTION
    # --------------------------------------------------------

    subscription = (
        PushSubscription.query
        .filter_by(
            endpoint=endpoint
        )
        .first()
    )

    # --------------------------------------------------------
    # UPDATE EXISTING
    # --------------------------------------------------------

    if subscription:

        subscription.company_id = (
            current_user.company_id
        )

        subscription.user_id = (
            current_user.id
        )

        subscription.p256dh = (
            p256dh
        )

        subscription.auth = (
            auth
        )

        subscription.user_agent = (
            request.headers.get(
                "User-Agent"
            )
        )

        if hasattr(
            subscription,
            "updated_at"
        ):

            subscription.updated_at = (
                datetime.now(timezone.utc)
            )

    # --------------------------------------------------------
    # CREATE NEW
    # --------------------------------------------------------

    else:

        subscription = PushSubscription(

            company_id=
                current_user.company_id,

            user_id=
                current_user.id,

            endpoint=
                endpoint,

            p256dh=
                p256dh,

            auth=
                auth,

            user_agent=
                request.headers.get(
                    "User-Agent"
                ),
        )

        db.session.add(
            subscription
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Failed to save push subscription "
            "for user %s",
            current_user.id,
        )

        return jsonify(
            {
                "success": False,

                "message":
                    "Unable to enable browser notifications.",
            }
        ), 500

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify(
        {
            "success": True,

            "message":
                "Browser notifications enabled.",
        }
    )


# ============================================================
# REMOVE PUSH SUBSCRIPTION
# ============================================================

@notifications_bp.route(
    "/api/push/unsubscribe",
    methods=["POST"],
)
@login_required
@csrf.exempt
def unsubscribe_push():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    endpoint = data.get(
        "endpoint"
    )

    # --------------------------------------------------------
    # REMOVE CURRENT USER'S SUBSCRIPTION
    # --------------------------------------------------------

    if endpoint:

        (
            PushSubscription.query
            .filter_by(
                endpoint=endpoint,
                user_id=current_user.id,
            )
            .delete(
                synchronize_session=False
            )
        )

        db.session.commit()

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify(
        {
            "success": True,
        }
    )


# ============================================================
# VAPID PUBLIC KEY
# ============================================================

@notifications_bp.route(
    "/api/push/public-key"
)
@login_required
def push_public_key():

    public_key = (
        current_app.config.get(
            "VAPID_PUBLIC_KEY"
        )
    )

    # --------------------------------------------------------
    # CHECK CONFIGURATION
    # --------------------------------------------------------

    if not public_key:

        return jsonify(
            {
                "success": False,

                "message":
                    "VAPID public key is not configured.",
            }
        ), 503

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify(
        {
            "success": True,

            "public_key":
                public_key,
        }
    )