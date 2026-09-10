"""Add embeddings to ticket and department to models

Revision ID: pgvector_tickets
Revises: pgvector_abcd1234
Create Date: 2026-09-07 23:38:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'pgvector_tickets'
down_revision = 'pgvector_abcd1234'
branch_labels = None
depends_on = None

def upgrade():
    # Add embedding and department to tickets
    op.add_column('tickets', sa.Column('embedding', Vector(3072), nullable=True))
    op.add_column('tickets', sa.Column('department', sa.String(), nullable=True))
    
    # Add department to users
    op.add_column('users', sa.Column('department', sa.String(), nullable=True))
    
    # Add department to knowledge_documents
    op.add_column('knowledge_documents', sa.Column('department', sa.String(), nullable=True))


def downgrade():
    op.drop_column('knowledge_documents', 'department')
    op.drop_column('users', 'department')
    op.drop_column('tickets', 'department')
    op.drop_column('tickets', 'embedding')
