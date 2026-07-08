"""
Add interview questions to jobs

Revision ID: 0004_add_interview_questions
Revises: 0003_security_and_rls
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Alembic revision identifiers
revision = "0004_add_interview_questions"
down_revision = "0003_security_and_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add interview_questions column
    op.add_column("jobs", sa.Column("interview_questions", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    # Drop interview_questions column
    op.drop_column("jobs", "interview_questions")
