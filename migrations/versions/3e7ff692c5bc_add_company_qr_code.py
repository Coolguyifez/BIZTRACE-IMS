"""Add company QR code

Revision ID: 3e7ff692c5bc
Revises: 2e56236b51fb
Create Date: 2026-09-11 01:04:00.477349

"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = '3e7ff692c5bc'
down_revision = '2e56236b51fb'
branch_labels = None
depends_on = None


def upgrade():
    # Add the column as nullable first so existing companies can be updated.
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('qr_code', sa.String(length=32), nullable=True)
        )

    # Generate a unique QR code for existing companies.
    connection = op.get_bind()

    companies = connection.execute(
        sa.text("SELECT id FROM companies")
    ).fetchall()

    for company in companies:
        qr_code = uuid.uuid4().hex[:32]

        connection.execute(
            sa.text("""
                UPDATE companies
                SET qr_code = :qr_code
                WHERE id = :company_id
            """),
            {
                "qr_code": qr_code,
                "company_id": company.id
            }
        )

    # Make the QR code unique.
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_companies_qr_code',
            ['qr_code']
        )


def downgrade():
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.drop_constraint(
            'uq_companies_qr_code',
            type_='unique'
        )
        batch_op.drop_column('qr_code')