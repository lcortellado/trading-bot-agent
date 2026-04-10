"""
POST /agent/decide — submit a multi-signal bundle to the AI agent.

The agent synthesizes the signals and decides ENTER / SKIP / REDUCE_SIZE.
- SKIP  → no order placed; agent's reason is returned.
- ENTER / REDUCE_SIZE → forwarded to RiskManager → exchange (paper or testnet).

Fallback: if the AI service is unavailable, the agent returns SKIP automatically
(capital is never risked due to an infrastructure failure).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.agent_service import AgentService
from app.api.deps import get_agent_service, get_event_store
from app.dashboard.event_store import DashboardEventStore
from app.schemas.agent import (
    AgentDebugHeadline,
    AgentDebugItem,
    AgentDebugRecentResponse,
    AgentDecisionResponse,
    AgentSignalRequest,
)
from app.schemas.dashboard import DashboardEventKind

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


@router.get(
    "/debug/recent",
    response_model=AgentDebugRecentResponse,
    summary="Recent agent debug context",
    description=(
        "Returns recent AI agent events with decision metadata and optional "
        "news headlines that were attached to the LLM request."
    ),
)
async def agent_debug_recent(
    event_store: Annotated[DashboardEventStore, Depends(get_event_store)],
    limit: int = Query(default=20, ge=1, le=100),
) -> AgentDebugRecentResponse:
    events = await event_store.list_events(limit=500)
    rows: list[AgentDebugItem] = []
    for ev in events:
        if ev.kind != DashboardEventKind.AGENT:
            continue
        detail = ev.detail or {}
        raw_news = detail.get("news_headlines")
        headlines: list[AgentDebugHeadline] = []
        if isinstance(raw_news, list):
            for item in raw_news:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue
                headlines.append(
                    AgentDebugHeadline(
                        title=title,
                        source=item.get("source")
                        if isinstance(item.get("source"), str)
                        else None,
                        url=item.get("url") if isinstance(item.get("url"), str) else None,
                        published_at=item.get("published_at")
                        if isinstance(item.get("published_at"), str)
                        else None,
                    )
                )

        rows.append(
            AgentDebugItem(
                event_id=ev.id,
                ts=ev.ts.isoformat(),
                symbol=ev.symbol,
                decision=detail.get("decision")
                if isinstance(detail.get("decision"), str)
                else None,
                confidence=detail.get("confidence")
                if isinstance(detail.get("confidence"), (int, float))
                else None,
                reason=detail.get("reason") if isinstance(detail.get("reason"), str) else None,
                effective_confidence=detail.get("effective_confidence")
                if isinstance(detail.get("effective_confidence"), (int, float))
                else None,
                size_multiplier=detail.get("size_multiplier")
                if isinstance(detail.get("size_multiplier"), (int, float))
                else None,
                order_executed=detail.get("order_executed")
                if isinstance(detail.get("order_executed"), bool)
                else None,
                news_count=detail.get("news_count")
                if isinstance(detail.get("news_count"), int)
                else len(headlines),
                news_headlines=headlines,
            )
        )
        if len(rows) >= limit:
            break

    return AgentDebugRecentResponse(events=rows)
