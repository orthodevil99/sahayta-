"""add sos_reports.duplicate_of (Wave 4, Agent 10 — duplicate-merge semantics)

Revision ID: c7a10f3e2b91
Revises: b172c2490941
Create Date: 2026-10-06

SQLite has no ALTER CONSTRAINT support, so batch mode (copy-and-move) is used.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a10f3e2b91'
down_revision = 'b172c2490941'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sos_reports") as batch_op:
        batch_op.add_column(sa.Column("duplicate_of", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_sos_reports_duplicate_of",
            "sos_reports", ["duplicate_of"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("sos_reports") as batch_op:
        batch_op.drop_constraint("fk_sos_reports_duplicate_of", type_="foreignkey")
        batch_op.drop_column("duplicate_of")
