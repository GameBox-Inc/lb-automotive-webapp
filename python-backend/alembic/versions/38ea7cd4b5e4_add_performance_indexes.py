"""add_performance_indexes

Revision ID: 38ea7cd4b5e4
Revises: 
Create Date: 2026-01-23 18:54:16.312981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38ea7cd4b5e4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create indexes for better query performance
    # appointments.status is used for filtering in list view
    op.create_index('idx_appointments_status', 'appointments', ['status'], unique=False)
    
    # appointments.customer_name is used for search/display
    op.create_index('idx_appointments_customer', 'appointments', ['customer_name'], unique=False)
    
    # customers.name is used for search
    op.create_index('idx_customers_name', 'customers', ['name'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_customers_name', table_name='customers')
    op.drop_index('idx_appointments_customer', table_name='appointments')
    op.drop_index('idx_appointments_status', table_name='appointments')
