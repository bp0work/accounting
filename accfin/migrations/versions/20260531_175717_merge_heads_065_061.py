"""merge_heads_065_061

Revision ID: 90f9fdae291d
Revises: 20260528_065, 20260531_061
Create Date: 2026-05-31 17:57:17.460831

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '90f9fdae291d'
down_revision: Union[str, None] = ('20260528_065', '20260531_061')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
