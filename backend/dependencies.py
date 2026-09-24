from typing import Any, Dict, List, Optional
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from backend.database import APIKeyRecord, AdminAuditLog, SecretVault, get_db


class RateLimiter:
    def __init__(self):
        self._requests: Dict[str, List[float]] = {}
        self._window = 60.0

    def is_allowed(self, key: str, limit: int) -> bool:
        import time

        now = time.time()
        if key not in self._requests:
            self._requests[key] = []
        self._requests[key] = [t for t in self._requests[key] if now - t < self._window]
        if len(self._requests[key]) >= limit:
            return False
        self._requests[key].append(now)
        return True


class IPBlocklist:
    def __init__(self):
        self._blocked: Dict[str, datetime] = {}

    def block(self, ip: str, duration_seconds: int = 3600) -> None:
        self._blocked[ip] = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

    def is_blocked(self, ip: str) -> bool:
        if ip not in self._blocked:
            return False
        if datetime.now(timezone.utc) > self._blocked[ip]:
            del self._blocked[ip]
            return False
        return True


rate_limiter = RateLimiter()
ip_blocklist = IPBlocklist()


def _get_key_record(api_key: str, db: Session) -> Optional[APIKeyRecord]:
    return db.query(APIKeyRecord).filter(APIKeyRecord.key == api_key, APIKeyRecord.revoked == False).first()


def _enforce_scope(record: APIKeyRecord, required_scope: str) -> None:
    scopes = {s.strip() for s in record.scopes.split(",") if s.strip()}
    if required_scope not in scopes and "admin" not in scopes:
        raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")


def _log_admin_action(
    db: Session,
    action: str,
    actor_key: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    log = AdminAuditLog(
        action=action,
        actor_key=actor_key,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        error=error,
    )
    db.add(log)
    db.commit()


def _set_secret(db: Session, name: str, value: str) -> None:
    existing = _get_secret(db, name)
    if existing:
        secret = db.query(SecretVault).filter(SecretVault.name == name).first()
        if secret:
            secret.value = value
            db.add(secret)
            db.commit()
            return
    secret = SecretVault(name=name, value=value)
    db.add(secret)
    db.commit()


def _get_secret(db: Session, name: str) -> Optional[str]:
    record = db.query(SecretVault).filter(SecretVault.name == name).first()
    if not record:
        return None
    return record.value


def _sign_payload(secret: str, payload: str) -> str:
    import hashlib
    import hmac

    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_signature(secret: str, payload: str, signature: str) -> bool:
    import hmac

    expected = _sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)


def _build_scope_spec(raw_scopes: Optional[str]) -> str:
    return raw_scopes or "audit:read,audit:write,agent:read"


def _current_scope_set(raw_scopes: str) -> set:
    return {s.strip() for s in raw_scopes.split(",") if s.strip()}


async def verify_api_key_and_rate_limit(
    request: Request,
    db: Session = Depends(get_db),
    required_scope: Optional[str] = None,
) -> str:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    client_ip = request.client.host if request.client else None
    if client_ip and ip_blocklist.is_blocked(client_ip):
        raise HTTPException(status_code=403, detail="IP address blocked")
    
    record = _get_key_record(api_key, db)
    if not record:
        raise HTTPException(status_code=403, detail="Invalid API key")
    if record.expires_at and record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="API key expired")
    if not rate_limiter.is_allowed(api_key, record.rate_limit):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    record.last_used_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
    if required_scope:
        _enforce_scope(record, required_scope)
    return api_key


async def verify_admin_api_key(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    api_key = await verify_api_key_and_rate_limit(request, db)
    record = _get_key_record(api_key, db)
    _enforce_scope(record, "admin")
    return api_key
