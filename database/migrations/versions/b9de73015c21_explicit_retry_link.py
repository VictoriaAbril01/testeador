"""Link explicit retries to their interrupted source execution."""

from alembic import op
import sqlalchemy as sa

revision = "b9de73015c21"
down_revision = "a10e312cb840"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("retry_of_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f("fk_test_runs_retry_of_run_id_test_runs"), "test_runs", "test_runs",
                          ["retry_of_run_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_test_runs_retry_of_run_id"), "test_runs", ["retry_of_run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_test_runs_retry_of_run_id"), table_name="test_runs")
    op.drop_constraint(op.f("fk_test_runs_retry_of_run_id_test_runs"), "test_runs", type_="foreignkey")
    op.drop_column("test_runs", "retry_of_run_id")
