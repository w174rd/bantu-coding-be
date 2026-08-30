"""a verdict can produce many tickets

Revision ID: 22b059f01724
Revises: b7c4e0d51a93
Create Date: 2026-08-30

The Arbiter now splits work with independently shippable parts into several
tickets, so the foreign key moves from verdicts.ticket_id to tickets.verdict_id.

The UPDATE between the two schema changes is not optional: dropping
verdicts.ticket_id without it silently discards every existing link.

The downgrade is LOSSY BY NATURE. A verdict that produced several tickets has no
representation in a single-FK column, so only its first ticket survives the
round trip. Downgrading past this revision loses that association.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22b059f01724'
down_revision: Union[str, Sequence[str], None] = 'b7c4e0d51a93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tickets', sa.Column('verdict_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_tickets_verdict_id',
        'tickets',
        'verdicts',
        ['verdict_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_tickets_verdict_id', 'tickets', ['verdict_id'])

    # Carry the existing links across before the column that holds them is dropped.
    op.execute(
        """
        UPDATE tickets
        SET verdict_id = verdicts.id
        FROM verdicts
        WHERE verdicts.ticket_id = tickets.id
        """
    )

    op.drop_column('verdicts', 'ticket_id')


def downgrade() -> None:
    """Downgrade schema. Lossy — see the module docstring."""
    op.add_column('verdicts', sa.Column('ticket_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_verdicts_ticket_id',
        'verdicts',
        'tickets',
        ['ticket_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Only the lowest-id ticket per verdict survives; the rest keep existing as
    # ordinary board tickets with no verdict of record.
    op.execute(
        """
        UPDATE verdicts
        SET ticket_id = (
            SELECT min(t.id) FROM tickets t WHERE t.verdict_id = verdicts.id
        )
        """
    )

    op.drop_index('ix_tickets_verdict_id', table_name='tickets')
    op.drop_constraint('fk_tickets_verdict_id', 'tickets', type_='foreignkey')
    op.drop_column('tickets', 'verdict_id')
