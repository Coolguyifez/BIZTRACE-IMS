from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort
)

from flask_login import (
    current_user
)

from sqlalchemy import or_, func

from app.extensions import db
from app.models import (
    User,
    Role,
    Permission,
    RolePermission,
    UserRole
)

from app.company_admin import company_admin_bp
from app.company_admin.decorators import company_permission_required
from sqlalchemy.exc import IntegrityError

# ============================================================
# HELPERS
# ============================================================

def get_company_role(role_id):
    """
    Return a role belonging to the currently logged-in company.

    System Administrators are not handled here because this
    module is intended for company administration.
    """

    if current_user.company_id is None:
        abort(403)

    role = Role.query.filter(
        Role.id == role_id,
        Role.company_id == current_user.company_id
    ).first()

    if role is None:
        abort(404)

    return role


def get_company_user(user_id):
    """
    Return a user belonging to the currently logged-in company.
    """

    if current_user.company_id is None:
        abort(403)

    user = User.query.filter(
        User.id == user_id,
        User.company_id == current_user.company_id
    ).first()

    if user is None:
        abort(404)

    return user

# ============================================================
# ROLES
# ============================================================

@company_admin_bp.route("/roles")
@company_permission_required("view_users")
def roles():

    company_id = current_user.company_id

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    status = request.args.get(
        "status",
        "all",
        type=str
    )

    query = Role.query.filter(
        Role.company_id == company_id
    )

    if search:

        query = query.filter(
            or_(
                Role.name.ilike(
                    f"%{search}%"
                ),
                Role.description.ilike(
                    f"%{search}%"
                )
            )
        )

    if status == "active":

        query = query.filter(
            Role.is_active.is_(True)
        )

    elif status == "inactive":

        query = query.filter(
            Role.is_active.is_(False)
        )

    roles_list = query.order_by(
        Role.is_system_role.desc(),
        Role.name.asc()
    ).all()

    return render_template(
        "company_admin/roles.html",
        roles=roles_list,
        search=search,
        status=status
    )


# ============================================================
# VIEW ROLE
# ============================================================

@company_admin_bp.route("/roles/<int:role_id>")
@company_permission_required("view_users")
def role_view(role_id):

    role = get_company_role(role_id)

    permissions = (
        Permission.query
        .join(
            RolePermission,
            RolePermission.permission_id == Permission.id
        )
        .filter(
            RolePermission.role_id == role.id
        )
        .order_by(
            Permission.permission_group.asc(),
            Permission.name.asc()
        )
        .all()
    )

    assigned_users = (
        User.query
        .join(
            UserRole,
            UserRole.user_id == User.id
        )
        .filter(
            UserRole.role_id == role.id,
            User.company_id == current_user.company_id
        )
        .order_by(
            User.username.asc()
        )
        .all()
    )

    return render_template(
        "company_admin/role_view.html",
        role=role,
        permissions=permissions,
        assigned_users=assigned_users
    )


# ============================================================
# CREATE ROLE
# ============================================================

@company_admin_bp.route(
    "/roles/new",
    methods=["GET", "POST"]
)
@company_permission_required("manage_users")
def role_create():

    permissions = (
        Permission.query
        .order_by(
            Permission.permission_group.asc(),
            Permission.name.asc()
        )
        .all()
    )

    permission_groups = {}

    for permission in permissions:

        group = (
            permission.permission_group
            or "Other"
        )

        permission_groups.setdefault(
            group,
            []
        ).append(permission)

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        selected_permissions = request.form.getlist(
            "permissions"
        )

        if not name:

            flash(
                "Role name is required.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=None,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        if len(name) > 100:

            flash(
                "Role name cannot exceed 100 characters.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=None,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        existing_role = Role.query.filter(
            Role.company_id == current_user.company_id,
            func.lower(Role.name) == name.lower()
        ).first()

        if existing_role:

            flash(
                "A role with this name already exists.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=None,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        role = Role(
            company_id=current_user.company_id,
            name=name,
            description=description or None,
            is_system_role=False,
            is_active=True
        )

        db.session.add(role)

        try:

            db.session.flush()

            valid_permission_ids = {
                str(permission.id)
                for permission in permissions
            }

            for permission_id in selected_permissions:

                if permission_id not in valid_permission_ids:
                    continue

                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=int(permission_id)
                )

                db.session.add(
                    role_permission
                )

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "The role could not be created. Please try again.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=None,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        flash(
            f'Role "{role.name}" was created successfully.',
            "success"
        )

        return redirect(
            url_for(
                "company_admin.role_view",
                role_id=role.id
            )
        )

    return render_template(
        "company_admin/role_form.html",
        role=None,
        permissions=permissions,
        permission_groups=permission_groups,
        selected_permissions=[]
    )


# ============================================================
# EDIT ROLE
# ============================================================

@company_admin_bp.route(
    "/roles/<int:role_id>/edit",
    methods=["GET", "POST"]
)
@company_permission_required("manage_users")
def role_edit(role_id):

    role = get_company_role(role_id)

    # System roles are managed by the platform.
    # Company Administrators should not modify them.
    if role.is_system_role:

        flash(
            "System roles cannot be modified.",
            "warning"
        )

        return redirect(
            url_for(
                "company_admin.role_view",
                role_id=role.id
            )
        )

    permissions = (
        Permission.query
        .order_by(
            Permission.permission_group.asc(),
            Permission.name.asc()
        )
        .all()
    )

    permission_groups = {}

    for permission in permissions:

        group = (
            permission.permission_group
            or "Other"
        )

        permission_groups.setdefault(
            group,
            []
        ).append(permission)

    current_permission_ids = {
        str(rp.permission_id)
        for rp in role.role_permissions
    }

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        selected_permissions = request.form.getlist(
            "permissions"
        )

        if not name:

            flash(
                "Role name is required.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=role,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        existing_role = Role.query.filter(
            Role.company_id == current_user.company_id,
            func.lower(Role.name) == name.lower(),
            Role.id != role.id
        ).first()

        if existing_role:

            flash(
                "Another role with this name already exists.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=role,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        role.name = name

        role.description = (
            description
            or None
        )

        valid_permission_ids = {
            str(permission.id)
            for permission in permissions
        }

        selected_permission_ids = {
            int(permission_id)
            for permission_id in selected_permissions
            if permission_id in valid_permission_ids
        }

        # Remove permissions no longer selected.
        for role_permission in list(
            role.role_permissions
        ):

            if (
                role_permission.permission_id
                not in selected_permission_ids
            ):

                db.session.delete(
                    role_permission
                )

        # Add newly selected permissions.
        existing_permission_ids = {
            role_permission.permission_id
            for role_permission in role.role_permissions
        }

        for permission_id in selected_permission_ids:

            if permission_id not in existing_permission_ids:

                db.session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission_id
                    )
                )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "The role could not be updated. Please try again.",
                "danger"
            )

            return render_template(
                "company_admin/role_form.html",
                role=role,
                permissions=permissions,
                permission_groups=permission_groups,
                selected_permissions=selected_permissions
            )

        flash(
            f'Role "{role.name}" was updated successfully.',
            "success"
        )

        return redirect(
            url_for(
                "company_admin.role_view",
                role_id=role.id
            )
        )

    return render_template(
        "company_admin/role_form.html",
        role=role,
        permissions=permissions,
        permission_groups=permission_groups,
        selected_permissions=current_permission_ids
    )


# ============================================================
# TOGGLE ROLE
# ============================================================

@company_admin_bp.route(
    "/roles/<int:role_id>/toggle",
    methods=["POST"]
)
@company_permission_required("manage_users")
def role_toggle(role_id):

    role = get_company_role(role_id)

    if role.is_system_role:

        flash(
            "System roles cannot be deactivated.",
            "warning"
        )

        return redirect(
            url_for(
                "company_admin.role_view",
                role_id=role.id
            )
        )

    role.is_active = not role.is_active

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "The role status could not be changed.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.role_view",
                role_id=role.id
            )
        )

    if role.is_active:

        flash(
            f'Role "{role.name}" has been activated.',
            "success"
        )

    else:

        flash(
            f'Role "{role.name}" has been deactivated.',
            "warning"
        )

    return redirect(
        url_for(
            "company_admin.role_view",
            role_id=role.id
        )
    )


# ============================================================
# USERS
# ============================================================

@company_admin_bp.route("/users")
@company_permission_required("view_users")
def users():

    company_id = current_user.company_id

    search = request.args.get(
        "search",
        "",
        type=str
    ).strip()

    status = request.args.get(
        "status",
        "all",
        type=str
    )

    query = User.query.filter(
        User.company_id == company_id
    )

    if search:

        query = query.filter(
            or_(
                User.username.ilike(
                    f"%{search}%"
                ),
                User.email.ilike(
                    f"%{search}%"
                )
            )
        )

    if status == "active":

        query = query.filter(
            User.is_active.is_(True)
        )

    elif status == "inactive":

        query = query.filter(
            User.is_active.is_(False)
        )

    users_list = query.order_by(
        User.username.asc()
    ).all()

    return render_template(
        "company_admin/users.html",
        users=users_list,
        search=search,
        status=status
    )

# ============================================================
# CREATE USER
# ============================================================

@company_admin_bp.route(
    "/users/new",
    methods=["GET", "POST"]
)
@company_permission_required("manage_users")
def user_create():

    # Only active roles belonging to this company
    # can be assigned to a new user.
    roles = Role.query.filter(
        Role.company_id == current_user.company_id,
        Role.is_active.is_(True)
    ).order_by(
        Role.is_system_role.desc(),
        Role.name.asc()
    ).all()

    if request.method == "POST":

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

        selected_role_ids = request.form.getlist(
            "roles"
        )

        errors = []

        # ----------------------------------------------------
        # USERNAME VALIDATION
        # ----------------------------------------------------

        if not username:

            errors.append(
                "Username is required."
            )

        elif len(username) > 80:

            errors.append(
                "Username cannot exceed 80 characters."
            )

        # ----------------------------------------------------
        # EMAIL VALIDATION
        # ----------------------------------------------------

        if not email:

            errors.append(
                "Email address is required."
            )

        elif len(email) > 150:

            errors.append(
                "Email address cannot exceed 150 characters."
            )

        else:

            existing_email = User.query.filter(
                func.lower(User.email) == email
            ).first()

            if existing_email:

                errors.append(
                    "An account with this email address already exists."
                )

        # ----------------------------------------------------
        # PASSWORD VALIDATION
        # ----------------------------------------------------

        if not password:

            errors.append(
                "Password is required."
            )

        elif len(password) < 8:

            errors.append(
                "Password must be at least 8 characters."
            )

        if password != confirm_password:

            errors.append(
                "Passwords do not match."
            )

        # ----------------------------------------------------
        # ROLE VALIDATION
        # ----------------------------------------------------

        if not selected_role_ids:

            errors.append(
                "Please select at least one role."
            )

        # Convert submitted IDs safely.
        role_ids = set()

        for role_id in selected_role_ids:

            try:

                role_ids.add(
                    int(role_id)
                )

            except (TypeError, ValueError):

                continue

        # Only roles belonging to this company
        # and currently active may be assigned.
        selected_roles = Role.query.filter(
            Role.id.in_(role_ids),
            Role.company_id == current_user.company_id,
            Role.is_active.is_(True)
        ).all()

        valid_role_ids = {
            role.id
            for role in selected_roles
        }

        if role_ids != valid_role_ids:

            errors.append(
                "One or more selected roles are invalid."
            )

        # ----------------------------------------------------
        # RETURN FORM WITH VALIDATION ERRORS
        # ----------------------------------------------------

        if errors:

            for error in errors:

                flash(
                    error,
                    "danger"
                )

            return render_template(
                "company_admin/user_form.html",
                user=None,
                roles=roles,
                selected_role_ids={
                    str(role_id)
                    for role_id in role_ids
                }
            )

        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

        user = User(
            company_id=current_user.company_id,
            username=username,
            email=email,
            role="Staff",
            is_active=True
        )

        user.set_password(
            password
        )

        db.session.add(
            user
        )

        try:

            # Get user.id before creating UserRole records.
            db.session.flush()

            # ------------------------------------------------
            # ASSIGN SELECTED ROLES
            # ------------------------------------------------

            for role in selected_roles:

                db.session.add(
                    UserRole(
                        user_id=user.id,
                        role_id=role.id,
                        assigned_by=current_user.id
                    )
                )

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "The user could not be created. "
                "Please try again.",
                "danger"
            )

            return render_template(
                "company_admin/user_form.html",
                user=None,
                roles=roles,
                selected_role_ids={
                    str(role_id)
                    for role_id in role_ids
                }
            )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        flash(
            f'User "{user.username}" was created successfully.',
            "success"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    # --------------------------------------------------------
    # GET REQUEST
    # --------------------------------------------------------

    return render_template(
        "company_admin/user_form.html",
        user=None,
        roles=roles,
        selected_role_ids=set()
    )


# ============================================================
# EDIT USER
# ============================================================

@company_admin_bp.route(
    "/users/<int:user_id>/edit",
    methods=["GET", "POST"]
)
@company_permission_required("manage_users")
def user_edit(user_id):

    user = get_company_user(user_id)

    # --------------------------------------------------------
    # Load roles belonging to this company
    # --------------------------------------------------------

    roles = (
        Role.query
        .filter(
            Role.company_id == current_user.company_id,
            Role.is_active.is_(True)
        )
        .order_by(
            Role.is_system_role.desc(),
            Role.name.asc()
        )
        .all()
    )

    # --------------------------------------------------------
    # Get currently assigned role IDs
    # --------------------------------------------------------

    assigned_role_ids = {
        role.id
        for role in (
            Role.query
            .join(
                UserRole,
                UserRole.role_id == Role.id
            )
            .filter(
                UserRole.user_id == user.id,
                Role.company_id == current_user.company_id
            )
            .all()
        )
    }

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    if request.method == "POST":

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

        errors = []

        # ----------------------------------------------------
        # USERNAME
        # ----------------------------------------------------

        if not username:

            errors.append(
                "Username is required."
            )

        elif len(username) > 80:

            errors.append(
                "Username cannot exceed 80 characters."
            )

        # ----------------------------------------------------
        # EMAIL
        # ----------------------------------------------------

        if not email:

            errors.append(
                "Email address is required."
            )

        elif len(email) > 150:

            errors.append(
                "Email address cannot exceed 150 characters."
            )

        elif (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):

            errors.append(
                "Please enter a valid email address."
            )

        else:

            existing_user = User.query.filter(
                func.lower(User.email) == email,
                User.id != user.id
            ).first()

            if existing_user:

                errors.append(
                    "Another user is already using this email address."
                )

        # ----------------------------------------------------
        # OPTIONAL PASSWORD
        # ----------------------------------------------------

        if password:

            if len(password) < 8:

                errors.append(
                    "Password must be at least 8 characters."
                )

            if password != confirm_password:

                errors.append(
                    "Passwords do not match."
                )

        # ----------------------------------------------------
        # VALIDATION ERRORS
        # ----------------------------------------------------

        if errors:

            for error in errors:

                flash(
                    error,
                    "danger"
                )

            return render_template(
                "company_admin/user_form.html",
                user=user,
                roles=roles,
                selected_role_ids={
                    str(role_id)
                    for role_id in assigned_role_ids
                }
            )

        # ----------------------------------------------------
        # UPDATE USER
        # ----------------------------------------------------

        user.username = username
        user.email = email

        # Only change the password if one was supplied.
        if password:

            user.set_password(
                password
            )

        try:

            db.session.commit()

        except IntegrityError:

            db.session.rollback()

            flash(
                "The user could not be updated. "
                "The email address may already be in use.",
                "danger"
            )

            return redirect(
                url_for(
                    "company_admin.user_edit",
                    user_id=user.id
                )
            )

        except Exception:

            db.session.rollback()

            flash(
                "The user could not be updated. "
                "Please try again.",
                "danger"
            )

            return redirect(
                url_for(
                    "company_admin.user_edit",
                    user_id=user.id
                )
            )

        flash(
            f'User "{user.username}" was updated successfully.',
            "success"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(
        "company_admin/user_form.html",
        user=user,
        roles=roles,
        selected_role_ids={
            str(role_id)
            for role_id in assigned_role_ids
        }
    )

# ============================================================
# TOGGLE USER STATUS
# ============================================================

@company_admin_bp.route(
    "/users/<int:user_id>/toggle",
    methods=["POST"]
)
@company_permission_required("manage_users")
def user_toggle(user_id):

    user = get_company_user(user_id)

    # --------------------------------------------------------
    # Prevent users from deactivating themselves
    # --------------------------------------------------------
    if user.id == current_user.id:

        flash(
            "You cannot deactivate your own account.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    # --------------------------------------------------------
    # If currently active, check whether this is the last
    # active Company Administrator
    # --------------------------------------------------------
    if user.is_active:

        is_company_admin = (
            UserRole.query
            .join(
                Role,
                Role.id == UserRole.role_id
            )
            .filter(
                UserRole.user_id == user.id,
                Role.company_id == current_user.company_id,
                Role.name == "Company Administrator"
            )
            .first()
        )

        if is_company_admin:

            active_admin_count = (
                User.query
                .join(
                    UserRole,
                    UserRole.user_id == User.id
                )
                .join(
                    Role,
                    Role.id == UserRole.role_id
                )
                .filter(
                    User.company_id == current_user.company_id,
                    User.is_active.is_(True),
                    Role.company_id == current_user.company_id,
                    Role.name == "Company Administrator"
                )
                .count()
            )

            if active_admin_count <= 1:

                flash(
                    "The last active Company Administrator "
                    "cannot be deactivated.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "company_admin.user_view",
                        user_id=user.id
                    )
                )

    # --------------------------------------------------------
    # Toggle status
    # --------------------------------------------------------
    user.is_active = not user.is_active

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "The user's account status could not be changed.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    # --------------------------------------------------------
    # Success message
    # --------------------------------------------------------
    if user.is_active:

        flash(
            f'User "{user.username}" has been activated.',
            "success"
        )

    else:

        flash(
            f'User "{user.username}" has been deactivated.',
            "warning"
        )

    return redirect(
        url_for(
            "company_admin.user_view",
            user_id=user.id
        )
    )



# ============================================================
# VIEW USER
# ============================================================

@company_admin_bp.route("/users/<int:user_id>")
@company_permission_required("view_users")
def user_view(user_id):

    user = get_company_user(user_id)

    assigned_roles = (
        Role.query
        .join(
            UserRole,
            UserRole.role_id == Role.id
        )
        .filter(
            UserRole.user_id == user.id,
            Role.company_id == current_user.company_id
        )
        .order_by(
            Role.name.asc()
        )
        .all()
    )

    return render_template(
        "company_admin/user_view.html",
        user=user,
        assigned_roles=assigned_roles
    )


# ============================================================
# ASSIGN ROLE TO USER
# ============================================================

@company_admin_bp.route(
    "/users/<int:user_id>/roles",
    methods=["POST"]
)
@company_permission_required("manage_users")
def assign_user_role(user_id):

    user = get_company_user(user_id)

    role_id = request.form.get(
        "role_id",
        type=int
    )

    if not role_id:

        flash(
            "Please select a role.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    role = get_company_role(role_id)

    if not role.is_active:

        flash(
            "An inactive role cannot be assigned.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    existing = UserRole.query.filter_by(
        user_id=user.id,
        role_id=role.id
    ).first()

    if existing:

        flash(
            "This user already has this role.",
            "info"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    db.session.add(
        UserRole(
            user_id=user.id,
            role_id=role.id,
            assigned_by=current_user.id
        )
    )

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "The role could not be assigned.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    flash(
        f'Role "{role.name}" assigned to {user.username}.',
        "success"
    )

    return redirect(
        url_for(
            "company_admin.user_view",
            user_id=user.id
        )
    )


# ============================================================
# REMOVE ROLE FROM USER
# ============================================================

@company_admin_bp.route(
    "/users/<int:user_id>/roles/<int:role_id>/remove",
    methods=["POST"]
)
@company_permission_required("manage_users")
def remove_user_role(
    user_id,
    role_id
):

    user = get_company_user(user_id)

    role = get_company_role(role_id)

    user_role = UserRole.query.filter_by(
        user_id=user.id,
        role_id=role.id
    ).first()

    if user_role is None:

        flash(
            "The selected role is not assigned to this user.",
            "warning"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    # --------------------------------------------------------
    # Prevent removing the last active Company Administrator
    # --------------------------------------------------------

    if role.name == "Company Administrator":

        active_admin_count = (
            User.query
            .join(
                UserRole,
                UserRole.user_id == User.id
            )
            .filter(
                User.company_id == current_user.company_id,
                User.is_active.is_(True),
                UserRole.role_id == role.id
            )
            .count()
        )

        if active_admin_count <= 1:

            flash(
                "The last active Company Administrator role "
                "cannot be removed.",
                "danger"
            )

            return redirect(
                url_for(
                    "company_admin.user_view",
                    user_id=user.id
                )
            )

    db.session.delete(
        user_role
    )

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "The role could not be removed.",
            "danger"
        )

        return redirect(
            url_for(
                "company_admin.user_view",
                user_id=user.id
            )
        )

    flash(
        f'Role "{role.name}" removed from {user.username}.',
        "success"
    )

    return redirect(
        url_for(
            "company_admin.user_view",
            user_id=user.id
        )
    )