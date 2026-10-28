from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request
)

from flask_login import (
    login_required,
    current_user
)

from app.company_admin.decorators import (
    company_permission_required
)

from app.extensions import db

from app.models import Service

from app.services import services_bp

from app.services.forms import ServiceForm


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def clean_text(value):
    """
    Safely clean optional text fields.
    """

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def clean_required_text(value):
    """
    Safely clean required text fields.
    """

    return str(value or "").strip()


def company_id():
    """
    Return the currently authenticated user's company ID.
    """

    return current_user.company_id


# =========================================================
# SERVICES
# =========================================================

@services_bp.route("/")
@login_required
@company_permission_required("view_sales")
def services():

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    status = request.args.get(
        "status",
        "",
        type=str
    ).strip().lower()

    query = Service.query.filter_by(
        company_id=company_id()
    )

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    if search:

        query = query.filter(
            db.or_(
                Service.name.ilike(
                    f"%{search}%"
                ),

                Service.service_code.ilike(
                    f"%{search}%"
                ),

                Service.description.ilike(
                    f"%{search}%"
                )
            )
        )

    # -----------------------------------------------------
    # Status filter
    # -----------------------------------------------------

    if status == "active":

        query = query.filter(
            Service.is_active.is_(True)
        )

    elif status == "inactive":

        query = query.filter(
            Service.is_active.is_(False)
        )

    services = query.order_by(
        Service.name.asc()
    ).all()

    return render_template(
        "services/services.html",
        services=services,
        search=search,
        selected_status=status
    )


# =========================================================
# NEW SERVICE
# =========================================================

@services_bp.route(
    "/new",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_sales")
def new_service():

    form = ServiceForm()

    if form.validate_on_submit():

        name = clean_required_text(
            form.name.data
        )

        service_code = clean_required_text(
            form.service_code.data
        )

        # -------------------------------------------------
        # Check duplicate service code.
        # -------------------------------------------------

        existing = Service.query.filter_by(
            company_id=company_id(),
            service_code=service_code
        ).first()

        if existing:

            flash(
                "A service with this service code already exists.",
                "warning"
            )

            return render_template(
                "services/service_form.html",
                form=form,
                title="New Service"
            )

        # -------------------------------------------------
        # Create service.
        # -------------------------------------------------

        service = Service(
            company_id=company_id(),

            name=name,

            service_code=service_code,

            description=clean_text(
                form.description.data
            ),

            price=form.price.data or 0,

            is_active=True
        )

        try:

            db.session.add(service)

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to create the service. Please try again.",
                "danger"
            )

            return render_template(
                "services/service_form.html",
                form=form,
                title="New Service"
            )

        flash(
            "Service created successfully.",
            "success"
        )

        return redirect(
            url_for("services.services")
        )

    return render_template(
        "services/service_form.html",
        form=form,
        title="New Service"
    )


# =========================================================
# EDIT SERVICE
# =========================================================

@services_bp.route(
    "/<int:service_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@company_permission_required("manage_sales")
def edit_service(service_id):

    service = Service.query.filter_by(
        id=service_id,
        company_id=company_id()
    ).first_or_404()

    form = ServiceForm(
        obj=service
    )

    if form.validate_on_submit():

        name = clean_required_text(
            form.name.data
        )

        service_code = clean_required_text(
            form.service_code.data
        )

        # -------------------------------------------------
        # Prevent duplicate service codes.
        # -------------------------------------------------

        duplicate = Service.query.filter(
            Service.company_id == company_id(),
            Service.service_code == service_code,
            Service.id != service.id
        ).first()

        if duplicate:

            flash(
                "Another service already uses this service code.",
                "warning"
            )

            return render_template(
                "services/service_form.html",
                form=form,
                title="Edit Service"
            )

        # -------------------------------------------------
        # Update service.
        # -------------------------------------------------

        service.name = name

        service.service_code = service_code

        service.description = clean_text(
            form.description.data
        )

        service.price = (
            form.price.data or 0
        )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to update the service. Please try again.",
                "danger"
            )

            return render_template(
                "services/service_form.html",
                form=form,
                title="Edit Service"
            )

        flash(
            "Service updated successfully.",
            "success"
        )

        return redirect(
            url_for("services.services")
        )

    return render_template(
        "services/service_form.html",
        form=form,
        title="Edit Service"
    )


# =========================================================
# ACTIVATE / DEACTIVATE SERVICE
# =========================================================

@services_bp.route(
    "/<int:service_id>/toggle",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_sales")
def toggle_service(service_id):

    service = Service.query.filter_by(
        id=service_id,
        company_id=company_id()
    ).first_or_404()

    service.is_active = not service.is_active

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to change the service status. Please try again.",
            "danger"
        )

        return redirect(
            url_for("services.services")
        )

    if service.is_active:

        flash(
            f"Service '{service.name}' activated successfully.",
            "success"
        )

    else:

        flash(
            f"Service '{service.name}' deactivated successfully.",
            "warning"
        )

    return redirect(
        url_for("services.services")
    )


# =========================================================
# DELETE SERVICE
# =========================================================

@services_bp.route(
    "/<int:service_id>/delete",
    methods=["POST"]
)
@login_required
@company_permission_required("manage_sales")
def delete_service(service_id):

    service = Service.query.filter_by(
        id=service_id,
        company_id=company_id()
    ).first_or_404()

    # -----------------------------------------------------
    # Services used in previous sales must be preserved.
    # -----------------------------------------------------

    if service.sale_items:

        flash(
            "This service cannot be deleted because it has "
            "already been used in a sale. Deactivate it instead.",
            "warning"
        )

        return redirect(
            url_for("services.services")
        )

    try:

        db.session.delete(service)

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to delete the service. Please try again.",
            "danger"
        )

        return redirect(
            url_for("services.services")
        )

    flash(
        "Service deleted successfully.",
        "success"
    )

    return redirect(
        url_for("services.services")
    )