from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.database import (
    AdminAuditLog,
    Agent,
    APIKeyRecord,
    SecretVault,
    get_db,
)
from backend.dependencies import verify_admin_api_key

router = APIRouter()


@router.get("/logs")
async def list_admin_logs(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
    limit: int = 100,
) -> List[dict]:
    logs = db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(min(limit, 500)).all()
    from backend.dependencies import _log_admin_action

    _log_admin_action(
        db,
        "admin.logs.read",
        admin_key,
        "admin_audit_log",
        None,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )
    return [
        {
            "id": l.id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "actor_key": l.actor_key,
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "success": l.success,
            "error": l.error,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/keys")
async def list_keys(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    keys = db.query(APIKeyRecord).all()
    from backend.dependencies import _log_admin_action

    _log_admin_action(
        db,
        "admin.keys.read",
        admin_key,
        "api_key",
        None,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )
    return {
        "keys": [
            {
                "key": k.key,
                "owner": k.owner,
                "rate_limit": k.rate_limit,
                "scopes": k.scopes,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "revoked": k.revoked,
            }
            for k in keys
        ]
    }


@router.get("/admin/agents")
async def list_agents_admin(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    agents = db.query(Agent).all()
    from backend.dependencies import _log_admin_action

    _log_admin_action(
        db,
        "admin.agents.read",
        admin_key,
        "agent",
        None,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "agent_type": a.agent_type,
                "endpoint": a.endpoint,
                "api_key": a.api_key,
            }
            for a in agents
        ]
    }


@router.post("/secrets/{name}")
async def upsert_secret(
    name: str,
    value: str,
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    from backend.dependencies import _get_secret, _log_admin_action, _set_secret

    existing = _get_secret(db, name)
    if existing:
        _log_admin_action(
            db,
            "secret.update",
            admin_key,
            "secret",
            name,
            request.client.host if request and request.client else None,
            request.headers.get("user-agent") if request else None,
            success=True,
        )
    else:
        _log_admin_action(
            db,
            "secret.create",
            admin_key,
            "secret",
            name,
            request.client.host if request and request.client else None,
            request.headers.get("user-agent") if request else None,
            success=True,
        )
    _set_secret(db, name, value)
    return {"name": name, "updated": str(bool(existing))}


@router.get("/secrets/{name}")
async def read_secret(
    name: str,
    admin_key: str = Depends(verify_admin_api_key),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    from backend.dependencies import _get_secret, _log_admin_action

    value = _get_secret(db, name)
    if value is None:
        raise HTTPException(status_code=404, detail="Secret not found")
    _log_admin_action(db, "secret.read", admin_key, "secret", name, None, None, success=True)
    return {"name": name, "value": value}


@router.post("/secrets/{name}/rotate")
async def rotate_secret(
    name: str,
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    import secrets

    from backend.dependencies import _log_admin_action, _set_secret

    _set_secret(db, name, secrets.token_hex(32))
    _log_admin_action(
        db,
        "secret.rotate",
        admin_key,
        "secret",
        name,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )
    return {"name": name, "rotated": "true"}


@router.post("/backup")
async def create_backup(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    import json
    import hashlib
    import os
    from datetime import datetime, timezone

    backup_dir = os.getenv("BACKUP_DIR", "./backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.json"
    filepath = os.path.join(backup_dir, filename)

    data = {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "agent_type": a.agent_type,
                "endpoint": a.endpoint,
                "created_at": a.created_at.isoformat(),
            }
            for a in db.query(Agent).all()
        ],
        "audits": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "status": r.status,
                "overall_score": r.overall_score,
                "created_at": r.created_at.isoformat(),
            }
            for r in db.query(Audit).all()
        ],
        "findings": [
            {
                "id": f.id,
                "audit_id": f.audit_id,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
            }
            for f in db.query(Finding).all()
        ],
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    checksum = hashlib.sha256(open(filepath, "rb").read()).hexdigest()
    size_bytes = os.path.getsize(filepath)

    record = BackupRecord(path=filepath, size_bytes=size_bytes, checksum=checksum)
    db.add(record)
    db.commit()

    from backend.dependencies import _log_admin_action

    _log_admin_action(
        db,
        "backup.create",
        admin_key,
        "backup",
        record.id,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )

    return {"backup_id": record.id, "path": filepath, "size_bytes": size_bytes, "checksum": checksum}


@router.post("/restore")
async def restore_backup(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
    backup_path: str = None,
) -> Dict[str, str]:
    if not backup_path:
        raise HTTPException(status_code=400, detail="backup_path is required")

    import json

    with open(backup_path, "r") as f:
        data = json.load(f)

    restored_agents = 0
    for agent_data in data.get("agents", []):
        existing = db.query(Agent).filter(Agent.id == agent_data["id"]).first()
        if not existing:
            db.add(Agent(**agent_data))
            restored_agents += 1

    db.commit()

    from backend.dependencies import _log_admin_action

    _log_admin_action(
        db,
        "backup.restore",
        admin_key,
        "backup",
        backup_path,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )

    return {"restored_agents": restored_agents, "status": "completed"}
