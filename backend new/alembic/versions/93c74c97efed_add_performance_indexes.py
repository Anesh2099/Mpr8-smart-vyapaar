"""add performance indexes

Revision ID: 93c74c97efed
Revises: f76eb668f2ee
Create Date: 2026-04-13 16:12:45.040398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93c74c97efed'
down_revision: Union[str, None] = 'f76eb668f2ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX idx_inventory_low_stock
        ON inventory(store_id, product_id)
        WHERE stock < reorder_level
    """)
    op.execute("""
        CREATE INDEX idx_inventory_expiry
        ON inventory(store_id, expiry_date)
        WHERE expiry_date IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX idx_sales_date
        ON customer_sales(store_id, sale_date DESC)
    """)
    op.execute("""
        CREATE INDEX idx_supplier_products_gin
        ON suppliers USING gin(products)
    """)
    op.execute("""
        CREATE INDEX idx_alerts_store_active
        ON proactive_alerts(store_id, created_at DESC)
        WHERE dismissed = false
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_inventory_low_stock")
    op.execute("DROP INDEX IF EXISTS idx_inventory_expiry")
    op.execute("DROP INDEX IF EXISTS idx_sales_date")
    op.execute("DROP INDEX IF EXISTS idx_supplier_products_gin")
    op.execute("DROP INDEX IF EXISTS idx_alerts_store_active")
