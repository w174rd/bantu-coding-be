"""add verdicts and the arbiter cadence override

Revision ID: b7c4e0d51a93
Revises: f52211af4ab5
Create Date: 2026-08-29

Hand-written for the same reason as f52211af4ab5: the database is unreachable
(blank DB_* credentials), so autogenerate cannot run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c4e0d51a93'
down_revision: Union[str, Sequence[str], None] = 'f52211af4ab5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'conversations',
        sa.Column('arbiter_every_n_rounds', sa.Integer(), nullable=True),
    )

    op.create_table(
        'verdicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('round_index', sa.Integer(), nullable=False),
        sa.Column('headline', sa.Text(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        # SET NULL, not CASCADE: deleting the ticket must not erase the reasoning
        # that produced it.
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_verdicts_conversation_id', 'verdicts', ['conversation_id'])

    op.create_table(
        'verdict_options',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('verdict_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('percentage', sa.Integer(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['verdict_id'], ['verdicts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_verdict_options_verdict_id', 'verdict_options', ['verdict_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_verdict_options_verdict_id', table_name='verdict_options')
    op.drop_table('verdict_options')
    op.drop_index('ix_verdicts_conversation_id', table_name='verdicts')
    op.drop_table('verdicts')
    op.drop_column('conversations', 'arbiter_every_n_rounds')
    # No enum types are created here, so nothing to drop by hand this time.
