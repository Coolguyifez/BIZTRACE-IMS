"""add booking fulfillment and sale relationship

Revision ID: d10934d0ec9d
Revises: 253ef2c5ea54
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d10934d0ec9d"
down_revision = "253ef2c5ea54"
branch_labels = None
depends_on = None


def upgrade():
    # ============================================================
    # SALES
    # Add booking_id so one booking can create one sale.
    # ============================================================

    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "booking_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.create_foreign_key(
            "fk_sales_booking_id",
            "bookings",
            ["booking_id"],
            ["id"]
        )

        batch_op.create_unique_constraint(
            "uq_sales_booking_id",
            ["booking_id"]
        )

    # ============================================================
    # BOOKINGS
    # Add fulfillment tracking.
    # ============================================================

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "fulfilled_at",
                sa.DateTime(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "fulfilled_by",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.create_foreign_key(
            "fk_bookings_fulfilled_by",
            "users",
            ["fulfilled_by"],
            ["id"]
        )


def downgrade():
    # ============================================================
    # BOOKINGS
    # ============================================================

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_bookings_fulfilled_by",
            type_="foreignkey"
        )

        batch_op.drop_column("fulfilled_by")
        batch_op.drop_column("fulfilled_at")

    # ============================================================
    # SALES
    # ============================================================

    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_sales_booking_id",
            type_="unique"
        )

        batch_op.drop_constraint(
            "fk_sales_booking_id",
            type_="foreignkey"
        )

        batch_op.drop_column("booking_id")