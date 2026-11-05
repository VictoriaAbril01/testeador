"""Queue lifecycle, cancellation and idempotent execution requests."""

from alembic import op
import sqlalchemy as sa

revision = "a10e312cb840"
down_revision = "88a1b7c52d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_test_runs_status"), "test_runs", type_="check")
    op.create_check_constraint(op.f("ck_test_runs_status"), "test_runs",
        "status IN ('pending', 'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled')")
    op.add_column("test_runs", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.add_column("test_runs", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.add_column("test_runs", sa.Column("dispatch_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("test_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(op.f("uq_test_runs_idempotency_key"), "test_runs", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_test_runs_idempotency_key"), "test_runs", type_="unique")
    op.drop_column("test_runs", "heartbeat_at")
    op.drop_column("test_runs", "request_fingerprint")
    op.drop_column("test_runs", "dispatch_requested")
    op.drop_column("test_runs", "idempotency_key")
    op.drop_constraint(op.f("ck_test_runs_status"), "test_runs", type_="check")
    op.create_check_constraint(op.f("ck_test_runs_status"), "test_runs",
        "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')")
