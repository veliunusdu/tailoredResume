"""
Initial PostgreSQL schema migration for TailoredResume.

Creates:
  - jobs (multi-tenant with user_id)
  - apply_attempts (multi-tenant with user_id)
  - resumes (new: stores per-user resume content)
  - user_search_config (new: per-user search configuration)

This replaces the SQLite init_db() inline DDL.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, DOUBLE_PRECISION


# Alembic revision identifiers
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text, nullable=False),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("company", sa.Text),
        sa.Column("location", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("date_posted", sa.Text),
        sa.Column("salary", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("site", sa.Text),
        sa.Column("tags", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("fetched_at", DOUBLE_PRECISION),
        sa.Column("score", sa.Integer),
        sa.Column("verdict", sa.Text),
        sa.Column("reason", sa.Text),
        sa.PrimaryKeyConstraint("id", "user_id"),
    )
    op.create_index("idx_jobs_user_score", "jobs", ["user_id", sa.text("score DESC")])
    op.create_index("idx_jobs_user_fetched", "jobs", ["user_id", sa.text("fetched_at DESC")])

    # ── apply_attempts ────────────────────────────────────────────────────────
    op.create_table(
        "apply_attempts",
        sa.Column("id", sa.Text, nullable=False),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("job_id", sa.Text),
        sa.Column(
            "status",
            sa.Text,
            sa.CheckConstraint(
                "status IN ('queued','running','success','failed','manual_required')"
            ),
        ),
        sa.Column("job_board", sa.Text),
        sa.Column("dry_run", sa.Integer, server_default=sa.text("1")),
        sa.Column("error_msg", sa.Text),
        sa.Column("screenshot", sa.Text),
        sa.Column("ai_patch_suggestion", sa.Text),
        sa.Column("applied_at", DOUBLE_PRECISION),
        sa.Column("created_at", DOUBLE_PRECISION),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_apply_attempts_user_job", "apply_attempts", ["user_id", "job_id"]
    )

    # ── resumes ───────────────────────────────────────────────────────────────
    op.create_table(
        "resumes",
        sa.Column("id", sa.Text, nullable=False),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("storage_path", sa.Text),
        sa.Column("created_at", DOUBLE_PRECISION),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_resumes_user", "resumes", ["user_id"])

    # ── user_search_config ────────────────────────────────────────────────────
    op.create_table(
        "user_search_config",
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("queries", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("locations", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "boards",
            JSONB,
            server_default=sa.text("'[\"indeed\",\"linkedin\",\"glassdoor\"]'::jsonb"),
        ),
        sa.Column("exclude_titles", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("results_per_site", sa.Integer, server_default=sa.text("20")),
        sa.Column("hours_old", sa.Integer, server_default=sa.text("72")),
        sa.Column("updated_at", DOUBLE_PRECISION),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_search_config")
    op.drop_index("idx_resumes_user", table_name="resumes")
    op.drop_table("resumes")
    op.drop_index("idx_apply_attempts_user_job", table_name="apply_attempts")
    op.drop_table("apply_attempts")
    op.drop_index("idx_jobs_user_fetched", table_name="jobs")
    op.drop_index("idx_jobs_user_score", table_name="jobs")
    op.drop_table("jobs")
