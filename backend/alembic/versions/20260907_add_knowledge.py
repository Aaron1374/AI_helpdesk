"""Add Phase 5 knowledge models

Revision ID: pgvector_abcd1234
Revises: 1234abcd5678
Create Date: 2026-09-07 23:33:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'pgvector_abcd1234'
down_revision = '1234abcd5678'
branch_labels = None
depends_on = None

def upgrade():
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'knowledge_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('knowledge_documents')
    # op.execute("DROP EXTENSION vector") # Generally don't drop extensions automatically
