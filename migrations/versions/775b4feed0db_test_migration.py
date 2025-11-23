"""test migration

Revision ID: 775b4feed0db
Revises: 6bb2462d6477
Create Date: 2025-11-23 07:58:21.540052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '775b4feed0db'
down_revision: Union[str, Sequence[str], None] = '6bb2462d6477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
