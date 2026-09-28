from typing import Optional
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.crypto import encrypt_to_str
from backend.database import Agent, get_db
from backend.dependencies import verify_api_key_and_rate_limit

router = APIRouter()


class AgentCreateRequest(BaseModel):
    name: str
    description: str
    agent_type: str = "custom"
    endpoint: Optional[str] = None
    api_key: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


def _can_see_all(request: Request) -> bool:
    return bool(getattr(request.state, "is_admin", False))


def _owner_filter(request: Request):
    return None if _can_see_all(request) else getattr(request.state, "owner", None)


def _public_agent(agent: Agent) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "agent_type": agent.agent_type,
        "endpoint": agent.endpoint,
        "created_at": agent.created_at.isoformat(),
    }


@router.post("/agents", status_code=201)
async def create_agent(body: AgentCreateRequest, request: Request, api_key: str = Depends(verify_api_key_and_rate_limit), db: Session = Depends(get_db)) -> dict:
    owner = getattr(request.state, "owner", None)
    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db_agent = Agent(id=agent_id, name=body.name, description=body.description, agent_type=body.agent_type, endpoint=body.endpoint, tenant_id=owner)
    if body.api_key:
        db_agent.encrypted_api_key = encrypt_to_str(body.api_key)
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return _public_agent(db_agent)


@router.get("/agents")
async def list_agents(request: Request, api_key: str = Depends(verify_api_key_and_rate_limit), db: Session = Depends(get_db)) -> list:
    query = db.query(Agent)
    owner = _owner_filter(request)
    if owner:
        query = query.filter(Agent.tenant_id == owner)
    return [_public_agent(agent) for agent in query.order_by(Agent.created_at.desc()).all()]


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request, api_key: str = Depends(verify_api_key_and_rate_limit), db: Session = Depends(get_db)) -> dict:
    query = db.query(Agent).filter(Agent.id == agent_id)
    owner = _owner_filter(request)
    if owner:
        query = query.filter(Agent.tenant_id == owner)
    agent = query.first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _public_agent(agent)


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, request: Request, api_key: str = Depends(verify_api_key_and_rate_limit), db: Session = Depends(get_db)) -> dict:
    query = db.query(Agent).filter(Agent.id == agent_id)
    owner = _owner_filter(request)
    if owner:
        query = query.filter(Agent.tenant_id == owner)
    agent = query.first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted", "agent_id": agent_id}
