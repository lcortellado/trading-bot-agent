"""HTTP tests for dashboard routes (uses full app lifespan)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.conftest import make_settings

_FRONTEND_INDEX = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html"
)


@pytest.mark.skipif(
    not _FRONTEND_INDEX.is_file(),
    reason="Run `cd frontend && npm run build` to enable SPA smoke test",
)
def test_dashboard_spa_served_when_dist_exists() -> None:
    """Production: React build mounted at /dashboard."""
    with TestClient(app) as client:
        r = client.get("/dashboard/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert "root" in r.text


def test_dashboard_snapshot() -> None:
    with TestClient(app) as client:
        r = client.get("/api/dashboard/snapshot")
        assert r.status_code == 200
        data = r.json()
        assert "capital" in data
        assert "daily_pnl" in data
        assert data["open_positions"] == 0
        assert data["positions"] == []


def test_dashboard_strategy_lab_response_when_disabled_in_settings() -> None:
    """Override settings so the test is independent of STRATEGY_LAB_ENABLED in developer .env."""

    def _settings_off() -> object:
        return make_settings(strategy_lab_enabled=False)

    app.dependency_overrides[get_settings] = _settings_off
    try:
        with TestClient(app) as client:
            r = client.get("/api/dashboard/strategy-lab")
            assert r.status_code == 200
            data = r.json()
            assert data["enabled"] is False
            assert data["last_tick_at"] is None
            assert data["tick_count"] == 0
            assert data["rows"] == []
            assert data["leaderboard"] == []
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_dashboard_public_config_no_secrets() -> None:
    """GET /api/dashboard/config returns safe fields only (no API key strings)."""
    with TestClient(app) as client:
        r = client.get("/api/dashboard/config")
        assert r.status_code == 200
        raw = r.text.lower()
        assert "sk-" not in raw  # typical key prefix should not appear
        data = r.json()
        assert "api_key" not in data
        assert "secret" not in data
        assert data["app_name"]
        assert "trading_mode" in data
        assert "auto_trading_enabled" in data
        assert isinstance(data["ai_anthropic_key_configured"], bool)
        assert isinstance(data["ai_openai_key_configured"], bool)
        assert isinstance(data["news_context_enabled"], bool)
        assert isinstance(data["news_cryptopanic_configured"], bool)


def test_signal_post_appends_dashboard_event() -> None:
    with TestClient(app) as client:
        body = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "action": "buy",
            "strategy_name": "manual_test",
            "confidence": 0.85,
            "reason": "Dashboard integration test",
            "price": "50000",
        }
        sig = client.post("/signal", json=body)
        assert sig.status_code == 202

        ev = client.get("/api/dashboard/events?limit=10")
        assert ev.status_code == 200
        rows = ev.json()["events"]
        assert len(rows) >= 1
        signal_rows = [r for r in rows if r.get("kind") == "signal"]
        assert signal_rows, "Expected at least one signal event in feed"
        latest = signal_rows[0]
        assert latest["symbol"] == "BTCUSDT"
        assert latest["detail"]["strategy"] == "manual_test"


def test_agent_debug_recent_endpoint() -> None:
    with TestClient(app) as client:
        body = {
            "primary_signal": {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "action": "buy",
                "strategy_name": "manual_agent_debug",
                "confidence": 0.8,
                "reason": "Debug endpoint seed",
                "price": "50000",
            },
            "signals": [
                {
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "action": "buy",
                    "strategy_name": "manual_agent_debug",
                    "confidence": 0.8,
                    "reason": "Debug endpoint seed",
                    "price": "50000",
                }
            ],
        }
        r = client.post("/agent/decide", json=body)
        assert r.status_code == 200

        debug = client.get("/agent/debug/recent?limit=5")
        assert debug.status_code == 200
        data = debug.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert len(data["events"]) >= 1

        first = data["events"][0]
        assert first["symbol"] == "BTCUSDT"
        assert "decision" in first
        assert "reason" in first
        assert "news_headlines" in first
        assert "news_count" in first
