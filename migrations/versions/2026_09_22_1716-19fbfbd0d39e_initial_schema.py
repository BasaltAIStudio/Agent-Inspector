"""initial schema

Revision ID: 19fbfbd0d39e
Revises: 
Create Date: 2026-09-22 17:16:00.199140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '19fbfbd0d39e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        from sqlalchemy import text
        op.create_table(
            "agents",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("agent_type", sa.String(100)),
            sa.Column("config", sa.Text()),
            sa.Column("endpoint", sa.String(500)),
            sa.Column("api_key", sa.String(255)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_agents_name", "agents", ["name"], unique=False)
        op.create_table(
            "audits",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("agent_id", sa.String(255), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("status", sa.String(50), server_default="pending"),
            sa.Column("overall_score", sa.Float()),
            sa.Column("reliability_score", sa.Float()),
            sa.Column("security_score", sa.Float()),
            sa.Column("tool_usage_score", sa.Float()),
            sa.Column("hallucination_score", sa.Float()),
            sa.Column("privacy_score", sa.Float()),
            sa.Column("cost_score", sa.Float()),
            sa.Column("latency_score", sa.Float()),
            sa.Column("instruction_following_score", sa.Float()),
            sa.Column("human_escalation_score", sa.Float()),
            sa.Column("test_count", sa.Integer(), server_default="0"),
            sa.Column("findings_count", sa.Integer(), server_default="0"),
            sa.Column("critical_count", sa.Integer(), server_default="0"),
            sa.Column("high_count", sa.Integer(), server_default="0"),
            sa.Column("medium_count", sa.Integer(), server_default="0"),
            sa.Column("low_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime()),
        )
        op.create_index("ix_audits_agent_id", "audits", ["agent_id"], unique=False)
        op.create_table(
            "findings",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("audit_id", sa.String(255), sa.ForeignKey("audits.id"), nullable=True),
            sa.Column("category", sa.String(100)),
            sa.Column("severity", sa.String(50)),
            sa.Column("title", sa.String(500)),
            sa.Column("description", sa.Text()),
            sa.Column("evidence", sa.Text()),
            sa.Column("remediation", sa.Text()),
            sa.Column("reproducibility", sa.Float()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_findings_audit_id", "findings", ["audit_id"], unique=False)
        op.create_table(
            "test_results",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("audit_id", sa.String(255), sa.ForeignKey("audits.id"), nullable=True),
            sa.Column("test_name", sa.String(255)),
            sa.Column("category", sa.String(100)),
            sa.Column("status", sa.String(50)),
            sa.Column("input_data", sa.Text()),
            sa.Column("output_data", sa.Text()),
            sa.Column("expected", sa.Text()),
            sa.Column("actual", sa.Text()),
            sa.Column("latency_ms", sa.Float()),
            sa.Column("cost", sa.Float()),
            sa.Column("tokens_used", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_test_results_audit_id", "test_results", ["audit_id"], unique=False)
        op.create_table(
            "task_queue",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("audit_id", sa.String(255), sa.ForeignKey("audits.id"), nullable=True),
            sa.Column("status", sa.String(50), server_default="pending"),
            sa.Column("priority", sa.Integer(), server_default="0"),
            sa.Column("retries", sa.Integer(), server_default="0"),
            sa.Column("error", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("finished_at", sa.DateTime()),
        )
        op.create_index("ix_task_queue_audit_id", "task_queue", ["audit_id"], unique=False)
        op.create_table(
            "api_keys",
            sa.Column("key", sa.String(255), primary_key=True),
            sa.Column("owner", sa.String(255)),
            sa.Column("rate_limit", sa.Integer(), server_default="100"),
            sa.Column("scopes", sa.Text(), server_default="audit:read,audit:write,agent:read"),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    else:
        op.create_table(
            "agents",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("agent_type", sa.String(100)),
            sa.Column("config", sa.Text()),
            sa.Column("endpoint", sa.String(500)),
            sa.Column("api_key", sa.String(255)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_agents_name", "agents", ["name"], unique=False)
        op.create_table(
            "audits",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("agent_id", sa.String(255), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("status", sa.String(50), server_default="pending"),
            sa.Column("overall_score", sa.Float()),
            sa.Column("reliability_score", sa.Float()),
            sa.Column("security_score", sa.Float()),
            sa.Column("tool_usage_score", sa.Float()),
            sa.Column("hallucination_score", sa.Float()),
            sa.Column("privacy_score", sa.Float()),
            sa.Column("cost_score", sa.Float()),
            sa.Column("latency_score", sa.Float()),
            sa.Column("instruction_following_score", sa.Float()),
            sa.Column("human_escalation_score", sa.Float()),
            sa.Column("test_count", sa.Integer(), server_default="0"),
            sa.Column("findings_count", sa.Integer(), server_default="0"),
            sa.Column("critical_count", sa.Integer(), server_default="0"),
            sa.Column("high_count", sa.Integer(), server_default="0"),
            sa.Column("medium_count", sa.Integer(), server_default="0"),
            sa.Column("low_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime()),
        )
        op.create_index("ix_audits_agent_id", "audits", ["agent_id"], unique=False)
        op.create_table(
            "findings",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("audit_id", sa.String(255), sa.ForeignKey("audits.id"), nullable=True),
            sa.Column("category", sa.String(100)),
            sa.Column("severity", sa.String(50)),
            sa.Column("title", sa.String(500)),
            sa.Column("description", sa.Text()),
            sa.Column("evidence", sa.Text()),
            sa.Column("remediation", sa.Text()),
            sa.Column("reproducibility", sa.Float()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_findings_audit_id", "findings", ["audit_id"], unique=False)
        op.create_table(
            "test_results",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("audit_id", sa.String(255), sa.ForeignKey("audits.id"), nullable=True),
            sa.Column("test_name", sa.String(255)),
            sa.Column("category", sa.String(100)),
            sa.Column("status", sa.String(50)),
            sa.Column("input_data", postgresql.JSONB()),
            sa.Column("output_data", postgresql.JSONB()),
            sa.Column("expected", sa.Text()),
            sa.Column("actual", sa.Text()),
            sa.Column("latency_ms", sa.Float()),
            sa.Column("cost", sa.Float()),
            sa.Column("tokens_used", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_test_results_audit_id", "test_results", ["audit_id"], unique=False)
        op.create_table(
            "task_queue",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("audit_id", sa.String(255), sa.ForeignKey("audits.id"), nullable=True),
            sa.Column("status", sa.String(50), server_default="pending"),
            sa.Column("priority", sa.Integer(), server_default="0"),
            sa.Column("retries", sa.Integer(), server_default="0"),
            sa.Column("error", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("finished_at", sa.DateTime()),
        )
        op.create_index("ix_task_queue_audit_id", "task_queue", ["audit_id"], unique=False)
        op.create_table(
            "api_keys",
            sa.Column("key", sa.String(255), primary_key=True),
            sa.Column("owner", sa.String(255)),
            sa.Column("rate_limit", sa.Integer(), server_default="100"),
            sa.Column("scopes", sa.Text(), server_default="audit:read,audit:write,agent:read"),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_table("api_keys")
    op.drop_table("task_queue")
    op.drop_table("test_results")
    op.drop_table("findings")
    op.drop_table("audits")
    op.drop_table("agents")
