"""a model per persona

Revision ID: a3f1c27b5e04
Revises: db5519dc8798
Create Date: 2026-08-30

Each persona may point at its own ai_provider_config, so the four can run on
different models. The column is nullable and every existing row gets NULL, which
means "use whichever config is_active" -- exactly what all four personas did
before this column existed. No data is deleted and no table is rewritten.

ON DELETE SET NULL, never CASCADE: there are exactly four personas and they are
seeded by migration. Deleting a model configuration must drop the preference, not
the character that referenced it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c27b5e04'
down_revision: Union[str, Sequence[str], None] = 'db5519dc8798'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "personas",
        sa.Column("ai_provider_config_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_personas_ai_provider_config_id",
        "personas",
        "ai_provider_configs",
        ["ai_provider_config_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_personas_ai_provider_config_id", "personas", type_="foreignkey"
    )
    op.drop_column("personas", "ai_provider_config_id")
