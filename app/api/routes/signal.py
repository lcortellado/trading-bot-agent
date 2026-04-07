"""
POST /signal    — receive and process an external trading signal
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_signal_service
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.signal_service import SignalService

router = APIRouter(prefix="/signal", tags=["signal"])


@router.post("", response_model=SignalResponse, status_code=202)
async def receive_signal(
    body: SignalRequest,
    signal_service: Annotated[SignalService, Depends(get_signal_service)],
) -> SignalResponse:
    """
    Process an inbound trading signal.
    The signal is validated, run through risk management, and — if approved —
    an order is placed (paper-simulated or testnet depending on config).

    Returns 202 Accepted regardless of whether the signal was acted on.
    Check `accepted` and `risk_check_passed` in the response body.
    """
    try:
        return await signal_service.process_signal(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Signal processing failed: {exc}")
