"""Add Phase 4 ticket models

Revision ID: 1234abcd5678
Revises: previous_revision_id # Assuming there's a previous one, placeholder
Create Date: 2026-09-07 23:31:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1234abcd5678'
down_revision = 'baseline_0001'
branch_labels = None
depends_on = None


def upgrade():
    # Create Enum Type
    ticketstatus = postgresql.ENUM('NEW', 'TRIAGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'ESCALATED', name='ticketstatus')
    ticketstatus.create(op.get_bind())

    # Create tickets table
    op.create_table(
        'tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', ticketstatus, nullable=False, server_default='NEW'),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'])
    )

    # Create ticket_history table
    op.create_table(
        'ticket_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_status', ticketstatus, nullable=True),
        sa.Column('new_status', ticketstatus, nullable=False),
        sa.Column('changed_by', sa.String(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'])
    )

    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('trace_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('actor', sa.String(), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )
    op.create_index('ix_audit_events_trace_id', 'audit_events', ['trace_id'])


def downgrade():
    op.drop_index('ix_audit_events_trace_id', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('ticket_history')
    op.drop_table('tickets')
    
    ticketstatus = postgresql.ENUM('NEW', 'TRIAGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'ESCALATED', name='ticketstatus')
    ticketstatus.drop(op.get_bind())
