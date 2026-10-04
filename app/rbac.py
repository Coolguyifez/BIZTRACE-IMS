from .extensions import db
from .models import (
    Company,
    User,
    Permission,
    Role,
    RolePermission,
    UserRole,
)


# ============================================================
# PERMISSIONS
# ============================================================

PERMISSIONS = [

    # ========================================================
    # DASHBOARD
    # ========================================================

    {
        "name": "view_dashboard",
        "description": "View the company dashboard.",
        "group": "Dashboard",
    },

    # ========================================================
    # PRODUCTS
    # ========================================================

    {
        "name": "view_products",
        "description": "View products.",
        "group": "Products",
    },

    {
        "name": "manage_products",
        "description": "Create, edit, and delete products.",
        "group": "Products",
    },

    # ========================================================
    # CATEGORIES
    # ========================================================

    {
        "name": "view_categories",
        "description": "View product categories.",
        "group": "Categories",
    },

    {
        "name": "manage_categories",
        "description": "Create, edit, and delete product categories.",
        "group": "Categories",
    },

    # ========================================================
    # INVENTORY
    # ========================================================

    {
        "name": "view_inventory",
        "description": "View inventory information.",
        "group": "Inventory",
    },

    {
        "name": "manage_inventory",
        "description": "Manage inventory and stock transactions.",
        "group": "Inventory",
    },

    # ========================================================
    # SALES
    # ========================================================

    {
        "name": "view_sales",
        "description": "View & create sales records.",
        "group": "Sales",
    },

    {
        "name": "manage_sales",
        "description": "Edit and manage sales.",
        "group": "Sales",
    },

    # ========================================================
    # PURCHASES
    # ========================================================

    {
        "name": "view_purchases",
        "description": "View purchase records.",
        "group": "Purchases",
    },

    {
        "name": "manage_purchases",
        "description": "Create, edit, and manage purchases.",
        "group": "Purchases",
    },

    # ========================================================
    # CUSTOMERS
    # ========================================================

    {
        "name": "view_customers",
        "description": "View customers.",
        "group": "Customers",
    },

    {
        "name": "manage_customers",
        "description": "Create, edit, and delete customers.",
        "group": "Customers",
    },

    # ========================================================
    # SUPPLIERS
    # ========================================================

    {
        "name": "view_suppliers",
        "description": "View suppliers.",
        "group": "Suppliers",
    },

    {
        "name": "manage_suppliers",
        "description": "Create, edit, and delete suppliers.",
        "group": "Suppliers",
    },

    # ========================================================
    # EXPENSES
    # ========================================================

    {
        "name": "view_expenses",
        "description": "View business expenses.",
        "group": "Expenses",
    },

    {
        "name": "manage_expenses",
        "description": "Create, edit, and manage expenses.",
        "group": "Expenses",
    },

    # ========================================================
    # PAYMENTS
    # ========================================================

    {
        "name": "view_payments",
        "description": "View payments.",
        "group": "Payments",
    },

    {
        "name": "manage_payments",
        "description": "Create and manage payments.",
        "group": "Payments",
    },

    # ========================================================
    # RECEIVABLES
    # ========================================================

    {
        "name": "view_receivables",
        "description": "View receivables.",
        "group": "Receivables",
    },

    {
        "name": "manage_receivables",
        "description": "Manage receivables.",
        "group": "Receivables",
    },

    # ========================================================
    # CASH DEPOSITS
    # ========================================================

    {
        "name": "view_cash_deposits",
        "description": "View cash deposit records.",
        "group": "Cash Deposits",
    },

    {
        "name": "manage_cash_deposits",
        "description": "Create and manage cash deposits.",
        "group": "Cash Deposits",
    },

    # ========================================================
    # PAYABLES
    # ========================================================

    {
        "name": "view_payables",
        "description": "View payables.",
        "group": "Payables",
    },

    {
        "name": "manage_payables",
        "description": "Manage payables.",
        "group": "Payables",
    },

    # ========================================================
    # PRODUCTION
    # ========================================================

    {
        "name": "view_production",
        "description": "View production information.",
        "group": "Production",
    },

    {
        "name": "manage_production",
        "description": "Manage production operations.",
        "group": "Production",
    },

    # ========================================================
    # REPORTS
    # ========================================================

    {
        "name": "view_reports",
        "description": "View business reports.",
        "group": "Reports",
    },

    # ========================================================
    # USERS
    # ========================================================

    {
        "name": "view_users",
        "description": "View company users.",
        "group": "Users",
    },

    {
        "name": "manage_users",
        "description": "Create, edit, deactivate, and manage company users.",
        "group": "Users",
    },

    # ========================================================
    # COMPANY
    # ========================================================

    {
        "name": "view_company",
        "description": "View company information.",
        "group": "Company",
    },

    {
        "name": "manage_company",
        "description": "Manage company information and settings.",
        "group": "Company",
    },
]


# ============================================================
# DEFAULT ROLES
# ============================================================

DEFAULT_ROLES = {

    "Company Administrator": {
        "description": (
            "Full access to all company operations and administration."
        ),
        "permissions": [
            permission["name"]
            for permission in PERMISSIONS
        ],
    },

    "Sales Manager": {
        "description": (
            "Manage sales operations and customer records."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_inventory",
            "view_sales",
            "manage_sales",
            "view_customers",
            "manage_customers",
            "view_reports",
        ],
    },

    "Sales Staff": {
        "description": (
            "Handle day-to-day sales operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_inventory",
            "view_sales",
            "view_customers",
            "manage_customers",
        ],
    },

    "Inventory Manager": {
        "description": (
            "Manage products, categories, and inventory."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "manage_products",
            "view_categories",
            "manage_categories",
            "view_inventory",
            "manage_inventory",
            "view_purchases",
            "view_suppliers",
            "view_reports",
        ],
    },

    "Inventory Staff": {
        "description": (
            "Handle inventory operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_categories",
            "view_inventory",
            "manage_inventory",
        ],
    },

    "Purchase Manager": {
        "description": (
            "Manage purchases and supplier operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_inventory",
            "view_purchases",
            "manage_purchases",
            "view_suppliers",
            "manage_suppliers",
            "view_reports",
        ],
    },

    "Purchase Staff": {
        "description": (
            "Handle day-to-day purchasing operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_inventory",
            "view_purchases",
            "manage_purchases",
            "view_suppliers",
        ],
    },

    "Accountant": {
        "description": (
            "Manage financial records and financial operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_sales",
            "view_purchases",
            "view_expenses",
            "manage_expenses",
            "view_payments",
            "manage_payments",
            "view_cash_deposits",
            "manage_cash_deposits",
            "view_receivables",
            "manage_receivables",
            "view_payables",
            "manage_payables",
            "view_reports",
        ],
    },

    "Production Manager": {
        "description": (
            "Manage production operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_inventory",
            "view_production",
            "manage_production",
            "view_reports",
        ],
    },

    "Production Staff": {
        "description": (
            "Handle production operations."
        ),
        "permissions": [
            "view_dashboard",
            "view_products",
            "view_inventory",
            "view_production",
            "manage_production",
        ],
    },

    "Viewiers": {
        "description": (
            "Visitors"
        ),
        "permissions": [
            "view_dashboard",
            "view_users",
            "view_production",
        ],
    },
}


# ============================================================
# CONSTANT
# ============================================================

COMPANY_ADMIN_ROLE_NAME = "Company Administrator"


# ============================================================
# SEED GLOBAL PERMISSIONS
# ============================================================

def seed_permissions():
    """
    Create and synchronize all global permissions.

    Existing permissions are not duplicated.
    """

    created = 0
    updated = 0

    for data in PERMISSIONS:

        permission = Permission.query.filter_by(
            name=data["name"]
        ).first()

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        if permission is None:

            permission = Permission(
                name=data["name"],
                description=data["description"],
                permission_group=data["group"],
            )

            db.session.add(permission)

            created += 1

            continue

        # ----------------------------------------------------
        # UPDATE
        # ----------------------------------------------------

        changed = False

        if permission.description != data["description"]:

            permission.description = data["description"]

            changed = True

        if permission.permission_group != data["group"]:

            permission.permission_group = data["group"]

            changed = True

        if changed:

            updated += 1

    db.session.flush()

    return {
        "created": created,
        "updated": updated,
    }


# ============================================================
# GET PERMISSION MAP
# ============================================================

def get_permission_map():

    permissions = Permission.query.all()

    return {
        permission.name: permission
        for permission in permissions
    }


# ============================================================
# CREATE / SYNCHRONIZE COMPANY ROLE
# ============================================================

def create_company_role(
    company,
    role_name,
    description,
    permission_names,
    permission_map=None,
):
    """
    Create or synchronize a company role.
    """

    if company is None:
        raise ValueError("Company is required.")

    if permission_map is None:
        permission_map = get_permission_map()

    role = Role.query.filter_by(
        company_id=company.id,
        name=role_name,
    ).first()

    # --------------------------------------------------------
    # CREATE ROLE
    # --------------------------------------------------------

    if role is None:

        role = Role(
            company_id=company.id,
            name=role_name,
            description=description,
            is_system_role=False,
            is_active=True,
        )

        db.session.add(role)

        db.session.flush()

    else:

        if role.description != description:

            role.description = description

        if not role.is_active:

            role.is_active = True

    # --------------------------------------------------------
    # ATTACH PERMISSIONS
    # --------------------------------------------------------

    for permission_name in permission_names:

        permission = permission_map.get(
            permission_name
        )

        if permission is None:
            continue

        existing = RolePermission.query.filter_by(
            role_id=role.id,
            permission_id=permission.id,
        ).first()

        if existing:
            continue

        db.session.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id,
            )
        )

    return role


# ============================================================
# SEED COMPANY ROLES
# ============================================================

def seed_company_roles(company):

    if company is None:
        raise ValueError("Company is required.")

    seed_permissions()

    permission_map = get_permission_map()

    roles = {}

    for role_name, role_data in DEFAULT_ROLES.items():

        role = create_company_role(
            company=company,
            role_name=role_name,
            description=role_data["description"],
            permission_names=role_data["permissions"],
            permission_map=permission_map,
        )

        roles[role_name] = role

    db.session.flush()

    return roles


# ============================================================
# ASSIGN ROLE TO USER
# ============================================================

def assign_role_to_user(
    user,
    role,
    assigned_by=None,
):
    """
    Assign a role to a user.

    Does not commit.
    """

    if user is None:
        return None

    if role is None:
        return None

    if user.company_id != role.company_id:
        raise ValueError(
            "User and role must belong to the same company."
        )

    existing = UserRole.query.filter_by(
        user_id=user.id,
        role_id=role.id,
    ).first()

    if existing:
        return existing

    user_role = UserRole(
        user_id=user.id,
        role_id=role.id,
        assigned_by=(
            assigned_by.id
            if assigned_by is not None
            else None
        ),
    )

    db.session.add(user_role)

    db.session.flush()

    return user_role


# ============================================================
# DETECT COMPANY ADMINISTRATOR
# ============================================================

def is_company_administrator(user):
    """
    Determine whether a user is a Company Administrator.

    IMPORTANT:
    User.is_company_admin is a read-only property.

    Therefore this function uses the persisted User.role
    field as the database source of truth.
    """

    if user is None:
        return False

    role_name = str(
        getattr(user, "role", "") or ""
    ).strip().lower()

    return role_name == COMPANY_ADMIN_ROLE_NAME.lower()


# ============================================================
# GET COMPANY ADMINISTRATORS
# ============================================================

def get_company_administrators(company):
    """
    Return all Company Administrators for a company.

    Uses User.role instead of filtering on the read-only
    is_company_admin property.
    """

    if company is None:
        return []

    return User.query.filter(
        User.company_id == company.id,
        User.role == COMPANY_ADMIN_ROLE_NAME,
    ).all()


# ============================================================
# ENSURE COMPANY ADMIN ROLE
# ============================================================

def ensure_company_admin_role(
    user,
    company,
    assigned_by=None,
):
    """
    Ensure a Company Administrator has:

        1. Company Administrator role
        2. Company Administrator permissions
        3. UserRole record

    Does not assign to user.is_company_admin because that
    property is read-only.
    """

    if user is None:
        return None

    if company is None:
        return None

    # --------------------------------------------------------
    # VERIFY COMPANY OWNERSHIP
    # --------------------------------------------------------

    if user.company_id != company.id:
        return None

    # --------------------------------------------------------
    # ENSURE ROLE FIELD
    # --------------------------------------------------------

    if not is_company_administrator(user):

        user.role = COMPANY_ADMIN_ROLE_NAME

    # --------------------------------------------------------
    # CREATE / SYNCHRONIZE COMPANY ROLES
    # --------------------------------------------------------

    roles = seed_company_roles(
        company
    )

    admin_role = roles.get(
        COMPANY_ADMIN_ROLE_NAME
    )

    if admin_role is None:

        admin_role = Role.query.filter_by(
            company_id=company.id,
            name=COMPANY_ADMIN_ROLE_NAME,
        ).first()

    if admin_role is None:

        raise RuntimeError(
            "Company Administrator role could not be created."
        )

    # --------------------------------------------------------
    # ASSIGN ADMIN ROLE
    # --------------------------------------------------------

    user_role = assign_role_to_user(
        user=user,
        role=admin_role,
        assigned_by=assigned_by,
    )

    db.session.flush()

    return user_role


# ============================================================
# INITIALIZE COMPANY RBAC
# ============================================================

def initialize_company_rbac(
    company,
    administrator=None,
    assigned_by=None,
):
    """
    Initialize all RBAC records for a company.

    Creates:

        Permissions
        Roles
        RolePermissions
        UserRole for the Company Administrator
    """

    if company is None:
        raise ValueError("Company is required.")

    roles = seed_company_roles(
        company
    )

    if administrator is not None:

        ensure_company_admin_role(
            user=administrator,
            company=company,
            assigned_by=assigned_by,
        )

    db.session.flush()

    return roles


# ============================================================
# SYNCHRONIZE ONE COMPANY
# ============================================================

def sync_company_roles(company):
    """
    Synchronize all RBAC records for one company.
    """

    if company is None:

        raise ValueError(
            "Company is required for RBAC synchronization."
        )

    permission_result = seed_permissions()

    roles = seed_company_roles(
        company
    )

    added_permissions = 0
    assigned_users = 0

    # --------------------------------------------------------
    # ENSURE ALL ROLE PERMISSIONS
    # --------------------------------------------------------

    permission_map = get_permission_map()

    for role_name, role_data in DEFAULT_ROLES.items():

        role = roles.get(
            role_name
        )

        if role is None:
            continue

        for permission_name in role_data["permissions"]:

            permission = permission_map.get(
                permission_name
            )

            if permission is None:
                continue

            existing = RolePermission.query.filter_by(
                role_id=role.id,
                permission_id=permission.id,
            ).first()

            if existing:
                continue

            db.session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )

            added_permissions += 1

    # --------------------------------------------------------
    # COMPANY ADMINISTRATORS
    # --------------------------------------------------------

    admin_role = roles.get(
        COMPANY_ADMIN_ROLE_NAME
    )

    administrators = get_company_administrators(
        company
    )

    if admin_role:

        for administrator in administrators:

            existing = UserRole.query.filter_by(
                user_id=administrator.id,
                role_id=admin_role.id,
            ).first()

            if existing:
                continue

            db.session.add(
                UserRole(
                    user_id=administrator.id,
                    role_id=admin_role.id,
                    assigned_by=None,
                )
            )

            assigned_users += 1

    db.session.flush()

    return {
        "company_id": company.id,
        "company_name": getattr(
            company,
            "name",
            f"Company {company.id}",
        ),
        "permissions_created": permission_result["created"],
        "permissions_updated": permission_result["updated"],
        "added_permissions": added_permissions,
        "users_assigned": assigned_users,
    }


# ============================================================
# SYNCHRONIZE ALL COMPANIES
# ============================================================

def sync_all_company_roles():
    """
    Synchronize RBAC for every company.
    """

    try:

        permission_result = seed_permissions()

        companies = Company.query.order_by(
            Company.id.asc()
        ).all()

        results = []

        total_added_permissions = 0
        total_assigned_users = 0

        for company in companies:

            result = sync_company_roles(
                company
            )

            results.append(
                result
            )

            total_added_permissions += (
                result["added_permissions"]
            )

            total_assigned_users += (
                result["users_assigned"]
            )

        db.session.commit()

        return {
            "permissions_created":
                permission_result["created"],

            "permissions_updated":
                permission_result["updated"],

            "companies":
                len(companies),

            "permissions_attached":
                total_added_permissions,

            "users_assigned":
                total_assigned_users,

            "company_results":
                results,
        }

    except Exception:

        db.session.rollback()

        raise


# ============================================================
# SEED ALL RBAC
# ============================================================

def seed_all_rbac():
    """
    Complete RBAC initialization.

    Safe to run repeatedly.

    Creates and synchronizes:

        permissions
        roles
        role_permissions
        user_roles
    """

    try:

        # ====================================================
        # GLOBAL PERMISSIONS
        # ====================================================

        permission_result = seed_permissions()

        permission_map = get_permission_map()

        # ====================================================
        # COMPANIES
        # ====================================================

        companies = Company.query.order_by(
            Company.id.asc()
        ).all()

        # ====================================================
        # COUNTERS
        # ====================================================

        roles_created = 0
        permissions_attached = 0
        users_assigned = 0

        company_results = []

        # ====================================================
        # PROCESS EACH COMPANY
        # ====================================================

        for company in companies:

            company_roles_created = 0
            company_permissions_attached = 0
            company_users_assigned = 0

            # =================================================
            # CREATE / SYNC ROLES
            # =================================================

            for role_name, role_data in DEFAULT_ROLES.items():

                role = Role.query.filter_by(
                    company_id=company.id,
                    name=role_name,
                ).first()

                # ---------------------------------------------
                # CREATE ROLE
                # ---------------------------------------------

                if role is None:

                    role = Role(
                        company_id=company.id,
                        name=role_name,
                        description=role_data["description"],
                        is_system_role=False,
                        is_active=True,
                    )

                    db.session.add(
                        role
                    )

                    db.session.flush()

                    roles_created += 1
                    company_roles_created += 1

                else:

                    # -----------------------------------------
                    # UPDATE ROLE
                    # -----------------------------------------

                    if role.description != (
                        role_data["description"]
                    ):

                        role.description = (
                            role_data["description"]
                        )

                    if not role.is_active:

                        role.is_active = True

                # =================================================
                # ATTACH PERMISSIONS
                # =================================================

                for permission_name in (
                    role_data["permissions"]
                ):

                    permission = permission_map.get(
                        permission_name
                    )

                    if permission is None:
                        continue

                    existing = RolePermission.query.filter_by(
                        role_id=role.id,
                        permission_id=permission.id,
                    ).first()

                    if existing:
                        continue

                    db.session.add(
                        RolePermission(
                            role_id=role.id,
                            permission_id=permission.id,
                        )
                    )

                    permissions_attached += 1
                    company_permissions_attached += 1

            # =================================================
            # COMPANY ADMINISTRATOR ROLE
            # =================================================

            company_admin_role = Role.query.filter_by(
                company_id=company.id,
                name=COMPANY_ADMIN_ROLE_NAME,
            ).first()

            if company_admin_role is None:

                raise RuntimeError(
                    f"Company Administrator role was not "
                    f"created for company {company.id}."
                )

            # =================================================
            # FIND COMPANY ADMINISTRATORS
            # =================================================

            administrators = get_company_administrators(
                company
            )

            # =================================================
            # ASSIGN USER ROLES
            # =================================================

            for administrator in administrators:

                existing_assignment = UserRole.query.filter_by(
                    user_id=administrator.id,
                    role_id=company_admin_role.id,
                ).first()

                if existing_assignment:
                    continue

                db.session.add(
                    UserRole(
                        user_id=administrator.id,
                        role_id=company_admin_role.id,
                        assigned_by=None,
                    )
                )

                users_assigned += 1
                company_users_assigned += 1

            # =================================================
            # COMPANY RESULT
            # =================================================

            company_results.append(
                {
                    "company_id": company.id,

                    "company_name": getattr(
                        company,
                        "name",
                        f"Company {company.id}",
                    ),

                    "roles_created":
                        company_roles_created,

                    "permissions_attached":
                        company_permissions_attached,

                    "users_assigned":
                        company_users_assigned,
                }
            )

        # ====================================================
        # COMMIT
        # ====================================================

        db.session.commit()

        # ====================================================
        # RETURN SUMMARY
        # ====================================================

        return {
            "permissions_created":
                permission_result["created"],

            "permissions_updated":
                permission_result["updated"],

            "companies":
                len(companies),

            "roles_created":
                roles_created,

            "permissions_attached":
                permissions_attached,

            "users_assigned":
                users_assigned,

            "company_results":
                company_results,
        }

    except Exception:

        db.session.rollback()

        raise
