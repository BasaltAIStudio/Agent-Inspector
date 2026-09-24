from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.dependencies import verify_api_key_and_rate_limit

router = APIRouter()


class DemoAgentRequest(BaseModel):
    prompt: str
    model: Optional[str] = "gpt-4o-mini"
    provider: Optional[str] = "openai"


class DemoAgentResponse(BaseModel):
    response: str
    provider: str
    model: str


@router.post("/demo/agent", response_model=DemoAgentResponse)
async def demo_agent(
    body: DemoAgentRequest,
    _: str = Depends(verify_api_key_and_rate_limit),
) -> DemoAgentResponse:
    import os
    import httpx

    provider = body.provider.lower()
    model = body.model

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": body.prompt}],
                    "max_tokens": 512,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        return DemoAgentResponse(response=text, provider="openai", model=model)

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": body.prompt}],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
        return DemoAgentResponse(response=text, provider="anthropic", model=model)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}. Use 'openai' or 'anthropic'.")
