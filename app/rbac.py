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
        "description": "Edit, and manage sales.",
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
# DEFAULT ROLE DEFINITIONS
# ============================================================

DEFAULT_ROLES = {

    # ========================================================
    # COMPANY ADMINISTRATOR
    # ========================================================

    "Company Administrator": {
        "description": (
            "Full access to all company operations and administration."
        ),
        "permissions": [
            permission["name"]
            for permission in PERMISSIONS
        ],
    },

    # ========================================================
    # SALES MANAGER
    # ========================================================

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

    # ========================================================
    # SALES STAFF
    # ========================================================

    "Sales Staff": {
        "description": (
            "Handle day-to-day sales operations."
        ),
        "permissions": [
            "view_dashboard",

            "view_products",
            "view_inventory",

            "view_sales",
            "manage_sales",

            "view_customers",
            "manage_customers",
        ],
    },

    # ========================================================
    # INVENTORY MANAGER
    # ========================================================

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

    # ========================================================
    # INVENTORY STAFF
    # ========================================================

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

    # ========================================================
    # PURCHASE MANAGER
    # ========================================================

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

    # ========================================================
    # PURCHASE STAFF
    # ========================================================

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

    # ========================================================
    # ACCOUNTANT
    # ========================================================

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

    # ========================================================
    # PRODUCTION MANAGER
    # ========================================================

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

    # ========================================================
    # PRODUCTION STAFF
    # ========================================================

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

    # ========================================================
    # CUSTOM ROLE
    # ========================================================

    "Custom Role": {
        "description": (
            "Custom company role with configurable permissions."
        ),
        "permissions": [
            "view_dashboard",
        ],
    },
}


# ============================================================
# CREATE / SYNCHRONIZE GLOBAL PERMISSIONS
# ============================================================

def seed_permissions():
    """
    Create and synchronize all platform permissions.

    Permissions are global and are NOT tied to a company.
    """

    created = 0
    updated = 0

    for data in PERMISSIONS:

        permission = Permission.query.filter_by(
            name=data["name"]
        ).first()

        if permission is None:

            permission = Permission(
                name=data["name"],
                description=data["description"],
                permission_group=data["group"],
            )

            db.session.add(permission)

            created += 1

        else:

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
    """
    Return all permissions as:

        {
            "permission_name": Permission object
        }

    This avoids repeatedly querying the same permission.
    """

    return {
        permission.name: permission
        for permission in Permission.query.all()
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

    Missing RolePermission records are added.

    Existing RolePermission records are preserved.
    """

    if permission_map is None:
        permission_map = get_permission_map()

    # --------------------------------------------------------
    # FIND ROLE
    # --------------------------------------------------------

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

    added_permissions = 0

    for permission_name in permission_names:

        permission = permission_map.get(permission_name)

        if permission is None:
            continue

        existing = RolePermission.query.filter_by(
            role_id=role.id,
            permission_id=permission.id,
        ).first()

        if existing is not None:
            continue

        db.session.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id,
            )
        )

        added_permissions += 1

    return role, added_permissions


# ============================================================
# CREATE DEFAULT ROLES FOR COMPANY
# ============================================================

def seed_company_roles(company):
    """
    Create all default roles and attach their permissions.
    """

    permission_result = seed_permissions()

    permission_map = get_permission_map()

    roles = {}

    created_roles = 0
    added_permissions = 0

    for role_name, role_data in DEFAULT_ROLES.items():

        existing_role = Role.query.filter_by(
            company_id=company.id,
            name=role_name,
        ).first()

        if existing_role is None:
            created_roles += 1

        role, added = create_company_role(
            company=company,
            role_name=role_name,
            description=role_data["description"],
            permission_names=role_data["permissions"],
            permission_map=permission_map,
        )

        roles[role_name] = role

        added_permissions += added

    db.session.flush()

    return {
        "roles": roles,
        "permissions_created": permission_result["created"],
        "permissions_updated": permission_result["updated"],
        "roles_created": created_roles,
        "permissions_attached": added_permissions,
    }


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

    Does not create duplicate UserRole records.
    """

    existing = UserRole.query.filter_by(
        user_id=user.id,
        role_id=role.id,
    ).first()

    if existing is not None:
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

    return user_role


# ============================================================
# FIND COMPANY ADMINISTRATORS
# ============================================================

def get_company_administrators(company):
    """
    Find users belonging to the company who are marked
    as company administrators.

    This function supports the existing BizTrace
    is_company_admin flag.
    """

    return User.query.filter(
        User.company_id == company.id,
        User.is_company_admin.is_(True),
    ).all()


# ============================================================
# INITIALIZE COMPANY RBAC
# ============================================================

def initialize_company_rbac(
    company,
    administrator=None,
    assigned_by=None,
):
    """
    Fully initialize RBAC for one company.

    Creates:
        permissions
        roles
        role_permissions

    And optionally:
        user_roles
    """

    result = seed_company_roles(company)

    roles = result["roles"]

    # --------------------------------------------------------
    # ASSIGN SUPPLIED ADMINISTRATOR
    # --------------------------------------------------------

    if administrator is not None:

        admin_role = roles.get(
            "Company Administrator"
        )

        if admin_role is not None:

            assign_role_to_user(
                user=administrator,
                role=admin_role,
                assigned_by=assigned_by,
            )

    # --------------------------------------------------------
    # ASSIGN EXISTING COMPANY ADMINISTRATORS
    # --------------------------------------------------------
    #
    # This is important when migrating an existing database.
    #
    # --------------------------------------------------------

    admin_role = roles.get(
        "Company Administrator"
    )

    if admin_role is not None:

        administrators = get_company_administrators(
            company
        )

        for user in administrators:

            assign_role_to_user(
                user=user,
                role=admin_role,
                assigned_by=assigned_by,
            )

    db.session.flush()

    return result


# ============================================================
# SYNCHRONIZE ONE COMPANY
# ============================================================

def sync_company_roles(company):
    """
    Synchronize one existing company.

    This creates missing:
        roles
        role_permissions

    It also assigns Company Administrator to users
    marked as company administrators.
    """

    result = initialize_company_rbac(
        company=company,
    )

    db.session.commit()

    return {
        "company_id": company.id,
        "company_name": company.name,
        "roles_created": result["roles_created"],
        "permissions_created": result["permissions_created"],
        "permissions_updated": result["permissions_updated"],
        "permissions_attached": result["permissions_attached"],
    }


# ============================================================
# SYNCHRONIZE ALL COMPANIES
# ============================================================

def sync_all_company_roles():
    """
    Synchronize RBAC for every company.

    This is the function you should run when moving
    an existing BizTrace installation to a new database.

    It will populate:

        permissions
        roles
        role_permissions
        user_roles
    """

    # --------------------------------------------------------
    # GLOBAL PERMISSIONS
    # --------------------------------------------------------

    permission_result = seed_permissions()

    permission_map = get_permission_map()

    # --------------------------------------------------------
    # GET ALL COMPANIES
    # --------------------------------------------------------

    companies = Company.query.order_by(
        Company.id.asc()
    ).all()

    company_results = []

    total_roles_created = 0
    total_permissions_attached = 0
    total_admin_assignments = 0

    # --------------------------------------------------------
    # PROCESS EVERY COMPANY
    # --------------------------------------------------------

    for company in companies:

        roles_created = 0
        permissions_attached = 0
        admin_assignments = 0

        roles = {}

        # ----------------------------------------------------
        # CREATE / SYNCHRONIZE ROLES
        # ----------------------------------------------------

        for role_name, role_data in DEFAULT_ROLES.items():

            existing_role = Role.query.filter_by(
                company_id=company.id,
                name=role_name,
            ).first()

            if existing_role is None:
                roles_created += 1

            role, added = create_company_role(
                company=company,
                role_name=role_name,
                description=role_data["description"],
                permission_names=role_data["permissions"],
                permission_map=permission_map,
            )

            roles[role_name] = role

            permissions_attached += added

        db.session.flush()

        # ----------------------------------------------------
        # COMPANY ADMINISTRATORS
        # ----------------------------------------------------

        admin_role = roles.get(
            "Company Administrator"
        )

        if admin_role is not None:

            administrators = get_company_administrators(
                company
            )

            for user in administrators:

                existing_user_role = UserRole.query.filter_by(
                    user_id=user.id,
                    role_id=admin_role.id,
                ).first()

                if existing_user_role is None:

                    assign_role_to_user(
                        user=user,
                        role=admin_role,
                    )

                    admin_assignments += 1

        # ----------------------------------------------------
        # COMPANY RESULT
        # ----------------------------------------------------

        company_results.append({
            "company_id": company.id,
            "company_name": company.name,
            "roles_created": roles_created,
            "permissions_attached": permissions_attached,
            "admin_assignments": admin_assignments,
        })

        total_roles_created += roles_created
        total_permissions_attached += permissions_attached
        total_admin_assignments += admin_assignments

    # --------------------------------------------------------
    # COMMIT EVERYTHING
    # --------------------------------------------------------

    db.session.commit()

    return {
        "permissions_created": permission_result["created"],
        "permissions_updated": permission_result["updated"],
        "roles_created": total_roles_created,
        "permissions_attached": total_permissions_attached,
        "admin_assignments": total_admin_assignments,
        "companies": company_results,
    }


# ============================================================
# COMPLETE RBAC SEED
# ============================================================

def seed_all_rbac():
    """
    Complete RBAC initialization.

    Use this when setting up a fresh database.

    It creates:

        1. Global permissions
        2. Company roles
        3. Role permissions
        4. Company administrator user roles
    """

    return sync_all_company_roles()


# ============================================================
# CHECK RBAC STATUS
# ============================================================

def get_rbac_status():
    """
    Return a simple RBAC database status.
    """

    return {
        "permissions": Permission.query.count(),
        "roles": Role.query.count(),
        "role_permissions": RolePermission.query.count(),
        "user_roles": UserRole.query.count(),
        "companies": Company.query.count(),
        "users": User.query.count(),
    }
