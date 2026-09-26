"""Add system sound notification preference

Revision ID: c1634aaec335
Revises: 52ac35f97fb0
Create Date: 2026-09-26 00:21:39.657929

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1634aaec335"
down_revision = "52ac35f97fb0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "system_sound_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("system_sound_enabled")