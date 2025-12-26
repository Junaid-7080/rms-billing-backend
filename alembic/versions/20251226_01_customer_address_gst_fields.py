"""Add structured address and GST fields to customers

Revision ID: 20251226_01
Revises: 
Create Date: 2025-12-26 09:26:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251226_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("address_line1", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("address_line2", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("address_line3", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("country", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("customer_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("gst_exempted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("gst_exemption_reason", sa.Text(), nullable=True))
        batch_op.drop_column("address")

    op.alter_column("customers", "gst_exempted", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("address", sa.Text(), nullable=True))
        batch_op.drop_column("gst_exemption_reason")
        batch_op.drop_column("gst_exempted")
        batch_op.drop_column("customer_note")
        batch_op.drop_column("country")
        batch_op.drop_column("state")
        batch_op.drop_column("address_line3")
        batch_op.drop_column("address_line2")
        batch_op.drop_column("address_line1")
