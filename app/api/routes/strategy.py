"""
GET  /strategy        — list available strategies
POST /strategy/run    — run a strategy against live market data and return the signal
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SettingsDep, get_market_data_service, get_strategies
from app.domain.enums import Timeframe
from app.schemas.strategy import RunStrategyRequest, RunStrategyResponse, StrategyListResponse, StrategyInfo
from app.services.market_data import MarketDataService
from app.strategies.base import Strategy

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    strategies: Annotated[dict[str, Strategy], Depends(get_strategies)],
) -> StrategyListResponse:
    items = [
        StrategyInfo(
            name=s.name,
            description=s.description,
            parameters={},
        )
        for s in strategies.values()
    ]
    return StrategyListResponse(strategies=items, total=len(items))


@router.post("/run", response_model=RunStrategyResponse)
async def run_strategy(
    body: RunStrategyRequest,
    strategies: Annotated[dict[str, Strategy], Depends(get_strategies)],
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
) -> RunStrategyResponse:
    strategy = strategies.get(body.strategy_name)
    if strategy is None:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{body.strategy_name}' not found. "
                   f"Available: {list(strategies.keys())}",
        )

    min_candles = strategy.min_candles_required()
    limit = max(body.limit, min_candles)

    try:
        candles = await market_data.get_candles(body.symbol, body.timeframe, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    try:
        signal = strategy.generate_signal(candles)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return RunStrategyResponse(
        strategy_name=signal.strategy_name,
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        action=signal.action.value,
        confidence=signal.confidence,
        reason=signal.reason,
        candles_analyzed=len(candles),
    )
