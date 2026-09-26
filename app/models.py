from datetime import datetime, timezone
from uuid import uuid4
from decimal import Decimal

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


# =========================================================
# COMPANY
# =========================================================

class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    qr_code = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        default=lambda: uuid4().hex
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )


    email = db.Column(
        db.String(150),
        nullable=True
    )

    phone = db.Column(
        db.String(50),
        nullable=True
    )

    address = db.Column(
        db.String(250),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    users = db.relationship(
        "User",
        backref="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    categories = db.relationship(
        "Category",
        backref="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    products = db.relationship(
        "Product",
        backref="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    customers = db.relationship(
        "Customer",
        backref="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    suppliers = db.relationship(
        "Supplier",
        backref="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    inventory_transactions = db.relationship(
        "InventoryTransaction",
        backref="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    roles = db.relationship(
        "Role",
        back_populates="company",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Company {self.name}>"



# ============================================================
# RBAC — PERMISSIONS
# ============================================================

class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    description = db.Column(
        db.String(255),
        nullable=True
    )

    permission_group = db.Column(
        db.String(50),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    role_permissions = db.relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Permission {self.name}>"



# ============================================================
# RBAC — ROLES
# ============================================================

class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.String(255),
        nullable=True
    )

    is_system_role = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    company = db.relationship(
        "Company",
        back_populates="roles"
    )

    role_permissions = db.relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    user_roles = db.relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "name",
            name="uq_company_role_name"
        ),
    )

    def __repr__(self):
        return f"<Role {self.name}>"


# ============================================================
# RBAC — ROLE PERMISSIONS
# ============================================================

class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id"),
        nullable=False
    )

    permission_id = db.Column(
        db.Integer,
        db.ForeignKey("permissions.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    role = db.relationship(
        "Role",
        back_populates="role_permissions"
    )

    permission = db.relationship(
        "Permission",
        back_populates="role_permissions"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permission"
        ),
    )

# ============================================================
# RBAC — USER ROLES
# ============================================================

class UserRole(db.Model):
    __tablename__ = "user_roles"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id"),
        nullable=False
    )

    assigned_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    assigned_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="user_roles"
    )

    role = db.relationship(
        "Role",
        back_populates="user_roles"
    )

    assigned_by_user = db.relationship(
        "User",
        foreign_keys=[assigned_by]
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "role_id",
            name="uq_user_role"
        ),
    )

    def __repr__(self):
        return f"<UserRole user={self.user_id} role={self.role_id}>"


# =========================================================
# USER
# =========================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=True
    )

    username = db.Column(
        db.String(80),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        default="Staff",
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    theme = db.Column(
        db.String(20),
        default="system",
        nullable=False
    )

    notification_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    browser_notification_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    email_notification_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    sound_notification_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    success_sound_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    system_sound_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )


    error_sound_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    low_stock_sound_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    gross_loss_sound_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    net_loss_sound_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    user_roles = db.relationship(
        "UserRole",
        foreign_keys="UserRole.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

    @property
    def is_system_admin(self):
        return (
                self.role == "System Administrator"
                and self.company_id is None
        )

    @property
    def is_company_admin(self):
        return (
                self.role == "Company Administrator"
                and self.company_id is not None
        )

    def has_permission(self, permission_name):
        """
        Check whether the user has a specific permission.
        System Administrators have unrestricted access.
        """

        if self.is_system_admin:
            return True

        if not self.is_active:
            return False

        if self.company_id is None:
            return False

        permission_exists = (
            db.session.query(Permission.id)
            .join(
                RolePermission,
                RolePermission.permission_id == Permission.id
            )
            .join(
                Role,
                Role.id == RolePermission.role_id
            )
            .join(
                UserRole,
                UserRole.role_id == Role.id
            )
            .filter(
                UserRole.user_id == self.id,
                Permission.name == permission_name,
                Role.is_active.is_(True),
                Role.company_id == self.company_id
            )
            .first()
        )

        return permission_exists is not None

    def has_any_permission(self, *permission_names):
        """
        Return True if the user has at least one
        of the supplied permissions.
        """

        if self.is_system_admin:
            return True

        return any(
            self.has_permission(permission)
            for permission in permission_names
        )

    def has_all_permissions(self, *permission_names):
        """
        Return True only if the user has every
        supplied permission.
        """

        if self.is_system_admin:
            return True

        return all(
            self.has_permission(permission)
            for permission in permission_names
        )



    def __repr__(self):
        return f"<User {self.username}>"


# =========================================================
# CATEGORY
# =========================================================

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.String(250),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    products = db.relationship(
        "Product",
        backref="category",
        lazy=True
    )

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "name",
            name="uq_category_company_name"
        ),
    )

    def __repr__(self):
        return f"<Category {self.name}>"


# =========================================================
# PRODUCT
# =========================================================

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    sku = db.Column(
        db.String(80),
        nullable=False
    )

    barcode = db.Column(
        db.String(100),
        nullable=True
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    unit = db.Column(
        db.String(30),
        default="piece",
        nullable=False
    )

    purchase_price = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    selling_price = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    # =====================================================
    # PHYSICAL STOCK
    # =====================================================

    quantity = db.Column(
        db.Numeric(14, 3),
        default=0,
        nullable=False
    )

    # =====================================================
    # RESERVED STOCK
    #
    # This remains independent of Booking.
    # It can be used by another reservation/order system.
    # =====================================================

    reserved_quantity = db.Column(
        db.Numeric(14, 3),
        default=0,
        nullable=False
    )

    # =====================================================
    # MINIMUM STOCK
    # =====================================================

    minimum_stock = db.Column(
        db.Numeric(14, 3),
        default=0,
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # =====================================================
    # INVENTORY TRANSACTIONS
    # =====================================================

    inventory_transactions = db.relationship(
        "InventoryTransaction",
        backref="product",
        lazy=True
    )

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "sku",
            name="uq_product_company_sku"
        ),
    )

    # =====================================================
    # LOW STOCK
    # =====================================================

    @property
    def is_low_stock(self):
        return self.quantity <= self.minimum_stock

    # =====================================================
    # AVAILABLE STOCK
    #
    # Physical quantity minus reserved quantity.
    # =====================================================

    @property
    def available_quantity(self):
        quantity = self.quantity or Decimal("0")
        reserved = self.reserved_quantity or Decimal("0")

        available = quantity - reserved

        return max(
            available,
            Decimal("0")
        )

    def __repr__(self):
        return f"<Product {self.name}>"


# =========================================================
# CUSTOMER
# =========================================================

class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        nullable=True
    )

    phone = db.Column(
        db.String(50),
        nullable=True
    )

    address = db.Column(
        db.String(250),
        nullable=True
    )

    opening_balance = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    credit_limit = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Customer {self.name}>"


# =========================================================
# SUPPLIER
# =========================================================

class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        nullable=True
    )

    phone = db.Column(
        db.String(50),
        nullable=True
    )

    address = db.Column(
        db.String(250),
        nullable=True
    )

    opening_balance = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Supplier {self.name}>"


# =========================================================
# INVENTORY TRANSACTION
# =========================================================

class InventoryTransaction(db.Model):
    __tablename__ = "inventory_transactions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    transaction_type = db.Column(
        db.String(50),
        nullable=False
    )

    quantity = db.Column(
        db.Numeric(14, 3),
        nullable=False
    )

    reference_type = db.Column(
        db.String(50),
        nullable=True
    )

    reference_id = db.Column(
        db.Integer,
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    def __repr__(self):
        return (
            f"<InventoryTransaction "
            f"{self.transaction_type} "
            f"{self.quantity}>"
        )


# =========================================================
# SALE
# =========================================================

class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id"),
        nullable=True
    )

    invoice_number = db.Column(
        db.String(80),
        nullable=False
    )

    sale_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    subtotal = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    discount = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    tax = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    total = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    paid_amount = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    balance = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="Completed",
        nullable=False
    )

    payment_status = db.Column(
        db.String(30),
        default="Unpaid",
        nullable=False
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # =====================================================
    # SALE ITEMS
    # =====================================================

    items = db.relationship(
        "SaleItem",
        backref="sale",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # =====================================================
    # PAYMENTS
    # =====================================================

    payments = db.relationship(
        "Payment",
        backref="sale",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = db.relationship(
        "Customer",
        backref="sales"
    )

    # =====================================================
    # CREATED BY
    # =====================================================

    created_by_user = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "invoice_number",
            name="uq_sale_company_invoice"
        ),
    )

    def __repr__(self):
        return f"<Sale {self.invoice_number}>"


# =========================================================
# SALE ITEM
# =========================================================

class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sales.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Numeric(14, 3),
        nullable=False
    )

    unit_price = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    discount = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    tax = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    total = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    product = db.relationship(
        "Product",
        backref="sale_items"
    )

    def __repr__(self):
        return f"<SaleItem {self.id}>"


# =========================================================
# PAYMENT
# =========================================================

class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sales.id"),
        nullable=True
    )

    purchase_id = db.Column(
        db.Integer,
        db.ForeignKey("purchases.id"),
        nullable=True
    )

    amount = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    method = db.Column(
        db.String(30),
        nullable=False
    )

    bank_name = db.Column(
        db.String(100),
        nullable=True
    )

    account_name = db.Column(
        db.String(150),
        nullable=True
    )

    account_number = db.Column(
        db.String(50),
        nullable=True
    )

    reference = db.Column(
        db.String(100),
        nullable=True
    )

    payment_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    def __repr__(self):
        return f"<Payment {self.amount}>"

# =========================================================
# CASH DEPOSIT
# =========================================================

class CashDeposit(db.Model):
    __tablename__ = "cash_deposits"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    amount = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    bank_name = db.Column(
        db.String(100),
        nullable=False
    )

    deposit_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    reference = db.Column(
        db.String(100),
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    company = db.relationship(
        "Company",
        backref=db.backref(
            "cash_deposits",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    created_by_user = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    def __repr__(self):
        return f"<CashDeposit {self.amount}>"


# =========================================================
# PURCHASE
# =========================================================

class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id"),
        nullable=True
    )

    purchase_number = db.Column(
        db.String(80),
        nullable=False
    )

    purchase_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # =====================================================
    # EXPECTED DELIVERY
    # =====================================================

    expected_delivery_date = db.Column(
        db.Date,
        nullable=True
    )

    # =====================================================
    # SUPPLIER REFERENCE
    # =====================================================

    supplier_invoice_number = db.Column(
        db.String(100),
        nullable=True
    )

    # =====================================================
    # FINANCIAL
    # =====================================================

    subtotal = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    discount = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    tax = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    total = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    paid_amount = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    balance = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = db.Column(
        db.String(30),
        default="Completed",
        nullable=False
    )

    payment_status = db.Column(
        db.String(30),
        default="Unpaid",
        nullable=False
    )

    # =====================================================
    # NOTES
    # =====================================================

    notes = db.Column(
        db.Text,
        nullable=True
    )

    # =====================================================
    # CREATED BY
    # =====================================================

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # =====================================================
    # PURCHASE ITEMS
    # =====================================================

    items = db.relationship(
        "PurchaseItem",
        backref="purchase",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # =====================================================
    # PAYMENTS
    # =====================================================

    payments = db.relationship(
        "Payment",
        backref="purchase",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # =====================================================
    # SUPPLIER
    # =====================================================

    supplier = db.relationship(
        "Supplier",
        backref="purchases"
    )

    # =====================================================
    # CREATED BY USER
    # =====================================================

    created_by_user = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "purchase_number",
            name="uq_purchase_company_number"
        ),
    )

    def __repr__(self):
        return f"<Purchase {self.purchase_number}>"


# =========================================================
# PURCHASE ITEM
# =========================================================

class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    purchase_id = db.Column(
        db.Integer,
        db.ForeignKey("purchases.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Numeric(14, 3),
        nullable=False
    )

    unit_cost = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    manufacturing_date = db.Column(
        db.Date,
        nullable=True
    )

    expiry_date = db.Column(
        db.Date,
        nullable=True
    )

    discount = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    tax = db.Column(
        db.Numeric(14, 2),
        default=0,
        nullable=False
    )

    total = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    product = db.relationship(
        "Product",
        backref="purchase_items"
    )

    def __repr__(self):
        return f"<PurchaseItem {self.id}>"


# =========================================================
# EXPENSE CATEGORY
# =========================================================

class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.String(250),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    expenses = db.relationship(
        "Expense",
        backref="category",
        lazy=True
    )

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "name",
            name="uq_expense_category_company_name"
        ),
    )

    def __repr__(self):
        return f"<ExpenseCategory {self.name}>"


# =========================================================
# EXPENSE
# =========================================================

class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("expense_categories.id"),
        nullable=False
    )

    expense_number = db.Column(
        db.String(80),
        nullable=False
    )

    description = db.Column(
        db.String(250),
        nullable=False
    )

    amount = db.Column(
        db.Numeric(14, 2),
        nullable=False
    )

    payment_method = db.Column(
        db.String(30),
        nullable=False
    )

    expense_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    reference = db.Column(
        db.String(100),
        nullable=True,
        unique=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    company = db.relationship(
        "Company",
        backref=db.backref(
            "expenses",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    created_by_user = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "expense_number",
            name="uq_expense_company_number"
        ),
    )

    def __repr__(self):
        return f"<Expense {self.expense_number}>"


# =========================================================
# NOTIFICATION
# =========================================================

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    category = db.Column(
        db.String(50),
        nullable=False,
        default="system"
    )

    priority = db.Column(
        db.String(20),
        nullable=False,
        default="normal"
    )

    sound = db.Column(
        db.String(50),
        nullable=True
    )

    reference_type = db.Column(
        db.String(50),
        nullable=True
    )

    reference_id = db.Column(
        db.Integer,
        nullable=True
    )

    link = db.Column(
        db.String(500),
        nullable=True
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    browser_sent = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    email_sent = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    dedupe_key = db.Column(
        db.String(255),
        nullable=True,
        unique=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    company = db.relationship(
        "Company",
        backref=db.backref(
            "notifications",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "notifications",
            lazy=True
        )
    )

    __table_args__ = (
        db.Index(
            "ix_notification_company_user",
            "company_id",
            "user_id"
        ),

        db.Index(
            "ix_notification_created_at",
            "created_at"
        ),

        db.Index(
            "ix_notification_unread",
            "company_id",
            "user_id",
            "is_read"
        ),
    )

    def __repr__(self):
        return f"<Notification {self.title}>"


# =========================================================
# PUSH SUBSCRIPTION
# =========================================================

class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    endpoint = db.Column(
        db.Text,
        nullable=False,
        unique=True
    )

    p256dh = db.Column(
        db.Text,
        nullable=False
    )

    auth = db.Column(
        db.Text,
        nullable=False
    )

    user_agent = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    company = db.relationship(
        "Company",
        backref=db.backref(
            "push_subscriptions",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "push_subscriptions",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    __table_args__ = (
        db.Index(
            "ix_push_subscription_user",
            "user_id"
        ),
    )

    def __repr__(self):
        return f"<PushSubscription {self.user_id}>"


class NotificationRecipient(db.Model):
    __tablename__ = "notification_recipients"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("notifications.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    read_at = db.Column(
        db.DateTime,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    notification = db.relationship(
        "Notification",
        backref=db.backref(
            "recipients",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    user = db.relationship(
        "User",
        backref="notification_recipients"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_notification_recipient"
        ),
    )

class CompanySetting(db.Model):
    __tablename__ = "company_settings"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False,
        unique=True
    )

    # ============================================================
    # CURRENCY
    # ============================================================

    currency_code = db.Column(
        db.String(10),
        default="NGN",
        nullable=False
    )

    currency_symbol = db.Column(
        db.String(10),
        default="₦",
        nullable=False
    )

    decimal_places = db.Column(
        db.Integer,
        default=2,
        nullable=False
    )

    currency_position = db.Column(
        db.String(10),
        default="before",
        nullable=False
    )

    # ============================================================
    # DATE & TIME
    # ============================================================

    timezone = db.Column(
        db.String(100),
        default="Africa/Lagos",
        nullable=False
    )

    date_format = db.Column(
        db.String(30),
        default="DD/MM/YYYY",
        nullable=False
    )

    time_format = db.Column(
        db.String(10),
        default="12h",
        nullable=False
    )

    week_starts = db.Column(
        db.String(10),
        default="Monday",
        nullable=False
    )

    # ============================================================
    # DOCUMENT NUMBERING
    # ============================================================

    invoice_prefix = db.Column(
        db.String(20),
        default="INV",
        nullable=False
    )

    purchase_prefix = db.Column(
        db.String(20),
        default="PUR",
        nullable=False
    )

    expense_prefix = db.Column(
        db.String(20),
        default="EXP",
        nullable=False
    )

    booking_prefix = db.Column(
        db.String(20),
        default="BOOK",
        nullable=False
    )

    number_length = db.Column(
        db.Integer,
        default=4,
        nullable=False
    )

    include_date = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    number_reset = db.Column(
        db.String(20),
        default="daily",
        nullable=False
    )

    # ============================================================
    # INVENTORY SETTINGS
    # ============================================================

    allow_negative_stock = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    reserve_stock = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    low_stock_notifications = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    stock_adjustment_requires_note = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    # ============================================================
    # RELATIONSHIP
    # ============================================================

    company = db.relationship(
        "Company",
        backref=db.backref(
            "settings",
            uselist=False,
            cascade="all, delete-orphan"
        )
    )

    def __repr__(self):
        return (
            f"<CompanySetting "
            f"company_id={self.company_id}>"
        )


class NotificationAssignment(db.Model):
    __tablename__ = "notification_assignments"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    notification_category = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    enabled = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    company = db.relationship(
        "Company",
        backref=db.backref(
            "notification_assignments",
            cascade="all, delete-orphan"
        )
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "notification_assignments",
            cascade="all, delete-orphan"
        )
    )

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "user_id",
            "notification_category",
            name="uq_notification_assignment"
        ),
    )

class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)

    maintenance_mode = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    maintenance_message = db.Column(
        db.Text,
        nullable=True
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )