"""add projects, scoping tickets and conversations

Revision ID: db5519dc8798
Revises: 22b059f01724
Create Date: 2026-08-30

A project is the container the product starts from: the user names one before any
room or ticket exists, and both carry a NOT NULL projects.id from then on.

THIS MIGRATION DELETES DATA, deliberately and on the user's instruction. Every
existing ticket, conversation, message and verdict predates projects and has no
project to belong to; rather than invent a default one, they are removed so the
NOT NULL columns can be added outright. personas and ai_provider_configs are left
alone -- the cast and the active provider config survive.

The downgrade drops the columns and the table. It does NOT restore the deleted
rows: nothing recorded them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db5519dc8798'
down_revision: Union[str, Sequence[str], None] = '22b059f01724'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Child-first, so no foreign key is violated on the way down the chain.
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM verdict_options")
    op.execute("DELETE FROM tickets")
    op.execute("DELETE FROM verdicts")
    op.execute("DELETE FROM conversations")

    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('repo_url', sa.String(length=500), nullable=True),
        sa.Column('default_branch', sa.String(length=100), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_projects_name'),
    )

    for table in ('tickets', 'conversations'):
        # The tables are empty by now, so NOT NULL needs no backfill and no
        # nullable-then-alter step.
        op.add_column(table, sa.Column('project_id', sa.Integer(), nullable=False))
        op.create_foreign_key(
            f'fk_{table}_project_id',
            table,
            'projects',
            ['project_id'],
            ['id'],
            ondelete='CASCADE',
        )
        op.create_index(f'ix_{table}_project_id', table, ['project_id'])


def downgrade() -> None:
    """Downgrade schema."""
    for table in ('tickets', 'conversations'):
        op.drop_index(f'ix_{table}_project_id', table_name=table)
        op.drop_constraint(f'fk_{table}_project_id', table, type_='foreignkey')
        op.drop_column(table, 'project_id')

    op.drop_table('projects')
