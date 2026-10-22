from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_login import (
    login_user,
    logout_user,
    current_user
)

from sqlalchemy import or_

from . import system_admin_bp
from .decorators import system_admin_required

from ..extensions import db
from ..models import (
    User,
    Company,
    SystemSetting,
    Subscription
)

from datetime import datetime, timezone


# ============================================================
# SYSTEM ADMIN SETUP
# ============================================================

@system_admin_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """
    One-time System Administrator setup.
    """

    existing_admin = User.query.filter_by(
        role="System Administrator"
    ).first()

    if existing_admin:
        return render_template(
            "system_admin/setup_disabled.html"
        ), 403

    import os

    setup_key = os.getenv(
        "SYSTEM_ADMIN_SETUP_KEY"
    )

    if not setup_key:
        return (
            "System Administrator setup is not configured.",
            503
        )

    if request.method == "POST":

        submitted_key = request.form.get(
            "setup_key",
            ""
        ).strip()

        if submitted_key != setup_key:

            flash(
                "Invalid setup key.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            ), 403

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not username:

            flash(
                "Username is required.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            )

        if not email:

            flash(
                "Email address is required.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            )

        if not password:

            flash(
                "Password is required.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            )

        if len(password) < 8:

            flash(
                "Password must be at least 8 characters.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "A user with this email already exists.",
                "danger"
            )

            return render_template(
                "system_admin/setup.html"
            )

        admin = User(
            company_id=None,
            username=username,
            email=email,
            role="System Administrator",
            is_active=True
        )

        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        flash(
            "System Administrator account created successfully.",
            "success"
        )

        return redirect(
            url_for("system_admin.login")
        )

    return render_template(
        "system_admin/setup.html"
    )


# ============================================================
# SYSTEM ADMIN LOGIN
# ============================================================

@system_admin_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

        if current_user.is_system_admin:

            return redirect(
                url_for("system_admin.dashboard")
            )

        logout_user()

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            flash(
                "Email and password are required.",
                "danger"
            )

            return render_template(
                "system_admin/login.html"
            )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            not user
            or not user.is_system_admin
            or not user.is_active
            or not user.check_password(password)
        ):

            flash(
                "Invalid System Administrator credentials.",
                "danger"
            )

            return render_template(
                "system_admin/login.html"
            )

        login_user(
            user,
            remember=False
        )

        return redirect(
            url_for("system_admin.dashboard")
        )

    return render_template(
        "system_admin/login.html"
    )


# ============================================================
# SYSTEM ADMIN LOGOUT
# ============================================================

@system_admin_bp.route("/logout")
def logout():

    if current_user.is_authenticated:
        logout_user()

    return redirect(
        url_for("system_admin.login")
    )


# ============================================================
# SYSTEM ADMIN DASHBOARD
# ============================================================

@system_admin_bp.route("/")
@system_admin_required
def dashboard():

    total_companies = Company.query.count()

    active_companies = Company.query.filter_by(
        is_active=True
    ).count()

    inactive_companies = Company.query.filter_by(
        is_active=False
    ).count()

    total_users = User.query.count()

    active_users = User.query.filter_by(
        is_active=True
    ).count()

    system_admins = User.query.filter_by(
        role="System Administrator"
    ).count()

    # --------------------------------------------------------
    # SUBSCRIPTION STATISTICS
    # --------------------------------------------------------

    total_subscriptions = Subscription.query.count()

    active_subscriptions = Subscription.query.filter_by(
        status="active"
    ).count()

    trial_subscriptions = Subscription.query.filter_by(
        status="trial"
    ).count()

    pending_subscriptions = Subscription.query.filter_by(
        status="pending"
    ).count()

    expired_subscriptions = Subscription.query.filter_by(
        status="expired"
    ).count()

    manually_activated_subscriptions = (
        Subscription.query
        .filter_by(manually_activated=True)
        .count()
    )

    # --------------------------------------------------------
    # SYSTEM SETTINGS
    # --------------------------------------------------------

    system_settings = SystemSetting.query.first()

    return render_template(
        "system_admin/dashboard.html",

        total_companies=total_companies,
        active_companies=active_companies,
        inactive_companies=inactive_companies,

        total_users=total_users,
        active_users=active_users,
        system_admins=system_admins,

        total_subscriptions=total_subscriptions,
        active_subscriptions=active_subscriptions,
        trial_subscriptions=trial_subscriptions,
        pending_subscriptions=pending_subscriptions,
        expired_subscriptions=expired_subscriptions,
        manually_activated_subscriptions=(
            manually_activated_subscriptions
        ),

        system_settings=system_settings
    )


# ============================================================
# USERS
# ============================================================

@system_admin_bp.route("/users")
@system_admin_required
def users():

    search = request.args.get(
        "search",
        ""
    ).strip()

    status = request.args.get(
        "status",
        "all"
    ).strip().lower()

    role = request.args.get(
        "role",
        "all"
    ).strip()

    company_id = request.args.get(
        "company_id",
        "all"
    ).strip()

    query = User.query

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if search:

        search_pattern = f"%{search}%"

        query = query.outerjoin(
            Company,
            User.company_id == Company.id
        ).filter(
            or_(
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                Company.name.ilike(search_pattern)
            )
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if status == "active":

        query = query.filter(
            User.is_active.is_(True)
        )

    elif status == "inactive":

        query = query.filter(
            User.is_active.is_(False)
        )

    # --------------------------------------------------------
    # ROLE
    # --------------------------------------------------------

    if role != "all":

        query = query.filter(
            User.role == role
        )

    # --------------------------------------------------------
    # COMPANY
    # --------------------------------------------------------

    if company_id != "all":

        try:

            company_id_value = int(
                company_id
            )

            query = query.filter(
                User.company_id == company_id_value
            )

        except (TypeError, ValueError):

            company_id = "all"

    users_list = query.order_by(
        User.created_at.desc()
    ).all()

    companies_list = Company.query.order_by(
        Company.name.asc()
    ).all()

    roles = [
        "System Administrator",
        "Company Administrator",
        "Staff"
    ]

    return render_template(
        "system_admin/users.html",
        users=users_list,
        companies=companies_list,
        roles=roles,
        search=search,
        status=status,
        role=role,
        company_id=company_id
    )


# ============================================================
# VIEW USER
# ============================================================

@system_admin_bp.route(
    "/users/<int:user_id>"
)
@system_admin_required
def user_view(user_id):

    user = db.session.get(
        User,
        user_id
    )

    if user is None:

        flash(
            "User not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.users")
        )

    company = None

    if user.company_id:

        company = db.session.get(
            Company,
            user.company_id
        )

    return render_template(
        "system_admin/user_view.html",
        user=user,
        company=company
    )


# ============================================================
# EDIT USER
# ============================================================

@system_admin_bp.route(
    "/users/<int:user_id>/edit",
    methods=["GET", "POST"]
)
@system_admin_required
def user_edit(user_id):

    user = db.session.get(
        User,
        user_id
    )

    if user is None:

        flash(
            "User not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.users")
        )

    companies_list = Company.query.order_by(
        Company.name.asc()
    ).all()

    roles = [
        "Company Administrator",
        "Staff"
    ]

    is_target_system_admin = user.is_system_admin

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not username:

            flash(
                "Username is required.",
                "danger"
            )

            return render_template(
                "system_admin/user_form.html",
                user=user,
                companies=companies_list,
                roles=roles,
                is_target_system_admin=(
                    is_target_system_admin
                )
            )

        if not email:

            flash(
                "Email address is required.",
                "danger"
            )

            return render_template(
                "system_admin/user_form.html",
                user=user,
                companies=companies_list,
                roles=roles,
                is_target_system_admin=(
                    is_target_system_admin
                )
            )

        existing_user = User.query.filter(
            User.email == email,
            User.id != user.id
        ).first()

        if existing_user:

            flash(
                "Another user already uses this email address.",
                "danger"
            )

            return render_template(
                "system_admin/user_form.html",
                user=user,
                companies=companies_list,
                roles=roles,
                is_target_system_admin=(
                    is_target_system_admin
                )
            )

        user.username = username
        user.email = email

        if is_target_system_admin:

            user.company_id = None
            user.role = "System Administrator"

        else:

            selected_company = request.form.get(
                "company_id",
                ""
            ).strip()

            selected_role = request.form.get(
                "role",
                "Staff"
            ).strip()

            if not selected_company:

                flash(
                    "A company must be assigned to this user.",
                    "danger"
                )

                return render_template(
                    "system_admin/user_form.html",
                    user=user,
                    companies=companies_list,
                    roles=roles,
                    is_target_system_admin=(
                        is_target_system_admin
                    )
                )

            try:

                selected_company_id = int(
                    selected_company
                )

            except (TypeError, ValueError):

                flash(
                    "Invalid company selection.",
                    "danger"
                )

                return render_template(
                    "system_admin/user_form.html",
                    user=user,
                    companies=companies_list,
                    roles=roles,
                    is_target_system_admin=(
                        is_target_system_admin
                    )
                )

            company = db.session.get(
                Company,
                selected_company_id
            )

            if company is None:

                flash(
                    "Selected company was not found.",
                    "danger"
                )

                return render_template(
                    "system_admin/user_form.html",
                    user=user,
                    companies=companies_list,
                    roles=roles,
                    is_target_system_admin=(
                        is_target_system_admin
                    )
                )

            if selected_role not in roles:

                flash(
                    "Invalid user role.",
                    "danger"
                )

                return render_template(
                    "system_admin/user_form.html",
                    user=user,
                    companies=companies_list,
                    roles=roles,
                    is_target_system_admin=(
                        is_target_system_admin
                    )
                )

            user.company_id = company.id
            user.role = selected_role

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if new_password:

            if len(new_password) < 8:

                flash(
                    "Password must be at least 8 characters.",
                    "danger"
                )

                return render_template(
                    "system_admin/user_form.html",
                    user=user,
                    companies=companies_list,
                    roles=roles,
                    is_target_system_admin=(
                        is_target_system_admin
                    )
                )

            if new_password != confirm_password:

                flash(
                    "Passwords do not match.",
                    "danger"
                )

                return render_template(
                    "system_admin/user_form.html",
                    user=user,
                    companies=companies_list,
                    roles=roles,
                    is_target_system_admin=(
                        is_target_system_admin
                    )
                )

            user.set_password(
                new_password
            )

        db.session.commit()

        flash(
            f"{user.username} was updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "system_admin.user_view",
                user_id=user.id
            )
        )

    return render_template(
        "system_admin/user_form.html",
        user=user,
        companies=companies_list,
        roles=roles,
        is_target_system_admin=(
            is_target_system_admin
        )
    )


# ============================================================
# ACTIVATE / DEACTIVATE USER
# ============================================================

@system_admin_bp.route(
    "/users/<int:user_id>/toggle",
    methods=["POST"]
)
@system_admin_required
def user_toggle(user_id):

    user = db.session.get(
        User,
        user_id
    )

    if user is None:

        flash(
            "User not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.users")
        )

    if user.id == current_user.id:

        flash(
            "You cannot deactivate your own System Administrator account.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("system_admin.users")
        )

    if user.is_system_admin:

        flash(
            "System Administrator accounts cannot be "
            "deactivated from User Management.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("system_admin.users")
        )

    user.is_active = not user.is_active

    db.session.commit()

    if user.is_active:

        flash(
            f"{user.username} has been activated.",
            "success"
        )

    else:

        flash(
            f"{user.username} has been deactivated.",
            "warning"
        )

    return redirect(
        request.referrer
        or url_for("system_admin.users")
    )


# ============================================================
# COMPANIES
# ============================================================

@system_admin_bp.route("/companies")
@system_admin_required
def companies():

    search = request.args.get(
        "search",
        ""
    ).strip()

    status = request.args.get(
        "status",
        "all"
    ).strip().lower()

    query = Company.query

    if search:

        search_pattern = f"%{search}%"

        query = query.filter(
            or_(
                Company.name.ilike(search_pattern),
                Company.email.ilike(search_pattern),
                Company.phone.ilike(search_pattern)
            )
        )

    if status == "active":

        query = query.filter_by(
            is_active=True
        )

    elif status == "inactive":

        query = query.filter_by(
            is_active=False
        )

    companies_list = query.order_by(
        Company.created_at.desc()
    ).all()

    return render_template(
        "system_admin/companies.html",
        companies=companies_list,
        search=search,
        status=status
    )


# ============================================================
# CREATE COMPANY
# ============================================================

@system_admin_bp.route(
    "/companies/new",
    methods=["GET", "POST"]
)
@system_admin_required
def company_create():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        if not name:

            flash(
                "Company name is required.",
                "danger"
            )

            return render_template(
                "system_admin/company_form.html",
                company=None
            )

        company = Company(
            name=name,
            email=email or None,
            phone=phone or None,
            address=address or None,
            is_active=True
        )

        db.session.add(company)
        db.session.commit()

        flash(
            f"{company.name} was created successfully.",
            "success"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    return render_template(
        "system_admin/company_form.html",
        company=None
    )


# ============================================================
# EDIT COMPANY
# ============================================================

@system_admin_bp.route(
    "/companies/<int:company_id>/edit",
    methods=["GET", "POST"]
)
@system_admin_required
def company_edit(company_id):

    company = db.session.get(
        Company,
        company_id
    )

    if company is None:

        flash(
            "Company not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        if not name:

            flash(
                "Company name is required.",
                "danger"
            )

            return render_template(
                "system_admin/company_form.html",
                company=company
            )

        company.name = name
        company.email = email or None
        company.phone = phone or None
        company.address = address or None

        db.session.commit()

        flash(
            f"{company.name} was updated successfully.",
            "success"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    return render_template(
        "system_admin/company_form.html",
        company=company
    )


# ============================================================
# VIEW COMPANY
# ============================================================

@system_admin_bp.route(
    "/companies/<int:company_id>"
)
@system_admin_required
def company_view(company_id):

    company = db.session.get(
        Company,
        company_id
    )

    if company is None:

        flash(
            "Company not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    company_users = User.query.filter_by(
        company_id=company.id
    ).order_by(
        User.created_at.desc()
    ).all()

    # --------------------------------------------------------
    # SUBSCRIPTION INFORMATION
    # --------------------------------------------------------

    subscriptions = Subscription.query.filter_by(
        company_id=company.id
    ).order_by(
        Subscription.created_at.desc()
    ).all()

    current_subscription = (
        Subscription.query
        .filter_by(company_id=company.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    return render_template(
        "system_admin/company_view.html",
        company=company,
        company_users=company_users,
        subscriptions=subscriptions,
        current_subscription=current_subscription
    )


# ============================================================
# ACTIVATE / DEACTIVATE COMPANY
# ============================================================

@system_admin_bp.route(
    "/companies/<int:company_id>/toggle",
    methods=["POST"]
)
@system_admin_required
def company_toggle(company_id):

    company = db.session.get(
        Company,
        company_id
    )

    if company is None:

        flash(
            "Company not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    # --------------------------------------------------------
    # CURRENTLY ACTIVE -> DEACTIVATE
    # --------------------------------------------------------

    if company.is_active:

        company.is_active = False

        # Remove System Administrator override
        current_subscription = (
            Subscription.query
            .filter_by(company_id=company.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

        if current_subscription:

            current_subscription.manually_activated = False
            current_subscription.manually_activated_by = None
            current_subscription.manually_activated_at = None

            if current_subscription.status == "manually_active":
                current_subscription.status = "expired"

        db.session.commit()

        flash(
            f"{company.name} has been deactivated manually "
            f"by the System Administrator.",
            "warning"
        )

    # --------------------------------------------------------
    # CURRENTLY INACTIVE -> ACTIVATE
    # --------------------------------------------------------

    else:

        company.is_active = True

        current_subscription = (
            Subscription.query
            .filter_by(company_id=company.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

        # ----------------------------------------------------
        # CREATE MANUAL SUBSCRIPTION IF NONE EXISTS
        # ----------------------------------------------------

        if current_subscription is None:

            current_subscription = Subscription(
                company_id=company.id,
                plan="manual",
                amount=0,
                currency="NGN",
                status="manually_active",
                payment_status="not_required",
                payment_method="system_admin",
                activation_source="system_admin",
                manually_activated=True,
                manually_activated_by=current_user.id,
                manually_activated_at=datetime.now(timezone.utc),
                start_date=datetime.now(timezone.utc),
                end_date=None
            )

            db.session.add(
                current_subscription
            )

        # ----------------------------------------------------
        # UPDATE EXISTING SUBSCRIPTION
        # ----------------------------------------------------

        else:

            current_subscription.status = "manually_active"

            current_subscription.payment_status = (
                current_subscription.payment_status
                or "not_required"
            )

            current_subscription.activation_source = (
                "system_admin"
            )

            current_subscription.manually_activated = True

            current_subscription.manually_activated_by = (
                current_user.id
            )

            current_subscription.manually_activated_at = (
                datetime.now(timezone.utc)
            )

        db.session.commit()

        flash(
            f"{company.name} has been activated manually "
            f"by the System Administrator. "
            f"The System Administrator override is active.",
            "success"
        )

    return redirect(
        request.referrer
        or url_for("system_admin.companies")
    )


# ============================================================
# MANUALLY ACTIVATE COMPANY
# ============================================================

@system_admin_bp.route(
    "/companies/<int:company_id>/activate",
    methods=["POST"]
)
@system_admin_required
def company_activate(company_id):

    company = db.session.get(
        Company,
        company_id
    )

    if company is None:

        flash(
            "Company not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    company.is_active = True

    current_subscription = (
        Subscription.query
        .filter_by(company_id=company.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    # --------------------------------------------------------
    # CREATE MANUAL SUBSCRIPTION IF NONE EXISTS
    # --------------------------------------------------------

    if current_subscription is None:

        current_subscription = Subscription(
            company_id=company.id,
            plan="manual",
            amount=0,
            currency="NGN",
            status="manually_active",
            payment_status="not_required",
            payment_method="system_admin",
            activation_source="system_admin",
            manually_activated=True,
            manually_activated_by=current_user.id,
            manually_activated_at=datetime.now(timezone.utc),
            start_date=datetime.now(timezone.utc),
            end_date=None
        )

        db.session.add(
            current_subscription
        )

    # --------------------------------------------------------
    # UPDATE EXISTING SUBSCRIPTION
    # --------------------------------------------------------

    else:

        current_subscription.status = "manually_active"

        current_subscription.activation_source = (
            "system_admin"
        )

        current_subscription.manually_activated = True

        current_subscription.manually_activated_by = (
            current_user.id
        )

        current_subscription.manually_activated_at = (
            datetime.now(timezone.utc)
        )

    db.session.commit()

    flash(
        f"{company.name} has been manually activated.",
        "success"
    )

    return redirect(
        request.referrer
        or url_for(
            "system_admin.company_view",
            company_id=company.id
        )
    )


# ============================================================
# MANUALLY DEACTIVATE COMPANY
# ============================================================

@system_admin_bp.route(
    "/companies/<int:company_id>/deactivate",
    methods=["POST"]
)
@system_admin_required
def company_deactivate(company_id):

    company = db.session.get(
        Company,
        company_id
    )

    if company is None:

        flash(
            "Company not found.",
            "danger"
        )

        return redirect(
            url_for("system_admin.companies")
        )

    company.is_active = False

    current_subscription = (
        Subscription.query
        .filter_by(company_id=company.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    if current_subscription:

        current_subscription.manually_activated = False

        current_subscription.manually_activated_by = None

        current_subscription.manually_activated_at = None

        if current_subscription.status == "manually_active":

            current_subscription.status = "expired"

    db.session.commit()

    flash(
        f"{company.name} has been manually deactivated.",
        "warning"
    )

    return redirect(
        request.referrer
        or url_for(
            "system_admin.company_view",
            company_id=company.id
        )
    )


# ============================================================
# SUBSCRIPTIONS
# ============================================================

@system_admin_bp.route(
    "/subscriptions"
)
@system_admin_required
def subscriptions():

    search = request.args.get(
        "search",
        ""
    ).strip()

    status = request.args.get(
        "status",
        "all"
    ).strip().lower()

    plan = request.args.get(
        "plan",
        "all"
    ).strip().lower()

    # --------------------------------------------------------
    # BASE QUERY
    # --------------------------------------------------------

    query = (
        Subscription.query
        .join(
            Company,
            Subscription.company_id == Company.id
        )
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if search:

        search_pattern = f"%{search}%"

        query = query.filter(
            or_(
                Company.name.ilike(
                    search_pattern
                ),

                Company.email.ilike(
                    search_pattern
                ),

                Subscription.transaction_reference.ilike(
                    search_pattern
                ),

                Subscription.order_id.ilike(
                    search_pattern
                ),

                Subscription.paystack_reference.ilike(
                    search_pattern
                ),

                Subscription.paystack_transaction_id.ilike(
                    search_pattern
                )
            )
        )

    # --------------------------------------------------------
    # STATUS FILTER
    # --------------------------------------------------------

    if status != "all":

        query = query.filter(
            Subscription.status == status
        )

    # --------------------------------------------------------
    # PLAN FILTER
    # --------------------------------------------------------

    if plan != "all":

        query = query.filter(
            Subscription.plan == plan
        )

    # --------------------------------------------------------
    # GET RECORDS
    # --------------------------------------------------------

    subscriptions_list = (
        query
        .order_by(
            Subscription.created_at.desc()
        )
        .all()
    )

    # --------------------------------------------------------
    # SUMMARY COUNTS
    # --------------------------------------------------------

    total_count = Subscription.query.count()

    active_count = Subscription.query.filter(
        Subscription.status == "active"
    ).count()

    trial_count = Subscription.query.filter(
        Subscription.status == "trial"
    ).count()

    pending_count = Subscription.query.filter(
        Subscription.status == "pending"
    ).count()

    expired_count = Subscription.query.filter(
        Subscription.status == "expired"
    ).count()

    maintenance_count = Subscription.query.filter(
        Subscription.status == "maintenance"
    ).count()

    failed_count = Subscription.query.filter(
        Subscription.status == "failed"
    ).count()

    return render_template(
        "system_admin/subscriptions.html",

        subscriptions=subscriptions_list,

        search=search,
        status=status,
        plan=plan,

        total_count=total_count,
        active_count=active_count,
        trial_count=trial_count,
        pending_count=pending_count,
        expired_count=expired_count,
        maintenance_count=maintenance_count,
        failed_count=failed_count
    )


# ============================================================
# VIEW SUBSCRIPTION
# ============================================================

@system_admin_bp.route(
    "/subscriptions/<int:subscription_id>"
)
@system_admin_required
def subscription_view(subscription_id):

    subscription = db.session.get(
        Subscription,
        subscription_id
    )

    if subscription is None:

        flash(
            "Subscription not found.",
            "danger"
        )

        return redirect(
            url_for(
                "system_admin.subscriptions"
            )
        )

    company = db.session.get(
        Company,
        subscription.company_id
    )

    # --------------------------------------------------------
    # BASE SUBSCRIPTION AMOUNT
    # --------------------------------------------------------

    if subscription.plan == "monthly":

        base_amount = 15000

    elif subscription.plan == "annual":

        base_amount = 135000

    else:

        base_amount = 0

    # --------------------------------------------------------
    # MAINTENANCE FEE
    # --------------------------------------------------------

    maintenance_fee = (
        subscription.maintenance_fee or 0
    )

    # --------------------------------------------------------
    # TOTAL PAYMENT
    #
    # For paid subscriptions, subscription.amount already
    # represents the amount initialized with Paystack.
    #
    # For clarity, we also calculate the expected total.
    # --------------------------------------------------------

    expected_total = (
        base_amount
        + float(maintenance_fee)
    )

    return render_template(
        "system_admin/subscription_view.html",

        subscription=subscription,

        company=company,

        base_amount=base_amount,

        maintenance_fee=maintenance_fee,

        expected_total=expected_total
    )

# ============================================================
# SECURITY
# ============================================================

@system_admin_bp.route("/security")
@system_admin_required
def security():

    return render_template(
        "system_admin/security.html"
    )


# ============================================================
# PLATFORM SETTINGS
# ============================================================

@system_admin_bp.route(
    "/platform-settings",
    methods=["GET", "POST"]
)
@system_admin_required
def platform_settings():

    system_settings = SystemSetting.query.first()

    if system_settings is None:

        system_settings = SystemSetting(
            maintenance_mode=False,
            maintenance_message=(
                "The system is currently undergoing maintenance. "
                "Please try again later."
            )
        )

        db.session.add(
            system_settings
        )

        db.session.commit()

    if request.method == "POST":

        maintenance_mode = (
            request.form.get(
                "maintenance_mode"
            ) == "on"
        )

        maintenance_message = request.form.get(
            "maintenance_message",
            ""
        ).strip()

        if not maintenance_message:

            maintenance_message = (
                "The system is currently undergoing maintenance. "
                "Please try again later."
            )

        system_settings.maintenance_mode = (
            maintenance_mode
        )

        system_settings.maintenance_message = (
            maintenance_message
        )

        db.session.commit()

        if maintenance_mode:

            flash(
                "Maintenance mode has been enabled.",
                "warning"
            )

        else:

            flash(
                "Maintenance mode has been disabled.",
                "success"
            )

        return redirect(
            url_for(
                "system_admin.platform_settings"
            )
        )

    return render_template(
        "system_admin/platform_settings.html",
        system_settings=system_settings
    )
