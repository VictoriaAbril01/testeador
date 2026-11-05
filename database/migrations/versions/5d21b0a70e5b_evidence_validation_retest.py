"""Evidence retention, validation audit, and retest lineage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "5d21b0a70e5b"
down_revision = "ca60c5011653"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("retest_of_run_id", sa.Uuid(), nullable=True))
    op.add_column("test_runs", sa.Column("scenario_urls", JSONB(), nullable=True))
    op.create_foreign_key("fk_test_runs_retest_of_run_id_test_runs", "test_runs", "test_runs", ["retest_of_run_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_test_runs_retest_of_run_id", "test_runs", ["retest_of_run_id"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])
    op.add_column("evidence", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE evidence SET expires_at = created_at + interval '30 days' WHERE expires_at IS NULL"))
    op.alter_column("evidence", "expires_at", nullable=False)
    op.create_table(
        "finding_validations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("finding_id", sa.Uuid(), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=False),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("to_status IN ('pending_confirmation', 'confirmed', 'not_reproducible', 'false_positive', 'fixed', 'retested')", name="ck_finding_validations_to_status"),
    )
    op.create_index("ix_finding_validations_finding_at", "finding_validations", ["finding_id", "validated_at"])


def downgrade() -> None:
    op.drop_index("ix_finding_validations_finding_at", table_name="finding_validations")
    op.drop_table("finding_validations")
    op.drop_column("evidence", "expires_at")
    op.drop_index("ix_findings_fingerprint", table_name="findings")
    op.drop_index("ix_test_runs_retest_of_run_id", table_name="test_runs")
    op.drop_constraint("fk_test_runs_retest_of_run_id_test_runs", "test_runs", type_="foreignkey")
    op.drop_column("test_runs", "scenario_urls")
    op.drop_column("test_runs", "retest_of_run_id")
