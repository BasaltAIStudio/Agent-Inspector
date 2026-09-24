# Migrations

## Applying

```bash
alembic upgrade head
```

## Creating

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Files

- `migrations/versions/2026_09_22_1716-19fbfbd0d39e_initial_schema.py`
- `migrations/versions/2026_09_22_1520-a1b2c3d4e5f6_add_agent_name_and_framework.py`

## Rolling back

```bash
alembic downgrade -1
```
