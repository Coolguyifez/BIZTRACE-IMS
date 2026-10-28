"""Add services and support service sale items

Revision ID: aba685b9a601
Revises: 3d8ce651e61a
Create Date: 2026-10-28 13:42:19.316272

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aba685b9a601"
down_revision = "3d8ce651e61a"
branch_labels = None
depends_on = None


def upgrade():
    # ============================================================
    # 1. CREATE SERVICES TABLE
    # ============================================================

    op.create_table(
        "services",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False
        ),

        sa.Column(
            "service_code",
            sa.String(length=80),
            nullable=False
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True
        ),

        sa.Column(
            "price",
            sa.Numeric(precision=14, scale=2),
            nullable=False
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"]
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "company_id",
            "service_code",
            name="uq_service_company_code"
        )
    )

    with op.batch_alter_table("services", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_services_company_id"),
            ["company_id"],
            unique=False
        )

    # ============================================================
    # 2. ADD NEW SALE ITEM COLUMNS AS NULLABLE FIRST
    #
    # Existing sale_items already exist, so these columns cannot
    # initially be NOT NULL.
    # ============================================================

    with op.batch_alter_table("sale_items", schema=None) as batch_op:

        batch_op.add_column(
            sa.Column(
                "item_type",
                sa.String(length=20),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "service_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "item_name",
                sa.String(length=150),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "item_code",
                sa.String(length=100),
                nullable=True
            )
        )

        batch_op.alter_column(
            "product_id",
            existing_type=sa.INTEGER(),
            nullable=True
        )

    # ============================================================
    # 3. BACKFILL EXISTING SALE ITEMS
    #
    # Every existing SaleItem was a product sale before services
    # were introduced.
    #
    # Therefore:
    #   item_type = product
    #   item_name = current Product.name
    #   item_code = current Product.sku
    #   service_id = NULL
    #
    # The historical name/code are copied into SaleItem so future
    # product edits do not change old sales.
    # ============================================================

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE sale_items
            SET
                item_type = 'product',
                item_name = (
                    SELECT products.name
                    FROM products
                    WHERE products.id = sale_items.product_id
                ),
                item_code = (
                    SELECT products.sku
                    FROM products
                    WHERE products.id = sale_items.product_id
                )
            """
        )
    )

    # ============================================================
    # 4. ADD SERVICE FOREIGN KEY
    # ============================================================

    with op.batch_alter_table("sale_items", schema=None) as batch_op:

        batch_op.create_foreign_key(
            "fk_sale_items_service_id_services",
            "services",
            ["service_id"],
            ["id"]
        )

    # ============================================================
    # 5. MAKE REQUIRED HISTORICAL FIELDS NON-NULL
    #
    # At this point all existing sale items should have been
    # populated from their corresponding products.
    # ============================================================

    with op.batch_alter_table("sale_items", schema=None) as batch_op:

        batch_op.alter_column(
            "item_type",
            existing_type=sa.String(length=20),
            nullable=False
        )

        batch_op.alter_column(
            "item_name",
            existing_type=sa.String(length=150),
            nullable=False
        )


def downgrade():

    # ============================================================
    # 1. REMOVE SERVICE FOREIGN KEY AND NEW SALE ITEM FIELDS
    # ============================================================

    with op.batch_alter_table("sale_items", schema=None) as batch_op:

        batch_op.drop_constraint(
            "fk_sale_items_service_id_services",
            type_="foreignkey"
        )

        batch_op.alter_column(
            "product_id",
            existing_type=sa.INTEGER(),
            nullable=False
        )

        batch_op.drop_column("item_code")
        batch_op.drop_column("item_name")
        batch_op.drop_column("service_id")
        batch_op.drop_column("item_type")

    # ============================================================
    # 2. REMOVE SERVICES TABLE
    # ============================================================

    with op.batch_alter_table("services", schema=None) as batch_op:

        batch_op.drop_index(
            batch_op.f("ix_services_company_id")
        )

    op.drop_table("services")