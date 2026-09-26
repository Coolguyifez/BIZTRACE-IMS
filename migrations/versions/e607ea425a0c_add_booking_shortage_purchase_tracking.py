"""Add booking shortage purchase tracking

Revision ID: e607ea425a0c
Revises: d10934d0ec9d
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e607ea425a0c"
down_revision = "d10934d0ec9d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "purchases",
        schema=None
    ) as batch_op:

        # -------------------------------------------------
        # BOOKING LINK
        # -------------------------------------------------

        batch_op.add_column(
            sa.Column(
                "booking_id",
                sa.Integer(),
                nullable=True
            )
        )

        # -------------------------------------------------
        # PURCHASE TYPE
        # -------------------------------------------------

        batch_op.add_column(
            sa.Column(
                "purchase_type",
                sa.String(length=30),
                nullable=False,
                server_default="Normal"
            )
        )

        # -------------------------------------------------
        # RECEIVING INFORMATION
        # -------------------------------------------------

        batch_op.add_column(
            sa.Column(
                "received_at",
                sa.DateTime(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "received_by",
                sa.Integer(),
                nullable=True
            )
        )

        # -------------------------------------------------
        # NAMED FOREIGN KEYS
        # -------------------------------------------------

        batch_op.create_foreign_key(
            "fk_purchases_booking_id_bookings",
            "bookings",
            ["booking_id"],
            ["id"]
        )

        batch_op.create_foreign_key(
            "fk_purchases_received_by_users",
            "users",
            ["received_by"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table(
        "purchases",
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            "fk_purchases_received_by_users",
            type_="foreignkey"
        )

        batch_op.drop_constraint(
            "fk_purchases_booking_id_bookings",
            type_="foreignkey"
        )

        batch_op.drop_column(
            "received_by"
        )

        batch_op.drop_column(
            "received_at"
        )

        batch_op.drop_column(
            "purchase_type"
        )

        batch_op.drop_column(
            "booking_id"
        )