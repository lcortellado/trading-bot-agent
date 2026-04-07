"""
POST /agent/decide — submit a multi-signal bundle to the AI agent.

The agent synthesizes the signals and decides ENTER / SKIP / REDUCE_SIZE.
- SKIP  → no order placed; agent's reason is returned.
- ENTER / REDUCE_SIZE → forwarded to RiskManager → exchange (paper or testnet).

Fallback: if the AI service is unavailable, the agent returns SKIP automatically
(capital is never risked due to an infrastructure failure).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.agents.agent_service import AgentService
from app.api.deps import get_agent_service
from app.schemas.agent import AgentDecisionResponse, AgentSignalRequest

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.post(
    "/decide",
    response_model=AgentDecisionResponse,
    summary="AI multi-signal decision",
    description=(
        "Submit a bundle of trading signals to the AI agent. "
        "Returns the agent's decision (ENTER/SKIP/REDUCE_SIZE) with a mandatory reason "
        "and, if an order was placed, the order details."
    ),
)
async def agent_decide(
    body: AgentSignalRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentDecisionResponse:
    try:
        return await agent_service.process(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {exc}")
