"""Baseline schema for users and chat

Revision ID: baseline_0001
Revises: None
Create Date: 2026-09-07 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'baseline_0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # UserRole Enum
    userrole = postgresql.ENUM('employee', 'l1', 'l2', 'support_lead', 'admin', name='userrole')
    # userrole.create(op.get_bind())

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('role', userrole, nullable=False, server_default='employee')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # ConversationOwner Enum
    conversationowner = postgresql.ENUM('AI', 'HUMAN', name='conversationowner')
    # conversationowner.create(op.get_bind())

    # ConversationStatus Enum
    conversationstatus = postgresql.ENUM('ACTIVE', 'CLOSED', name='conversationstatus')
    # conversationstatus.create(op.get_bind())

    # Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_type', conversationowner, nullable=False, server_default='AI'),
        sa.Column('status', conversationstatus, nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )

    # SenderType Enum
    sendertype = postgresql.ENUM('USER', 'AI', 'SYSTEM', name='sendertype')
    # sendertype.create(op.get_bind())

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_type', sendertype, nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('trace_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'])
    )

def downgrade():
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    postgresql.ENUM(name='sendertype').drop(op.get_bind())
    postgresql.ENUM(name='conversationstatus').drop(op.get_bind())
    postgresql.ENUM(name='conversationowner').drop(op.get_bind())
    postgresql.ENUM(name='userrole').drop(op.get_bind())
