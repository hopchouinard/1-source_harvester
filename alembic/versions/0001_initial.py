from __future__ import annotations

from alembic import op


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Create all tables using app.models metadata to keep parity with code
    from app.models import metadata

    metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.models import metadata

    metadata.drop_all(bind)

