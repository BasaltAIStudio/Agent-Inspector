"""secure credentials and add workspace/task ownership fields

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

from typing import Sequence, Union
import hashlib
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    columns = {table: {c["name"] for c in inspector.get_columns(table)} for table in tables}

    def add_column(table: str, column: sa.Column) -> None:
        if table in tables and column.name not in columns[table]:
            op.add_column(table, column)

    add_column("api_keys", sa.Column("workspace_id", sa.String(), nullable=True))
    add_column("agents", sa.Column("encrypted_api_key", sa.Text(), nullable=True))
    add_column("audits", sa.Column("tenant_id", sa.String(), nullable=True))
    add_column("audits", sa.Column("idempotency_key", sa.String(), nullable=True))
    add_column("audits", sa.Column("timeout_seconds", sa.Integer(), nullable=True, server_default="300"))
    add_column("task_queue", sa.Column("max_retries", sa.Integer(), nullable=True, server_default="3"))
    add_column("task_queue", sa.Column("next_attempt_at", sa.DateTime(), nullable=True))
    add_column("task_queue", sa.Column("locked_at", sa.DateTime(), nullable=True))
    add_column("task_queue", sa.Column("worker_id", sa.String(), nullable=True))

    if "workspaces" not in tables:
        op.create_table("workspaces", sa.Column("id", sa.String(), primary_key=True), sa.Column("name", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=True))
    if "users" not in tables:
        op.create_table("users", sa.Column("id", sa.String(), primary_key=True), sa.Column("email", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=True))
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if "workspace_members" not in tables:
        op.create_table("workspace_members", sa.Column("id", sa.String(), primary_key=True), sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False), sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False), sa.Column("role", sa.String(), nullable=False, server_default="member"), sa.Column("created_at", sa.DateTime(), nullable=True))
        op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
        op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    if "api_keys" in tables:
        conn = op.get_bind()
        rows = conn.execute(sa.text("SELECT key, hashed_key FROM api_keys")).fetchall()
        for key, hashed_key in rows:
            if key and not hashed_key:
                conn.execute(sa.text("UPDATE api_keys SET hashed_key=:digest, key=:opaque WHERE key=:key"), {"digest": _hash(key), "opaque": "key_" + uuid.uuid4().hex, "key": key})


def downgrade() -> None:
    pass
