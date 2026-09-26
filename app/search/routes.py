from flask import jsonify, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, inspect

from app.search import search_bp
from app.extensions import db

from app.models import (
    Company,
    User,

    Category,
    Product,
    Customer,
    Supplier,

    InventoryTransaction,

    Sale,
    SaleItem,

    Purchase,
    PurchaseItem,

    Payment,
    CashDeposit,

    ExpenseCategory,
    Expense,

    Notification,
)

# ============================================================
# SEARCHABLE MODELS
# ============================================================

SEARCHABLE_MODELS = []


def register_searchable_models(*models):
    """
    Register SQLAlchemy models that should participate
    in global search.
    """

    for model in models:

        if model not in SEARCHABLE_MODELS:
            SEARCHABLE_MODELS.append(model)


# ============================================================
# REGISTER MODELS
# ============================================================

register_searchable_models(
    Company,
    User,

    Category,
    Product,
    Customer,
    Supplier,

    InventoryTransaction,

    Sale,
    SaleItem,

    Purchase,
    PurchaseItem,

    Payment,
    CashDeposit,

    ExpenseCategory,
    Expense,

    Notification,
)


# ============================================================
# MODEL ENDPOINTS
# ============================================================
#
# These endpoints are used when a search result is clicked.
#
# If an endpoint does not exist in your application yet,
# simply remove/comment that entry.
#
# ============================================================

MODEL_ENDPOINTS = {

    User: "company_admin.users",

    Product: "products.products",

    Customer: "products.customers",

    Supplier: "products.suppliers",

    Category: "products.categories",

    # Add your company management endpoint here if you have one.
    # Company: "company_admin.companies",
}


# ============================================================
# MODEL ICONS
# ============================================================

MODEL_ICONS = {

    User: "bi-person",

    Company: "bi-building",

    Product: "bi-box-seam",

    Customer: "bi-people",

    Supplier: "bi-truck",

    Category: "bi-tags",

}


# ============================================================
# MODEL LABELS
# ============================================================

MODEL_LABELS = {

    User: "User",

    Company: "Company",

    Product: "Product",

    Customer: "Customer",

    Supplier: "Supplier",

    Category: "Category",

}


# ============================================================
# SENSITIVE FIELDS
# ============================================================

SENSITIVE_FIELDS = {

    "password",

    "password_hash",

    "token",

    "reset_token",

    "secret",

    "api_key",

    "access_token",

    "refresh_token",

}


# ============================================================
# HELPERS
# ============================================================

def get_company_id_column(model):
    """
    Return company_id column if the model has one.
    """

    try:

        mapper = inspect(model)

        if "company_id" in mapper.columns:

            return mapper.columns["company_id"]

    except Exception:

        pass

    return None


# ============================================================


def get_searchable_columns(model):
    """
    Return text-like columns that can safely be searched.

    Sensitive fields are excluded.
    """

    try:

        mapper = inspect(model)

    except Exception:

        return []


    columns = []


    for column in mapper.columns:

        column_name = column.name.lower()


        # ----------------------------------------------------
        # NEVER SEARCH SENSITIVE FIELDS
        # ----------------------------------------------------

        if column_name in SENSITIVE_FIELDS:

            continue


        if any(
            sensitive in column_name
            for sensitive in (
                "password",
                "token",
                "secret",
                "api_key",
            )
        ):

            continue


        # ----------------------------------------------------
        # ONLY STRING-LIKE COLUMNS
        # ----------------------------------------------------

        try:

            python_type = column.type.python_type

        except Exception:

            python_type = None


        if python_type is str:

            columns.append(column)


    return columns


# ============================================================


def get_display_value(instance):
    """
    Find the best human-readable title for a search result.
    """

    preferred_fields = [

        "name",

        "title",

        "username",

        "product_name",

        "customer_name",

        "supplier_name",

        "invoice_number",

        "purchase_number",

        "booking_number",

        "reference",

        "sku",

        "code",

        "email",

    ]


    for field in preferred_fields:

        if not hasattr(instance, field):

            continue


        try:

            value = getattr(
                instance,
                field,
                None
            )

        except Exception:

            value = None


        if value:

            return str(value)


    # --------------------------------------------------------
    # FALLBACK TO ID
    # --------------------------------------------------------

    if hasattr(instance, "id"):

        try:

            return (
                f"{instance.__class__.__name__} "
                f"#{instance.id}"
            )

        except Exception:

            pass


    return instance.__class__.__name__


# ============================================================


def get_secondary_value(instance):
    """
    Find useful secondary information.
    """

    preferred_fields = [

        "email",

        "phone",

        "sku",

        "code",

        "status",

        "reference",

        "description",

        "number",

    ]


    for field in preferred_fields:

        if not hasattr(instance, field):

            continue


        try:

            value = getattr(
                instance,
                field,
                None
            )

        except Exception:

            value = None


        if value:

            value = str(value)

            # Prevent extremely long descriptions
            if len(value) > 100:

                value = value[:97] + "..."


            return value


    return ""


# ============================================================


def get_result_url(model, record):
    """
    Generate a URL for a search result.

    Returns None if the model has no registered endpoint
    or the endpoint cannot be generated.
    """

    endpoint = MODEL_ENDPOINTS.get(model)


    if not endpoint:

        return None


    if not hasattr(record, "id"):

        return None


    try:

        return url_for(
            endpoint,
            id=record.id
        )

    except Exception:

        # Some list pages may not accept id=.
        # Do not allow URL generation to break search.
        return None


# ============================================================


def get_result_icon(model):
    """
    Return Bootstrap icon for a model.
    """

    return MODEL_ICONS.get(
        model,
        "bi-search"
    )


# ============================================================


def get_result_type(model):
    """
    Return friendly model name.
    """

    return MODEL_LABELS.get(
        model,
        model.__name__
    )


# ============================================================
# SEARCH API
# ============================================================

@search_bp.route("/api", methods=["GET"])
@login_required
def api():

    # ========================================================
    # GET QUERY
    # ========================================================

    search_query = (
        request.args
        .get("q", "")
        .strip()
    )


    # ========================================================
    # MINIMUM SEARCH LENGTH
    # ========================================================

    if len(search_query) < 2:

        return jsonify({

            "success": True,

            "query": search_query,

            "results": [],

            "count": 0,

        })


    # ========================================================
    # LIMIT QUERY LENGTH
    # ========================================================
    #
    # Prevent unnecessarily large queries.
    #
    # ========================================================

    search_query = search_query[:100]


    search_term = f"%{search_query}%"


    results = []


    # ========================================================
    # SEARCH REGISTERED MODELS
    # ========================================================

    for model in SEARCHABLE_MODELS:

        # Stop when global result limit is reached.
        if len(results) >= 30:

            break


        try:

            # ==================================================
            # SEARCHABLE COLUMNS
            # ==================================================

            searchable_columns = (
                get_searchable_columns(model)
            )


            if not searchable_columns:

                continue


            # ==================================================
            # BUILD SEARCH FILTERS
            # ==================================================

            filters = [

                column.ilike(search_term)

                for column in searchable_columns

            ]


            if not filters:

                continue


            # ==================================================
            # BASE QUERY
            # ==================================================

            query_object = (
                db.session
                .query(model)
            )


            # ==================================================
            # COMPANY ISOLATION
            # ==================================================
            #
            # If the model has company_id, normal users can
            # only search records belonging to their company.
            #
            # System admins can search across companies.
            #
            # ==================================================

            company_column = (
                get_company_id_column(model)
            )


            if company_column is not None:

                if (
                    not getattr(
                        current_user,
                        "is_system_admin",
                        False
                    )
                    and getattr(
                        current_user,
                        "company_id",
                        None
                    ) is not None
                ):

                    query_object = (
                        query_object
                        .filter(
                            company_column
                            ==
                            current_user.company_id
                        )
                    )


            # ==================================================
            # SEARCH
            # ==================================================

            query_object = (
                query_object
                .filter(
                    or_(*filters)
                )
            )


            # ==================================================
            # LIMIT PER MODEL
            # ==================================================

            records = (
                query_object
                .limit(8)
                .all()
            )


            # ==================================================
            # BUILD RESULTS
            # ==================================================

            for record in records:

                # ----------------------------------------------
                # GLOBAL LIMIT
                # ----------------------------------------------

                if len(results) >= 30:

                    break


                # ----------------------------------------------
                # DISPLAY VALUE
                # ----------------------------------------------

                title = (
                    get_display_value(record)
                )


                # ----------------------------------------------
                # SECONDARY VALUE
                # ----------------------------------------------

                subtitle = (
                    get_secondary_value(record)
                )


                # ----------------------------------------------
                # URL
                # ----------------------------------------------

                result_url = (
                    get_result_url(
                        model,
                        record
                    )
                )


                # ----------------------------------------------
                # RESULT
                # ----------------------------------------------

                results.append({

                    "type": get_result_type(
                        model
                    ),

                    "model": model.__name__,

                    "title": title,

                    "subtitle": subtitle,

                    "url": result_url,

                    "icon": get_result_icon(
                        model
                    ),

                })


        except Exception as error:

            # --------------------------------------------------
            # IMPORTANT:
            # One model should never break global search.
            # --------------------------------------------------

            current_app = None

            try:

                from flask import current_app

                current_app.logger.exception(
                    "Global search failed for %s",
                    model.__name__
                )

            except Exception:

                pass

            continue


    # ========================================================
    # RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "query": search_query,

        "results": results[:30],

        "count": len(results),

    })