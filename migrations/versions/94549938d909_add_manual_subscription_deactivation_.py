"""Add manual subscription deactivation controls

Revision ID: 94549938d909
Revises: aba685b9a601
Create Date: 2026-10-29 14:04:18.831828

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "94549938d909"
down_revision = "aba685b9a601"
branch_labels = None
depends_on = None


def upgrade():
    # =====================================================
    # ADD MANUAL DEACTIVATION FIELDS
    # =====================================================

    with op.batch_alter_table(
        "subscriptions",
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "manually_deactivated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            )
        )

        batch_op.add_column(
            sa.Column(
                "manually_deactivated_by",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "manually_deactivated_at",
                sa.DateTime(timezone=True),
                nullable=True
            )
        )

        batch_op.create_index(
            batch_op.f(
                "ix_subscriptions_manually_deactivated"
            ),
            ["manually_deactivated"],
            unique=False
        )

        batch_op.create_foreign_key(
            "fk_subscriptions_manually_deactivated_by_users",
            "users",
            ["manually_deactivated_by"],
            ["id"]
        )

    # =====================================================
    # REMOVE SERVER DEFAULT
    # =====================================================
    #
    # The model itself already has:
    #
    # manually_deactivated = db.Column(
    #     db.Boolean,
    #     nullable=False,
    #     default=False
    # )
    #
    # The server_default above was only required so existing
    # database records could be migrated safely.

    with op.batch_alter_table(
        "subscriptions",
        schema=None
    ) as batch_op:

        batch_op.alter_column(
            "manually_deactivated",
            server_default=None
        )


def downgrade():

    with op.batch_alter_table(
        "subscriptions",
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            "fk_subscriptions_manually_deactivated_by_users",
            type_="foreignkey"
        )

        batch_op.drop_index(
            batch_op.f(
                "ix_subscriptions_manually_deactivated"
            )
        )

        batch_op.drop_column(
            "manually_deactivated_at"
        )

        batch_op.drop_column(
            "manually_deactivated_by"
        )

        batch_op.drop_column(
            "manually_deactivated"
        )