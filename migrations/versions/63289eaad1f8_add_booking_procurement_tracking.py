"""Add booking procurement tracking

Revision ID: 63289eaad1f8
Revises: e607ea425a0c
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "63289eaad1f8"
down_revision = "e607ea425a0c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "booking_items",
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "reserved_quantity",
                sa.Numeric(14, 3),
                nullable=False,
                server_default="0"
            )
        )

        batch_op.add_column(
            sa.Column(
                "procurement_quantity",
                sa.Numeric(14, 3),
                nullable=False,
                server_default="0"
            )
        )


def downgrade():
    with op.batch_alter_table(
        "booking_items",
        schema=None
    ) as batch_op:

        batch_op.drop_column("procurement_quantity")
        batch_op.drop_column("reserved_quantity")