"""Add user notification preferences

Revision ID: 76a9e43217a4
Revises: f8a50a377ef2
"""

from alembic import op
import sqlalchemy as sa


revision = "76a9e43217a4"
down_revision = "f8a50a377ef2"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(bind, table_name, index_name):
    inspector = sa.inspect(bind)

    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False

    return any(
        index.get("name") == index_name
        for index in indexes
    )


def _column_exists(bind, table_name, column_name):
    inspector = sa.inspect(bind)

    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return False

    return any(
        column.get("name") == column_name
        for column in columns
    )


def upgrade():

    bind = op.get_bind()

    # ============================================================
    # NOTIFICATIONS TABLE
    # ============================================================

    if not _table_exists(bind, "notifications"):

        op.create_table(
            "notifications",

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
                "user_id",
                sa.Integer(),
                nullable=True
            ),

            sa.Column(
                "title",
                sa.String(length=200),
                nullable=False
            ),

            sa.Column(
                "message",
                sa.Text(),
                nullable=False
            ),

            sa.Column(
                "category",
                sa.String(length=50),
                nullable=False,
                server_default="system"
            ),

            sa.Column(
                "priority",
                sa.String(length=20),
                nullable=False,
                server_default="normal"
            ),

            sa.Column(
                "sound",
                sa.String(length=50),
                nullable=True
            ),

            sa.Column(
                "reference_type",
                sa.String(length=50),
                nullable=True
            ),

            sa.Column(
                "reference_id",
                sa.Integer(),
                nullable=True
            ),

            sa.Column(
                "link",
                sa.String(length=500),
                nullable=True
            ),

            sa.Column(
                "is_read",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            ),

            sa.Column(
                "browser_sent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            ),

            sa.Column(
                "email_sent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            ),

            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False
            ),

            sa.ForeignKeyConstraint(
                ["company_id"],
                ["companies.id"]
            ),

            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"]
            ),

            sa.PrimaryKeyConstraint("id")
        )

    # ============================================================
    # NOTIFICATION INDEXES
    # ============================================================

    if not _index_exists(
        bind,
        "notifications",
        "ix_notification_company_user"
    ):
        op.create_index(
            "ix_notification_company_user",
            "notifications",
            ["company_id", "user_id"],
            unique=False
        )

    if not _index_exists(
        bind,
        "notifications",
        "ix_notification_created_at"
    ):
        op.create_index(
            "ix_notification_created_at",
            "notifications",
            ["created_at"],
            unique=False
        )

    if not _index_exists(
        bind,
        "notifications",
        "ix_notification_unread"
    ):
        op.create_index(
            "ix_notification_unread",
            "notifications",
            ["company_id", "user_id", "is_read"],
            unique=False
        )

    # ============================================================
    # PUSH SUBSCRIPTIONS TABLE
    # ============================================================

    if not _table_exists(bind, "push_subscriptions"):

        op.create_table(
            "push_subscriptions",

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
                "user_id",
                sa.Integer(),
                nullable=False
            ),

            sa.Column(
                "endpoint",
                sa.Text(),
                nullable=False
            ),

            sa.Column(
                "p256dh",
                sa.Text(),
                nullable=False
            ),

            sa.Column(
                "auth",
                sa.Text(),
                nullable=False
            ),

            sa.Column(
                "user_agent",
                sa.Text(),
                nullable=True
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

            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"]
            ),

            sa.PrimaryKeyConstraint("id"),

            sa.UniqueConstraint(
                "endpoint"
            )
        )

    # ============================================================
    # PUSH SUBSCRIPTION INDEX
    # ============================================================

    if not _index_exists(
        bind,
        "push_subscriptions",
        "ix_push_subscription_user"
    ):
        op.create_index(
            "ix_push_subscription_user",
            "push_subscriptions",
            ["user_id"],
            unique=False
        )

    # ============================================================
    # USER NOTIFICATION PREFERENCES
    # ============================================================

    with op.batch_alter_table(
        "users",
        schema=None
    ) as batch_op:

        if not _column_exists(
            bind,
            "users",
            "notification_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "notification_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "browser_notification_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "browser_notification_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "email_notification_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "email_notification_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "sound_notification_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "sound_notification_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "success_sound_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "success_sound_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "error_sound_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "error_sound_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "low_stock_sound_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "low_stock_sound_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "gross_loss_sound_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "gross_loss_sound_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )

        if not _column_exists(
            bind,
            "users",
            "net_loss_sound_enabled"
        ):
            batch_op.add_column(
                sa.Column(
                    "net_loss_sound_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true()
                )
            )


def downgrade():

    bind = op.get_bind()

    # ============================================================
    # USER COLUMNS
    # ============================================================

    existing_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("users")
    }

    user_columns = [
        "net_loss_sound_enabled",
        "gross_loss_sound_enabled",
        "low_stock_sound_enabled",
        "error_sound_enabled",
        "success_sound_enabled",
        "sound_notification_enabled",
        "email_notification_enabled",
        "browser_notification_enabled",
        "notification_enabled",
    ]

    with op.batch_alter_table(
        "users",
        schema=None
    ) as batch_op:

        for column_name in user_columns:
            if column_name in existing_columns:
                batch_op.drop_column(column_name)

    # ============================================================
    # PUSH SUBSCRIPTIONS
    # ============================================================

    if _table_exists(bind, "push_subscriptions"):

        if _index_exists(
            bind,
            "push_subscriptions",
            "ix_push_subscription_user"
        ):
            op.drop_index(
                "ix_push_subscription_user",
                table_name="push_subscriptions"
            )

        op.drop_table("push_subscriptions")

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    if _table_exists(bind, "notifications"):

        if _index_exists(
            bind,
            "notifications",
            "ix_notification_unread"
        ):
            op.drop_index(
                "ix_notification_unread",
                table_name="notifications"
            )

        if _index_exists(
            bind,
            "notifications",
            "ix_notification_created_at"
        ):
            op.drop_index(
                "ix_notification_created_at",
                table_name="notifications"
            )

        if _index_exists(
            bind,
            "notifications",
            "ix_notification_company_user"
        ):
            op.drop_index(
                "ix_notification_company_user",
                table_name="notifications"
            )

        op.drop_table("notifications")