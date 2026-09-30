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
# SEED GLOBAL PERMISSIONS
# ============================================================

def seed_permissions():
    """
    Create and synchronize all global permissions.

    Existing permissions are never duplicated.

    Existing descriptions/groups are updated when changed.

    Returns:
        {
            "created": int,
            "updated": int
        }
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

    # Flush so newly-created permissions have IDs available.
    db.session.flush()

    return {
        "created": created,
        "updated": updated,
    }


# ============================================================
# PERMISSION MAP
# ============================================================

def get_permission_map():
    """
    Return all permissions indexed by name.

    Example:

        {
            "view_dashboard": Permission(...),
            "manage_products": Permission(...),
        }
    """

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
    Create or synchronize one company role.

    Existing role permissions are preserved.

    Missing permissions are added.
    """

    # --------------------------------------------------------
    # PERMISSION MAP
    # --------------------------------------------------------

    if permission_map is None:
        permission_map = get_permission_map()

    # --------------------------------------------------------
    # FIND ROLE
    # --------------------------------------------------------

    role = Role.query.filter_by(
        company_id=company.id,
        name=role_name
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

    return role


# ============================================================
# SEED COMPANY ROLES
# ============================================================

def seed_company_roles(company):
    """
    Create and synchronize all default roles
    for one company.
    """

    # --------------------------------------------------------
    # MAKE SURE PERMISSIONS EXIST
    # --------------------------------------------------------

    seed_permissions()

    permission_map = get_permission_map()

    roles = {}

    # --------------------------------------------------------
    # CREATE / SYNCHRONIZE ROLES
    # --------------------------------------------------------

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
    Assign a role to a user without duplicates.

    Does not commit the transaction.
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
# GET COMPANY ADMINISTRATORS
# ============================================================

def get_company_administrators(company):
    """
    Find users who are marked as company administrators.

    This assumes the User model contains:

        is_company_admin

    and:

        company_id
    """

    return User.query.filter_by(
        company_id=company.id,
        is_company_admin=True,
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
    Initialize RBAC for a company.

    Creates all default roles.

    Creates missing permissions.

    Adds missing permissions to roles.

    Optionally assigns the Company Administrator
    role to the supplied administrator.
    """

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

    db.session.flush()

    return roles


# ============================================================
# SYNCHRONIZE ONE COMPANY
# ============================================================

def sync_company_roles(company):
    """
    Synchronize one company's RBAC configuration.

    This:

    - Creates missing roles
    - Updates role descriptions
    - Creates missing RolePermission records
    - Preserves existing permissions
    - Assigns Company Administrator to users marked
      is_company_admin=True

    Returns a summary.
    """

    # --------------------------------------------------------
    # GLOBAL PERMISSIONS
    # --------------------------------------------------------

    permission_result = seed_permissions()

    permission_map = get_permission_map()

    created_roles = 0
    added_permissions = 0
    assigned_users = 0

    # --------------------------------------------------------
    # DEFAULT ROLES
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

            # ------------------------------------------------
            # UPDATE ROLE DESCRIPTION
            # ------------------------------------------------

            if role.description != role_data["description"]:

                role.description = (
                    role_data["description"]
                )

            # ------------------------------------------------
            # REACTIVATE DEFAULT ROLE
            # ------------------------------------------------

            if not role.is_active:

                role.is_active = True

        # ----------------------------------------------------
        # ADD MISSING PERMISSIONS
        # ----------------------------------------------------

        for permission_name in role_data["permissions"]:

            permission = permission_map.get(
                permission_name
            )

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
                    permission_id=permission.id,
                )
            )

            added_permissions += 1

    # --------------------------------------------------------
    # FIND COMPANY ADMIN ROLE
    # --------------------------------------------------------

    company_admin_role = Role.query.filter_by(
        company_id=company.id,
        name="Company Administrator",
    ).first()

    # --------------------------------------------------------
    # ASSIGN COMPANY ADMIN ROLE
    # --------------------------------------------------------

    if company_admin_role:

        administrators = get_company_administrators(
            company
        )

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

            assigned_users += 1

    # --------------------------------------------------------
    # FLUSH
    # --------------------------------------------------------

    db.session.flush()

    return {
        "company_id": company.id,
        "company_name": getattr(
            company,
            "name",
            f"Company {company.id}"
        ),
        "permissions_created":
            permission_result["created"],
        "permissions_updated":
            permission_result["updated"],
        "created_roles":
            created_roles,
        "added_permissions":
            added_permissions,
        "users_assigned":
            assigned_users,
    }


# ============================================================
# SYNCHRONIZE ALL COMPANIES
# ============================================================

def sync_all_company_roles():
    """
    Synchronize RBAC for every company.

    This is useful when new permissions or roles are added
    after companies already exist.
    """

    # --------------------------------------------------------
    # MAKE SURE GLOBAL PERMISSIONS EXIST
    # --------------------------------------------------------

    permission_result = seed_permissions()

    permission_map = get_permission_map()

    companies = Company.query.order_by(
        Company.id.asc()
    ).all()

    results = []

    total_created_roles = 0
    total_added_permissions = 0
    total_assigned_users = 0

    # --------------------------------------------------------
    # LOOP THROUGH COMPANIES
    # --------------------------------------------------------

    for company in companies:

        result = sync_company_roles(
            company
        )

        results.append(result)

        total_created_roles += (
            result["created_roles"]
        )

        total_added_permissions += (
            result["added_permissions"]
        )

        total_assigned_users += (
            result["users_assigned"]
        )

    return {
        "permissions_created":
            permission_result["created"],

        "permissions_updated":
            permission_result["updated"],

        "companies":
            len(companies),

        "roles_created":
            total_created_roles,

        "permissions_attached":
            total_added_permissions,

        "users_assigned":
            total_assigned_users,

        "company_results":
            results,
    }


# ============================================================
# SEED ALL RBAC
# ============================================================

def seed_all_rbac():
    """
    Complete RBAC initialization and synchronization.

    This is the function called by:

        flask rbac-sync

    It performs the following:

        1. Creates global permissions.
        2. Updates existing permissions.
        3. Creates missing company roles.
        4. Adds missing role permissions.
        5. Assigns Company Administrator roles.
        6. Commits everything as one transaction.

    Safe to run repeatedly.
    """

    try:

        # ----------------------------------------------------
        # START TRANSACTION
        # ----------------------------------------------------

        # Make sure all permissions exist first.
        permission_result = seed_permissions()

        permission_map = get_permission_map()

        # ----------------------------------------------------
        # GET ALL COMPANIES
        # ----------------------------------------------------

        companies = Company.query.order_by(
            Company.id.asc()
        ).all()

        # ----------------------------------------------------
        # COUNTERS
        # ----------------------------------------------------

        roles_created = 0
        permissions_attached = 0
        users_assigned = 0

        company_results = []

        # ----------------------------------------------------
        # PROCESS EACH COMPANY
        # ----------------------------------------------------

        for company in companies:

            created_roles_for_company = 0
            added_permissions_for_company = 0
            assigned_users_for_company = 0

            # ------------------------------------------------
            # DEFAULT ROLES
            # ------------------------------------------------

            for role_name, role_data in DEFAULT_ROLES.items():

                role = Role.query.filter_by(
                    company_id=company.id,
                    name=role_name
                ).first()

                # --------------------------------------------
                # CREATE ROLE
                # --------------------------------------------

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

                    roles_created += 1
                    created_roles_for_company += 1

                else:

                    # ----------------------------------------
                    # UPDATE DESCRIPTION
                    # ----------------------------------------

                    if role.description != (
                        role_data["description"]
                    ):

                        role.description = (
                            role_data["description"]
                        )

                    # ----------------------------------------
                    # REACTIVATE DEFAULT ROLE
                    # ----------------------------------------

                    if not role.is_active:

                        role.is_active = True

                # ------------------------------------------------
                # ATTACH ROLE PERMISSIONS
                # ------------------------------------------------

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
                        permission_id=permission.id
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
                    added_permissions_for_company += 1

            # ------------------------------------------------
            # COMPANY ADMIN ROLE
            # ------------------------------------------------

            company_admin_role = Role.query.filter_by(
                company_id=company.id,
                name="Company Administrator",
            ).first()

            # ------------------------------------------------
            # COMPANY ADMIN USERS
            # ------------------------------------------------

            administrators = User.query.filter_by(
                company_id=company.id,
                is_company_admin=True,
            ).all()

            if company_admin_role:

                for administrator in administrators:

                    existing_assignment = (
                        UserRole.query.filter_by(
                            user_id=administrator.id,
                            role_id=company_admin_role.id,
                        ).first()
                    )

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
                    assigned_users_for_company += 1

            # ------------------------------------------------
            # COMPANY RESULT
            # ------------------------------------------------

            company_results.append({
                "company_id": company.id,

                "company_name": getattr(
                    company,
                    "name",
                    f"Company {company.id}"
                ),

                "roles_created":
                    created_roles_for_company,

                "permissions_attached":
                    added_permissions_for_company,

                "users_assigned":
                    assigned_users_for_company,
            })

        # ----------------------------------------------------
        # COMMIT EVERYTHING
        # ----------------------------------------------------

        db.session.commit()

        # ----------------------------------------------------
        # RETURN SUMMARY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ROLLBACK
        # ----------------------------------------------------

        db.session.rollback()

        raise
