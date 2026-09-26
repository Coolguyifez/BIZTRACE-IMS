"""separate purchases from bookings

Revision ID: 8ff319e78bc6
Revises: 709d4b0c25ea
Create Date: 2026-09-14 12:23:49.444922

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ff319e78bc6'
down_revision = '709d4b0c25ea'
branch_labels = None
depends_on = None


def upgrade():

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("purchases")
    }

    with op.batch_alter_table(
        "purchases",
        schema=None
    ) as batch_op:

        if "booking_id" in columns:
            batch_op.drop_column("booking_id")

        if "purchase_type" in columns:
            batch_op.drop_column("purchase_type")

        if "received_at" in columns:
            batch_op.drop_column("received_at")

        if "received_by" in columns:
            batch_op.drop_column("received_by")


def downgrade():

    with op.batch_alter_table(
        "purchases",
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "booking_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "purchase_type",
                sa.String(length=30),
                nullable=True
            )
        )

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