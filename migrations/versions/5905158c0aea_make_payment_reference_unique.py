"""Make payment reference unique

Revision ID: 5905158c0aea
Revises: f3d84c86eff6
Create Date: 2026-09-12 21:50:31.035802

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.

revision = "5905158c0aea"
down_revision = "f3d84c86eff6"
branch_labels = None
depends_on = None

def upgrade():


# PostgreSQL-safe unique constraint creation.
#
# The Render database is initially empty, so the constraint
# should simply be created on the payments.reference column.

op.create_unique_constraint(
    "uq_payments_reference",
    "payments",
    ["reference"]
)
```

def downgrade():

```
# Remove the constraint if the migration is rolled back.

op.drop_constraint(
    "uq_payments_reference",
    "payments",
    type_="unique"
)

