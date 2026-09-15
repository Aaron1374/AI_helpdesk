
"""change ticket embedding dimension to 3072

Revision ID: 5a6381fc5d41
Revises: 6d2f8363dfc9
Create Date: 2026-09-15 12:57:59.559972

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a6381fc5d41'
down_revision = '6d2f8363dfc9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tickets "
        "ALTER COLUMN embedding TYPE vector(3072)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tickets "
        "ALTER COLUMN embedding TYPE vector(1536)"
    )
