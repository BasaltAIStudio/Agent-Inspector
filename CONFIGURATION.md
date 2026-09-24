# AgentInspector Configuration Guide

This document describes all environment variables and configuration options for running AgentInspector in development and production.

## Table of Contents

- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
  - [Database](#database)
  - [Celery / Task Queue](#celery--task-queue)
  - [API and Security](#api-and-security)
  - [Model Configuration](#model-configuration)
  - [Logging](#logging)
- [Deployment Modes](#deployment-modes)
- [Migration Strategy](#migration-strategy)
- [Dashboard Configuration](#dashboard-configuration)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run database migrations:
   ```bash
   alembic upgrade head
   ```

4. Start the backend:
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

5. Start the dashboard:
   ```bash
   cd dashboard
   streamlit run app.py
   ```

---

## Environment Variables

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///./agentinspector.db` | SQLAlchemy database URL. Supports SQLite and PostgreSQL. |

**Examples:**

```bash
# SQLite (default, file-based, no server required)
DATABASE_URL=sqlite:///./agentinspector.db

# PostgreSQL (production)
DATABASE_URL=postgresql://postgres:pass@localhost:5432/agentinspector
```

### Task Execution

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CELERY_BROKER_URL` | No | None | If set, enables Celery task execution |
| `CELERY_RESULT_BACKEND` | No | None | Celery result backend |

If `CELERY_BROKER_URL` is not set, the backend uses in-process `asyncio` task execution.

### API and Security

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed CORS origins |

Authentication uses API keys created via `/api/v1/keys`.

### Model Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTENCE_TRANSFORMER_MODEL` | No | `all-MiniLM-L6-v2` | HuggingFace model name for semantic embeddings |
| `JUDGE_MODEL` | No | None | OpenAI model name for LLM judge evaluation |
| `OPENAI_API_KEY` | Conditional | None | Required if `JUDGE_MODEL` is set |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Deployment Modes

### Development Mode

Uses SQLite and in-process task execution.

```bash
# .env
DATABASE_URL=sqlite:///./agentinspector.db
```

### Production Mode

Uses PostgreSQL. Celery support is present but deferred; current production path is in-process `asyncio`.

```bash
# .env
DATABASE_URL=postgresql://postgres:pass@localhost:5432/agentinspector
CORS_ORIGINS=https://agentinspector.example.com
```

Start the backend:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Migration Strategy

AgentInspector uses Alembic for database migrations.

### Initial Setup

1. Ensure `DATABASE_URL` is set in your environment.
2. Run migrations:
   ```bash
   alembic upgrade head
   ```

### Creating New Migrations

When modifying models in `backend/database.py`:

```bash
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

### Production Migrations

```bash
# Back up before migrating
pg_dump agentinspector > backup_$(date +%Y%m%d).sql

# Apply migrations
alembic upgrade head
```

### Downgrading

```bash
alembic downgrade -1
alembic downgrade base
```

---

## CLI

The CLI is installed as the `agentinspector` entry point.

```bash
# Run audit
agentinspector audit --agent-id agent-1 --name "My Agent" --framework rest_api --output report.json

# List audits
agentinspector list-audits

# Get audit
agentinspector get-audit <audit_id>

# Export audit
agentinspector export-audit <audit_id> report.json
```

---

## Monitoring

Monitoring endpoints are available under `/api/v1/monitoring`:

- `GET /api/v1/monitoring/alerts?agent_id=<id>` — active alerts
- `GET /api/v1/monitoring/trends?agent_id=<id>&days=30` — score trend
- `GET /api/v1/monitoring/category-trends?agent_id=<id>&days=30` — category-level trends

Alert types:
- `score_drop` — overall score dropped sharply
- `failure_spike` — failure rate above threshold
- `critical_findings` — new critical findings detected

---

## Dashboard Configuration

The Streamlit dashboard connects to the backend API.

### Configuration via UI

1. Open the dashboard
2. Go to **Settings**
3. Enter backend URL and API key

### Real-time Updates

The dashboard polls the backend every 15 seconds when viewing audit history. Adjust the interval in `dashboard/app.py`:

```python
REFRESH_INTERVAL = 15  # seconds
```

---

## Troubleshooting

### "DATABASE_URL environment variable is required for migrations"

Set `DATABASE_URL` before running Alembic commands:

```bash
export DATABASE_URL=sqlite:///./agentinspector.db
alembic upgrade head
```

### "No module named 'backend'"

Ensure the project root is in `PYTHONPATH`:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Connection pooling

Production deployments should use a connection pool. For PostgreSQL, SQLAlchemy uses `QueuePool` by default. Adjust pool size via SQLAlchemy engine options if needed.

---

## Security Notes

- Never commit `.env` to version control
- Rotate API keys regularly
- Use strong, unique passwords for PostgreSQL in production
- Enable SSL for PostgreSQL connections in production
- Restrict `CORS_ORIGINS` to known domains in production
