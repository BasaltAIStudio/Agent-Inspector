import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import APIKeyRecord, get_db
from backend.dependencies import verify_admin_api_key, verify_api_key_and_rate_limit, _build_scope_spec, _get_secret, _hash_api_key, _log_admin_action, _sign_payload

router = APIRouter()


@router.post("/keys")
async def create_api_key(
    owner: str,
    rate_limit: int = 100,
    scopes: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    api_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None
        _log_admin_action(db, "api_key.create", api_key, "api_key", None, ip_address, user_agent, success=True)
    except Exception:
        pass
    key = "ai_" + secrets.token_hex(24)
    key_id = "key_" + secrets.token_hex(12)
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    record = APIKeyRecord(key=key_id, hashed_key=_hash_api_key(key), owner=owner, rate_limit=rate_limit, scopes=scopes or _build_scope_spec(None), expires_at=expires_at)
    db.add(record)
    db.commit()
    return {
        "api_key": key,
        "key_id": key_id,
        "owner": owner,
        "rate_limit": rate_limit,
        "scopes": scopes or _build_scope_spec(None),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


@router.delete("/keys/{api_key}")
async def revoke_api_key(
    key_id: str,
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    record = db.query(APIKeyRecord).filter(APIKeyRecord.key == key_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    record.revoked = True
    db.add(record)
    try:
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None
        _log_admin_action(db, "api_key.revoke", admin_key, "api_key", key_id, ip_address, user_agent, success=True)
    except Exception:
        pass
    db.commit()
    return {"message": "API key revoked", "key_id": key_id}


@router.post("/sign")
async def sign_payload(
    secret_name: str,
    payload: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    secret = _get_secret(db, secret_name)
    if not secret:
        raise HTTPException(status_code=404, detail="Signing secret not found")
    signature = _sign_payload(secret, payload)
    return {"secret_name": secret_name, "payload": payload, "signature": signature}
