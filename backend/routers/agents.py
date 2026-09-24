from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import Agent, get_db
from backend.dependencies import verify_api_key_and_rate_limit

router = APIRouter()


@router.post("/agents", status_code=201)
async def create_agent(body: dict, db: Session = Depends(get_db)) -> dict:
    from datetime import datetime, timezone
    import uuid

    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db_agent = Agent(
        id=agent_id,
        name=body["name"],
        description=body["description"],
        agent_type=body.get("agent_type", "custom"),
        endpoint=body.get("endpoint"),
        api_key=body.get("api_key"),
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return {
        "id": db_agent.id,
        "name": db_agent.name,
        "description": db_agent.description,
        "agent_type": db_agent.agent_type,
        "endpoint": db_agent.endpoint,
        "created_at": db_agent.created_at.isoformat(),
    }


@router.get("/agents")
async def list_agents(db: Session = Depends(get_db)) -> list:
    agents = db.query(Agent).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "agent_type": a.agent_type,
            "endpoint": a.endpoint,
            "created_at": a.created_at.isoformat(),
        }
        for a in agents
    ]


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)) -> dict:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "agent_type": agent.agent_type,
        "endpoint": agent.endpoint,
        "created_at": agent.created_at.isoformat(),
    }


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> dict:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted", "agent_id": agent_id}
