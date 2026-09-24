# Changelog

## 0.6.0 - 2026-09-23

### Added
- RBAC enforcement via scopes (`audit:read`, `audit:write`, `agent:read`, `agent:write`, `admin`).
- Admin audit logging in `admin_audit_logs` with actor, IP, user-agent, and outcome.
- Secret vault and rotation endpoints (`/api/v1/admin/secrets`, `/rotate`).
- HMAC request signing (`/api/v1/sign`).
- Structured logging with `StructuredFormatter`.
- Metrics endpoint (`/api/v1/metrics`) and operational dashboard (`/api/v1/dashboard`).
- DELETE endpoints for agents and audits.
- Dynamic test generation from failures.
- CI/CD gate with non-zero exit on failure (`--fail-on any|failed|error`).
- Competitive differentiation docs.

### Changed
- Health endpoint probes database connectivity.
- API key creation requires admin scope and logs admin action.

### Security
- Admin audit logging and secret vault for production readiness.
- Request signing behind feature flag (`REQUIRE_REQUEST_SIGNING`).
