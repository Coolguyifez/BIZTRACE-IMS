"""Remove booking system

Revision ID: a0dedcf7ad65
Revises: 8ff319e78bc6
Create Date: 2026-09-14 17:58:58.821020

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "a0dedcf7ad65"
down_revision = "8ff319e78bc6"
branch_labels = None
depends_on = None


def upgrade():

    # =========================================================
    # Remove booking_id from sales
    #
    # SQLite requires batch mode when removing a column.
    # We do NOT explicitly drop the FK because the existing
    # database does not have a constraint with the expected name.
    # =========================================================

    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.drop_column("booking_id")

    # =========================================================
    # Remove booking_items table
    # =========================================================

    op.drop_table("booking_items")

    # =========================================================
    # Remove bookings table
    # =========================================================

    op.drop_table("bookings")


def downgrade():

    raise NotImplementedError(
        "The Booking system was intentionally removed. "
        "Restore the database from a backup if a rollback is required."
    )