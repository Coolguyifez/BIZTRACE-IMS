from .extensions import db
from .models import (
    Company,
    User,
    Permission,
    Role,
    RolePermission,
    UserRole
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
        "description": "View sales records.",
        "group": "Sales",
    },

    {
        "name": "manage_sales",
        "description": "Create, edit, and manage sales.",
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

        "description":
            "Full access to all company operations and administration.",

        "permissions": [
            permission["name"]
            for permission in PERMISSIONS
        ],
    },


    # ========================================================
    # SALES MANAGER
    # ========================================================

    "Sales Manager": {

        "description":
            "Manage sales operations and customer records.",

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

        "description":
            "Handle day-to-day sales operations.",

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

        "description":
            "Manage products, categories, and inventory.",

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

        "description":
            "Handle inventory operations.",

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

        "description":
            "Manage purchases and supplier operations.",

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

        "description":
            "Handle day-to-day purchasing operations.",

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

        "description":
            "Manage financial records and financial operations.",

        "permissions": [
            "view_dashboard",

            "view_sales",

            "view_purchases",

            "view_expenses",
            "manage_expenses",

            "view_payments",
            "manage_payments",

            # Cash deposits
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

        "description":
            "Manage production operations.",

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

        "description":
            "Handle production operations.",

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

        "description":
            "Custom company role with configurable permissions.",

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
    Create all platform-defined permissions.

    Existing permissions are NOT duplicated.

    Existing permissions are also updated if their
    description or permission group has changed.

    Returns a dictionary containing:
        created
        updated
    """

    created = 0
    updated = 0

    for data in PERMISSIONS:

        permission = Permission.query.filter_by(
            name=data["name"]
        ).first()

        # ----------------------------------------------------
        # CREATE MISSING PERMISSION
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
        # UPDATE EXISTING PERMISSION
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

    db.session.commit()

    return {
        "created": created,
        "updated": updated,
    }


# ============================================================
# CREATE ROLE FOR COMPANY
# ============================================================

def create_company_role(
    company,
    role_name,
    description,
    permission_names
):
    """
    Create a role for a company and attach permissions.

    Existing roles are reused.

    Missing permissions are automatically added
    to the existing role.
    """

    # --------------------------------------------------------
    # FIND EXISTING ROLE
    # --------------------------------------------------------

    role = Role.query.filter_by(
        company_id=company.id,
        name=role_name
    ).first()

    # --------------------------------------------------------
    # CREATE ROLE IF IT DOES NOT EXIST
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

        # Update description if it changed.
        if role.description != description:

            role.description = description

        # Make sure the role remains active.
        if not role.is_active:

            role.is_active = True

    # --------------------------------------------------------
    # ATTACH PERMISSIONS
    # --------------------------------------------------------

    for permission_name in permission_names:

        permission = Permission.query.filter_by(
            name=permission_name
        ).first()

        # Permission should already exist because
        # seed_permissions() runs before this function.
        if permission is None:
            continue

        existing = RolePermission.query.filter_by(
            role_id=role.id,
            permission_id=permission.id
        ).first()

        # Already attached.
        if existing:
            continue

        # Add missing permission.
        db.session.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id
            )
        )

    return role


# ============================================================
# CREATE DEFAULT ROLES FOR COMPANY
# ============================================================

def seed_company_roles(company):
    """
    Create all default roles for a company.

    This function also synchronizes missing permissions
    for roles that already exist.
    """

    # --------------------------------------------------------
    # MAKE SURE GLOBAL PERMISSIONS EXIST
    # --------------------------------------------------------

    seed_permissions()

    roles = {}

    # --------------------------------------------------------
    # CREATE / UPDATE ALL DEFAULT ROLES
    # --------------------------------------------------------

    for role_name, role_data in DEFAULT_ROLES.items():

        role = create_company_role(
            company=company,
            role_name=role_name,
            description=role_data["description"],
            permission_names=role_data["permissions"],
        )

        roles[role_name] = role

    db.session.commit()

    return roles


# ============================================================
# SYNCHRONIZE EXISTING COMPANY ROLES
# ============================================================

def sync_company_roles(company):
    """
    Synchronize an existing company's roles with
    DEFAULT_ROLES.

    This is important when new permissions are added
    to the application after companies already exist.

    Example:

        view_cash_deposits
        manage_cash_deposits

    will automatically be added to the appropriate
    existing roles.

    Existing permissions are NOT removed.

    Returns the number of newly-created
    RolePermission records.
    """

    # --------------------------------------------------------
    # MAKE SURE ALL GLOBAL PERMISSIONS EXIST
    # --------------------------------------------------------

    seed_permissions()

    added_permissions = 0
    created_roles = 0

    # --------------------------------------------------------
    # LOOP THROUGH DEFAULT ROLES
    # --------------------------------------------------------

    for role_name, role_data in DEFAULT_ROLES.items():

        role = Role.query.filter_by(
            company_id=company.id,
            name=role_name
        ).first()

        # ----------------------------------------------------
        # CREATE MISSING ROLE
        # ----------------------------------------------------

        if role is None:

            role = Role(
                company_id=company.id,
                name=role_name,
                description=role_data["description"],
                is_system_role=False,
                is_active=True,
            )

            db.session.add(role)

            db.session.flush()

            created_roles += 1

        else:

            # Update role description if needed.
            if role.description != role_data["description"]:

                role.description = role_data["description"]

            # Ensure default roles remain active.
            if not role.is_active:

                role.is_active = True

        # ----------------------------------------------------
        # ADD MISSING PERMISSIONS
        # ----------------------------------------------------

        for permission_name in role_data["permissions"]:

            permission = Permission.query.filter_by(
                name=permission_name
            ).first()

            if permission is None:
                continue

            existing = RolePermission.query.filter_by(
                role_id=role.id,
                permission_id=permission.id
            ).first()

            if existing:
                continue

            db.session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id
                )
            )

            added_permissions += 1

    # --------------------------------------------------------
    # COMMIT
    # --------------------------------------------------------

    db.session.commit()

    return {
        "created_roles": created_roles,
        "added_permissions": added_permissions,
    }


# ============================================================
# SYNCHRONIZE ALL COMPANIES
# ============================================================

def sync_all_company_roles():
    """
    Synchronize RBAC for every company in the database.

    This should be used when new permissions are added
    to the application after companies already exist.

    Returns a summary dictionary.
    """

    # --------------------------------------------------------
    # MAKE SURE GLOBAL PERMISSIONS EXIST FIRST
    # --------------------------------------------------------

    permission_result = seed_permissions()

    results = []

    # --------------------------------------------------------
    # LOOP THROUGH ALL COMPANIES
    # --------------------------------------------------------

    companies = Company.query.order_by(
        Company.id.asc()
    ).all()

    for company in companies:

        result = sync_company_roles(company)

        results.append({
            "company_id": company.id,
            "company_name": company.name,
            "created_roles": result["created_roles"],
            "added_permissions": result["added_permissions"],
        })

    return {
        "permissions_created":
            permission_result["created"],

        "permissions_updated":
            permission_result["updated"],

        "companies":
            results,
    }


# ============================================================
# ASSIGN ROLE TO USER
# ============================================================

def assign_role_to_user(
    user,
    role,
    assigned_by=None
):
    """
    Assign a role to a user without creating duplicates.

    The caller is responsible for committing the transaction.
    """

    existing = UserRole.query.filter_by(
        user_id=user.id,
        role_id=role.id
    ).first()

    if existing:

        return existing

    user_role = UserRole(
        user_id=user.id,
        role_id=role.id,
        assigned_by=(
            assigned_by.id
            if assigned_by
            else None
        ),
    )

    db.session.add(user_role)

    return user_role


# ============================================================
# INITIALIZE COMPANY RBAC
# ============================================================

def initialize_company_rbac(
    company,
    administrator=None,
    assigned_by=None
):
    """
    Initialize RBAC for a company.

    Creates all default roles.

    Creates all missing permissions.

    Adds all missing permissions to the
    appropriate company roles.

    Optionally assigns the Company Administrator
    role to the supplied administrator.

    The caller is responsible for committing
    the administrator assignment.
    """

    # --------------------------------------------------------
    # CREATE / SYNCHRONIZE ROLES
    # --------------------------------------------------------

    roles = seed_company_roles(company)

    # --------------------------------------------------------
    # ASSIGN COMPANY ADMINISTRATOR
    # --------------------------------------------------------

    if administrator is not None:

        admin_role = roles.get(
            "Company Administrator"
        )

        if admin_role:

            assign_role_to_user(
                user=administrator,
                role=admin_role,
                assigned_by=assigned_by,
            )

            db.session.commit()

    return roles