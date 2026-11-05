"""Persist original finding scenario and rules actually evaluated in a run."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "88a1b7c52d10"
down_revision = "5d21b0a70e5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("scenario", JSONB(), nullable=True))
    op.add_column("test_steps", sa.Column("page_url", sa.String(2048), nullable=True))
    op.create_table(
        "rule_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_key", sa.String(50), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("page_url", sa.String(2048), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("observed_status", sa.Integer(), nullable=True),
    )
    op.create_index("ix_rule_evaluations_run_rule_url", "rule_evaluations", ["run_id", "rule_key", "url"])


def downgrade() -> None:
    op.drop_index("ix_rule_evaluations_run_rule_url", table_name="rule_evaluations")
    op.drop_table("rule_evaluations")
    op.drop_column("findings", "scenario")
    op.drop_column("test_steps", "page_url")
