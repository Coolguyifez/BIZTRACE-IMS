from datetime import datetime, date, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask_login import current_user

from app.models import CompanySetting


# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_CURRENCY_CODE = "NGN"
DEFAULT_CURRENCY_SYMBOL = "₦"
DEFAULT_DECIMAL_PLACES = 2
DEFAULT_CURRENCY_POSITION = "before"

DEFAULT_TIMEZONE = "Africa/Lagos"
DEFAULT_DATE_FORMAT = "DD/MM/YYYY"
DEFAULT_TIME_FORMAT = "12h"
DEFAULT_WEEK_STARTS = "Monday"


# ============================================================
# CURRENT COMPANY SETTINGS
# ============================================================

def get_current_company_settings():
    """
    Return settings belonging to the currently
    authenticated user's company.

    System Administrators have no company_id,
    so None is returned for them.
    """

    if not current_user.is_authenticated:
        return None

    company_id = getattr(
        current_user,
        "company_id",
        None
    )

    if not company_id:
        return None

    return CompanySetting.query.filter_by(
        company_id=company_id
    ).first()


# ============================================================
# COMPANY SETTINGS BY COMPANY ID
# ============================================================

def get_company_settings(company_id):
    """
    Get settings for a specific company.

    Useful when processing data for a company
    outside the current-user context.
    """

    if not company_id:
        return None

    return CompanySetting.query.filter_by(
        company_id=company_id
    ).first()


# ============================================================
# CURRENCY
# ============================================================

def get_currency_code():

    settings = get_current_company_settings()

    if settings and settings.currency_code:
        return settings.currency_code

    return DEFAULT_CURRENCY_CODE


def get_currency_symbol():

    settings = get_current_company_settings()

    if settings and settings.currency_symbol:
        return settings.currency_symbol

    return DEFAULT_CURRENCY_SYMBOL


def get_decimal_places():

    settings = get_current_company_settings()

    if settings and settings.decimal_places is not None:
        return settings.decimal_places

    return DEFAULT_DECIMAL_PLACES


def get_currency_position():

    settings = get_current_company_settings()

    if settings and settings.currency_position:
        return settings.currency_position

    return DEFAULT_CURRENCY_POSITION


# ============================================================
# FORMAT CURRENCY
# ============================================================

def format_currency(amount):
    """
    Format a financial amount according to the
    current company's currency settings.

    Examples:

        ₦1,500.00
        $1,500.00
        1,500.00 €
    """

    if amount is None:
        amount = Decimal("0")

    try:
        amount = Decimal(str(amount))

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):
        amount = Decimal("0")

    decimal_places = get_decimal_places()
    symbol = get_currency_symbol()
    position = get_currency_position()

    formatted_amount = (
        f"{amount:,.{decimal_places}f}"
    )

    if position == "after":
        return f"{formatted_amount} {symbol}"

    return f"{symbol}{formatted_amount}"


# ============================================================
# TIMEZONE
# ============================================================

def get_company_timezone_name():

    settings = get_current_company_settings()

    if settings and settings.timezone:
        return settings.timezone

    return DEFAULT_TIMEZONE


def get_company_timezone():

    timezone_name = get_company_timezone_name()

    try:
        return ZoneInfo(timezone_name)

    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


# ============================================================
# COMPANY CURRENT TIME
# ============================================================

def company_now():

    return datetime.now(
        get_company_timezone()
    )


def company_today():

    return company_now().date()


# ============================================================
# DATE FORMAT
# ============================================================

def get_date_format():

    settings = get_current_company_settings()

    if settings and settings.date_format:
        return settings.date_format

    return DEFAULT_DATE_FORMAT


# ============================================================
# TIME FORMAT
# ============================================================

def get_time_format():

    settings = get_current_company_settings()

    if settings and settings.time_format:
        return settings.time_format

    return DEFAULT_TIME_FORMAT


# ============================================================
# NORMALIZE DATABASE DATETIME
# ============================================================

def normalize_datetime(value):
    """
    Convert a database datetime into an aware UTC datetime.

    BizFlow stores timestamps using UTC.
    """

    if not isinstance(value, datetime):
        return value

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=ZoneInfo("UTC")
        )

    return value


# ============================================================
# FORMAT COMPANY DATE
# ============================================================

def format_company_date(value):

    if not value:
        return ""

    if isinstance(value, datetime):

        value = normalize_datetime(value)

        value = value.astimezone(
            get_company_timezone()
        )

        value = value.date()

    if not isinstance(value, date):
        return str(value)

    date_format = get_date_format()

    if date_format == "DD/MM/YYYY":
        return value.strftime("%d/%m/%Y")

    if date_format == "MM/DD/YYYY":
        return value.strftime("%m/%d/%Y")

    if date_format == "YYYY-MM-DD":
        return value.strftime("%Y-%m-%d")

    if date_format == "DD MMM YYYY":
        return value.strftime("%d %b %Y")

    return value.strftime("%d/%m/%Y")


# ============================================================
# FORMAT COMPANY TIME
# ============================================================

def format_company_time(value):

    if not value:
        return ""

    time_format = get_time_format()

    if isinstance(value, datetime):

        value = normalize_datetime(value)

        value = value.astimezone(
            get_company_timezone()
        )

        if time_format == "24h":
            return value.strftime("%H:%M")

        return value.strftime("%I:%M %p")

    if isinstance(value, time):

        if time_format == "24h":
            return value.strftime("%H:%M")

        return value.strftime("%I:%M %p")

    return str(value)


# ============================================================
# FORMAT COMPANY DATETIME
# ============================================================

def format_company_datetime(value):

    if not value:
        return ""

    if not isinstance(value, datetime):
        return str(value)

    value = normalize_datetime(value)

    value = value.astimezone(
        get_company_timezone()
    )

    date_format = get_date_format()
    time_format = get_time_format()

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if date_format == "DD/MM/YYYY":

        date_part = value.strftime(
            "%d/%m/%Y"
        )

    elif date_format == "MM/DD/YYYY":

        date_part = value.strftime(
            "%m/%d/%Y"
        )

    elif date_format == "YYYY-MM-DD":

        date_part = value.strftime(
            "%Y-%m-%d"
        )

    elif date_format == "DD MMM YYYY":

        date_part = value.strftime(
            "%d %b %Y"
        )

    else:

        date_part = value.strftime(
            "%d/%m/%Y"
        )

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if time_format == "24h":

        time_part = value.strftime(
            "%H:%M"
        )

    else:

        time_part = value.strftime(
            "%I:%M %p"
        )

    return f"{date_part} {time_part}"


# ============================================================
# WEEK START
# ============================================================

def get_week_starts():

    settings = get_current_company_settings()

    if settings and settings.week_starts:
        return settings.week_starts

    return DEFAULT_WEEK_STARTS