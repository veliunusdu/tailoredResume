"""
Security, Privacy, and RLS

Revision ID: 0003_security_and_rls
Revises: 0001_initial_schema
"""

from alembic import op
import sqlalchemy as sa


# Alembic revision identifiers
revision = "0003_security_and_rls"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add require_human_confirmation to user_search_config
    op.add_column("user_search_config", sa.Column("require_human_confirmation", sa.Integer, server_default=sa.text("1")))

    # 2. Create user_keys table
    op.create_table(
        "user_keys",
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("encrypted_data_key", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("user_id")
    )

    # 3. Enable RLS and Create Policies
    tables_with_user_id = [
        "jobs",
        "apply_attempts",
        "resumes",
        "user_search_config",
        "user_keys"
    ]

    for table in tables_with_user_id:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table} 
            AS PERMISSIVE FOR ALL TO public 
            USING (user_id = current_setting('app.current_user_id', true))
            WITH CHECK (user_id = current_setting('app.current_user_id', true));
            """
        )


def downgrade() -> None:
    tables_with_user_id = [
        "jobs",
        "apply_attempts",
        "resumes",
        "user_search_config",
        "user_keys"
    ]
    for table in tables_with_user_id:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_table("user_keys")
    op.drop_column("user_search_config", "require_human_confirmation")
