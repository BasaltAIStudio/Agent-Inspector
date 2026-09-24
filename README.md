# AgentInspector

Automated QA + security + reliability + cost + compliance testing platform for AI agents.

## Prerequisites

- Python >= 3.10
- PostgreSQL >= 14 (recommended)

## Install

```bash
git clone https://github.com/agentinspector/agentinspector.git
cd agentinspector
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,dashboard]"
```

## Configuration

Set the required environment variables:

```bash
export DATABASE_URL="postgresql://postgres:pass@localhost:5432/agentinspector"
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export CORS_ORIGINS="http://localhost:3000,http://localhost:8501"
```

Optional:

```bash
export OPENAI_API_KEY=""
export ANTHROPIC_API_KEY=""
export CELERY_BROKER_URL="redis://localhost:6379/0"
export SENTENCE_TRANSFORMER_MODEL="all-MiniLM-L6-v2"
export REQUIRE_REQUEST_SIGNING=""
```

Initialize the database:

```bash
alembic upgrade head
```

## Running

Backend:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Dashboard:

```bash
streamlit run dashboard/app.py
```

CLI:

```bash
agentinspector --help
agentinspector list-audits
agentinspector get-audit <audit_id>
agentinspector audit --agent-id <id> --name "My Agent" --framework rest_api --fail-on any
agentinspector create-key --owner alice --scopes "admin,agent:read" --expires-in-days 90
```

## Admin

Create an admin API key:

```bash
agentinspector create-key --owner admin --scopes admin --rate-limit 200
```

Manage signing secrets:

```bash
agentinspector upsert-secret signing_secret "$(python -c 'import secrets; print(secrets.token_hex(32))')"
agentinspector sign signing_secret "POST|/api/v1/audit|{}"
```

View admin audit log:

```bash
agentinspector list-logs
```

## CI/CD

Run a full audit and exit non-zero on failures for use in GitHub Actions, GitLab CI, or local gates:

```bash
agentinspector audit \
  --agent-id <id> \
  --name "My Agent" \
  --framework rest_api \
  --output report.json \
   --fail-on any
```

## Docker deployment

```bash
# Generate mTLS certificates
bash scripts/generate-certs.sh

# Start all services
docker compose up -d

# Verify
curl https://localhost/health --cacert certs/ca.crt --cert certs/client.crt --key certs/client.key
```

Services:
- Backend API: `https://localhost/api/` (mTLS required)
- Dashboard: `https://localhost/` (mTLS required)
- PostgreSQL: `localhost:5432`
- Nginx reverse proxy with rate limiting and security headers

## Competitive advantages

- **Semantic TF-IDF tool matching** — infers expected tools from behavior, not just keyword router or hardcoded oracles.
- **Multi-signal scoring with empirical weights** — deterministic baseline plus LLM judge when available.
- **Failure-driven dynamic test generation** — auto-generates regression tests from failed cases to close coverage gaps.
- **Audit taxonomy** — structured reliability, security, tool usage, latency, cost, compliance, and human-escalation findings.
- **Local-first SQLite/PostgreSQL backend** — agent-replay validates local trace storage; AgentInspector adds QA taxonomy and auditable scoring.
- **Built-in monitoring and alerting** — continuous anomaly detection and trend tracking for production agent ops.
- **Admin audit logging and secret vault** — role-bound keys, request signing, secret rotation, and action history for compliance.
- **Self-hostable dashboard and CLI** — no mandatory cloud dependency; deploy locally, in air-gapped environments, or behind your own VPC.

### Health

```
GET /health
GET /api/v1/dashboard
```

### Audits

```
POST /api/v1/audit
GET /api/v1/audits
GET /api/v1/audits/{audit_id}
GET /api/v1/audits/{audit_id}/tests
GET /api/v1/audits/{audit_id}/findings
```

### Monitoring

```
GET /api/v1/monitoring/alerts?agent_id={id}
GET /api/v1/monitoring/trends?agent_id={id}&days=30
GET /api/v1/monitoring/category-trends?agent_id={id}&days=30
```

### Metrics

```
GET /api/v1/metrics
```

### Admin

```
POST /api/v1/keys
GET /api/v1/admin/keys
POST /api/v1/admin/secrets/{name}
GET /api/v1/admin/secrets/{name}
POST /api/v1/admin/secrets/{name}/rotate
POST /api/v1/sign
```

## Security

- API keys with scopes, rate limits, expiry, and revocation
- Request signing via `X-Signature-Secret` and `X-Signature`
- Admin audit logging for sensitive actions
- Secret vault for rotating and managing sensitive values

## CI

```bash
pytest
ruff check .
mypy agentinspector backend
alembic check
agentinspector --help
```

## License

MIT
