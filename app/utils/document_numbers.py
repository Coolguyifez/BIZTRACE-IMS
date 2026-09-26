from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask_login import current_user

from app.extensions import db
from app.models import (
    CompanySetting,
    Sale,
    Purchase,
    Expense,

)


# ============================================================
# COMPANY SETTINGS
# ============================================================

def get_company_settings():
    """
    Get the settings for the currently logged-in company.

    If the company does not have a settings record yet,
    create one using the model defaults.
    """

    settings = CompanySetting.query.filter_by(
        company_id=current_user.company_id
    ).first()

    if not settings:

        settings = CompanySetting(
            company_id=current_user.company_id
        )

        db.session.add(settings)
        db.session.flush()

    return settings


# ============================================================
# COMPANY LOCAL TIME
# ============================================================

def get_company_now(settings):
    """
    Return the current datetime using the company's timezone.
    """

    timezone_name = (
        settings.timezone
        or "Africa/Lagos"
    )

    try:

        company_timezone = ZoneInfo(
            timezone_name
        )

    except Exception:

        company_timezone = ZoneInfo(
            "Africa/Lagos"
        )

    return datetime.now(
        company_timezone
    )


# ============================================================
# DATE PART
# ============================================================

def get_date_part(
    current_datetime,
    reset_mode
):
    """
    Generate the date portion used by document numbers.

    daily:
        20260925

    monthly:
        202609

    yearly:
        2026

    never:
        ""
    """

    if reset_mode == "daily":

        return current_datetime.strftime(
            "%Y%m%d"
        )

    if reset_mode == "monthly":

        return current_datetime.strftime(
            "%Y%m"
        )

    if reset_mode == "yearly":

        return current_datetime.strftime(
            "%Y"
        )

    return ""


# ============================================================
# DOCUMENT NUMBER GENERATOR
# ============================================================

def generate_document_number(
    model,
    number_field,
    prefix,
    settings
):
    """
    Generate a company-scoped document number.

    Examples:

        INV-20260925-0001
        INV-202609-0001
        INV-2026-0001
        INV-0001
    """

    current_datetime = get_company_now(
        settings
    )

    reset_mode = (
        settings.number_reset
        or "daily"
    )

    include_date = bool(
        settings.include_date
    )

    number_length = (
        settings.number_length
        or 4
    )

    number_length = max(
        2,
        min(number_length, 8)
    )

    prefix = (
        prefix
        or "DOC"
    ).strip().upper()

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_part = ""

    if include_date:

        date_part = get_date_part(
            current_datetime,
            reset_mode
        )

    # --------------------------------------------------------
    # PREFIX
    # --------------------------------------------------------

    if date_part:

        number_prefix = (
            f"{prefix}-"
            f"{date_part}-"
        )

    else:

        number_prefix = (
            f"{prefix}-"
        )

    # --------------------------------------------------------
    # FIND LAST DOCUMENT
    # --------------------------------------------------------

    query = model.query.filter(
        model.company_id ==
        current_user.company_id
    )

    query = query.filter(
        getattr(
            model,
            number_field
        ).like(
            f"{number_prefix}%"
        )
    )

    last_document = (
        query
        .order_by(
            model.id.desc()
        )
        .first()
    )

    # --------------------------------------------------------
    # NEXT SEQUENCE
    # --------------------------------------------------------

    if last_document:

        existing_number = getattr(
            last_document,
            number_field
        )

        try:

            last_number = int(
                existing_number
                .split("-")[-1]
            )

        except (
            ValueError,
            TypeError,
            AttributeError,
            IndexError
        ):

            last_number = 0

        next_number = (
            last_number + 1
        )

    else:

        next_number = 1

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    sequence = str(
        next_number
    ).zfill(
        number_length
    )

    return (
        f"{number_prefix}"
        f"{sequence}"
    )


# ============================================================
# INVOICE
# ============================================================

def generate_invoice_number():

    settings = get_company_settings()

    return generate_document_number(
        model=Sale,
        number_field="invoice_number",
        prefix=settings.invoice_prefix,
        settings=settings
    )


# ============================================================
# PURCHASE
# ============================================================

def generate_purchase_number():

    settings = get_company_settings()

    return generate_document_number(
        model=Purchase,
        number_field="purchase_number",
        prefix=settings.purchase_prefix,
        settings=settings
    )


# ============================================================
# EXPENSE
# ============================================================

def generate_expense_number():

    settings = get_company_settings()

    return generate_document_number(
        model=Expense,
        number_field="expense_number",
        prefix=settings.expense_prefix,
        settings=settings
    )