"""widen jobs.source_job_id to 512 chars

Some real job sources (JSearch/RapidAPI in particular) use long,
base64-encoded opaque job IDs -- 250-350+ characters observed live -- which
overflowed the original 255-char column and silently failed every insert
from that source until this was widened.

Revision ID: 0002_widen_source_job_id
Revises: 0001_initial
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_widen_source_job_id"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "jobs",
        "source_job_id",
        existing_type=sa.String(255),
        type_=sa.String(512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "jobs",
        "source_job_id",
        existing_type=sa.String(512),
        type_=sa.String(255),
        existing_nullable=False,
    )
