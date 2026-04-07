# Crypto Trading Bot

A clean-architecture Python trading bot with paper trading, Binance Testnet support, and a FastAPI interface.

## Architecture

```
app/
├── core/               # Config (pydantic-settings) + structured logging
├── domain/             # Pure domain models and enums (no framework deps)
├── schemas/            # Pydantic API request/response schemas
├── exchange/           # Abstract ExchangeClient + BinanceClient (testnet)
├── strategies/         # Strategy interface + SMA Crossover implementation
├── risk_management/    # RiskManager — enforces capital protection rules
├── agents/             # AI decision layer: AIDecisionClient, AgentService, schemas
├── services/           # Orchestration: MarketDataService, SignalService, PositionMonitor
└── api/routes/         # FastAPI thin routes: /health /strategy /signal /agent
```

**Key design decisions:**
- Strategies are pure functions: candles in → Signal out. No exchange, no risk logic.
- Risk Manager is stateless: caller provides capital/positions/drawdown state.
- AI agent is an *additional* reasoning layer — RiskManager remains the hard capital barrier.
- Exchange client is abstract: swap Binance for any other exchange without touching services.
- TA-Lib excluded: SMA computed with pandas rolling mean (zero C compilation needed).
- Trading mode defaults to `paper` — no live trading mode exists (by design).

### Decision flow with AI agent

```
POST /agent/decide
  └─ AgentService
       ├─ AIDecisionClient (Claude API) → ENTER | SKIP | REDUCE_SIZE
       │    └─ Fallback: always SKIP if AI unavailable
       ├─ SKIP  → return immediately, no order
       └─ ENTER/REDUCE_SIZE
            └─ SignalService
                 ├─ RiskManager (hard capital rules — always runs)
                 └─ ExchangeClient (paper simulate or testnet order)
```

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env if you want testnet mode (get keys from https://testnet.binance.vision/)
```

### 2. Run with Docker

```bash
docker compose up --build
```

### 3. Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API available at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + exchange connectivity check |
| GET | `/strategy` | List available strategies |
| POST | `/strategy/run` | Run a strategy on live market data |
| POST | `/signal` | Submit a signal for risk evaluation + order |
| POST | `/agent/decide` | Submit a multi-signal bundle to the AI agent |

### Example: Run SMA Crossover on BTCUSDT

```bash
curl -X POST http://localhost:8000/strategy/run \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "sma_crossover", "symbol": "BTCUSDT", "timeframe": "1h", "limit": 100}'
```

### Example: Submit a signal manually

```bash
curl -X POST http://localhost:8000/signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "action": "buy",
    "strategy_name": "sma_crossover",
    "confidence": 0.75,
    "reason": "Golden cross: SMA9 crossed above SMA21",
    "price": "50000"
  }'
```

### Example: AI agent multi-signal decision

```bash
curl -X POST http://localhost:8000/agent/decide \
  -H "Content-Type: application/json" \
  -d '{
    "primary_signal": {
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "action": "buy",
      "strategy_name": "sma_crossover",
      "confidence": 0.75,
      "reason": "Golden cross: SMA9 crossed above SMA21",
      "price": "50000"
    },
    "signals": [
      {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "action": "buy",
        "strategy_name": "sma_crossover",
        "confidence": 0.75,
        "reason": "Golden cross: SMA9 crossed above SMA21",
        "price": "50000"
      }
    ],
    "market_context": {
      "volume_ratio": 1.4,
      "volatility_24h": 0.025,
      "trend": "bullish"
    }
  }'
```

The response includes `agent_decision` (ENTER/SKIP/REDUCE_SIZE), `agent_reason`, and
`signal_response` with the order details if an order was placed.

## Activating the AI agent

1. Copy `.env.example` to `.env`.
2. Set `AI_API_KEY=<your Anthropic key>` (get one at https://console.anthropic.com/).
3. Optionally tune `AI_MODEL` (default: `claude-haiku-4-5-20251001`) and `AI_TIMEOUT` (default: 15 s).
4. Call `POST /agent/decide` with a signal bundle.

**Fallback behaviour**: if `AI_API_KEY` is empty or the API is unreachable, the agent
automatically returns `SKIP` — no order is placed and capital is preserved.

## Position monitoring

The position monitor starts automatically on app startup as a background task.
It polls open positions every `POSITION_MONITOR_INTERVAL` seconds (default: 30).
When a stop-loss or take-profit level is hit, it places a MARKET close order
(paper-simulated or testnet) and logs the reason via the structured decision logger.

To adjust the check frequency: set `POSITION_MONITOR_INTERVAL=<seconds>` in `.env`.

## Running Tests

```bash
pytest -v
```

## Trading Modes

| Mode | Orders | Exchange calls |
|------|--------|---------------|
| `paper` | Simulated locally | Market data only (no auth needed) |
| `testnet` | Sent to testnet.binance.vision | Requires API keys from testnet |

Set `TRADING_MODE=testnet` in `.env` and add your testnet API keys to enable testnet execution.

## Next Steps

- [ ] Backtesting engine (`app/backtesting/`)
- [ ] SQLAlchemy persistence layer (`app/repositories/`)
- [ ] Additional strategies (RSI, Bollinger Bands, MACD)
- [ ] WebSocket price streaming
- [ ] Position tracking across restarts
- [ ] Prometheus metrics + Grafana dashboard
- [ ] Alembic migrations setup
