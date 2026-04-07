# Crypto Trading Bot

A clean-architecture Python trading bot with paper trading, Binance Testnet support, and a FastAPI interface.

## Architecture

```
frontend/               # React (Vite + TypeScript) — panel web; build → servido en /dashboard
app/
├── core/               # Config (pydantic-settings) + structured logging
├── domain/             # Pure domain models and enums (no framework deps)
├── schemas/            # Pydantic API request/response schemas
├── exchange/           # Abstract ExchangeClient + BinanceClient (testnet)
├── strategies/         # Strategy interface + SMA Crossover implementation
├── risk_management/    # RiskManager — enforces capital protection rules
├── agents/             # AI decision layer: AIDecisionClient, AgentService, schemas
├── dashboard/          # DashboardEventStore (in-memory ring buffer for /dashboard)
├── templates/          # (reserved; web UI is React in frontend/)
├── services/           # Orchestration: MarketDataService, SignalService, PositionMonitor
└── api/routes/         # FastAPI routes: /health /strategy /signal /agent /dashboard
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

`REDUCE_SIZE` halves the agent-forwarded `size_multiplier` (default `0.5`) while scaling confidence. `POST /signal` accepts optional `size_multiplier` (0.01–1.0) to scale notional. Open positions lock paper capital until close; shorts use SL above entry and TP below. Claude API calls honor `AI_TIMEOUT` (seconds).

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

### 3. Run locally (API)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: http://localhost:8000 · Docs: http://localhost:8000/docs

### 4. Web UI (React) — recomendado para desarrollo

**Modo desarrollo** (Vite con proxy al API en :8000):

```bash
# Terminal 1
uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm install && npm run dev
```

Abre **http://localhost:5173** — formularios para señal, agente IA y estrategia SMA.

**Modo un solo servidor** (compilar y servir bajo `/dashboard`):

```bash
cd frontend && npm install && npm run build
cd .. && uvicorn app.main:app --reload --port 8000
```

Abre **http://localhost:8000/dashboard/** (requiere `frontend/dist` generado por `npm run build`).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + exchange connectivity check |
| GET | `/strategy` | List available strategies |
| POST | `/strategy/run` | Run a strategy on live market data |
| POST | `/signal` | Submit a signal for risk evaluation + order |
| POST | `/agent/decide` | Submit a multi-signal bundle to the AI agent |
| GET | `/dashboard/` | SPA React (tras `npm run build` en `frontend/`) |
| GET | `/api/dashboard/events` | JSON feed of recent decisions (in-memory ring buffer) |
| GET | `/api/dashboard/snapshot` | Paper capital, daily PnL, open positions |

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

**Option A — ChatGPT (OpenAI API)**  
2. Set `AI_PROVIDER=openai` and `OPENAI_API_KEY=<key>` from [platform.openai.com](https://platform.openai.com/api-keys).  
3. Optionally set `OPENAI_MODEL` (default: `gpt-4o-mini`).

**Option B — Claude (Anthropic)**  
2. Set `AI_PROVIDER=anthropic` (or omit) and `AI_API_KEY=<key>` from [console.anthropic.com](https://console.anthropic.com/).  
3. Optionally tune `AI_MODEL` (default: `claude-haiku-4-5-20251001`).

Then call `POST /agent/decide` with a signal bundle. Tune `AI_TIMEOUT` (default: 15 s) if needed.

**Fallback behaviour**: if the matching API key is empty or the API is unreachable, the agent
returns `SKIP` — no order is placed and capital is preserved.

## Position monitoring

The position monitor starts automatically on app startup as a background task.
It polls open positions every `POSITION_MONITOR_INTERVAL` seconds (default: 30).
When a stop-loss or take-profit level is hit, it places a MARKET close order
(paper-simulated or testnet) and logs the reason via the structured decision logger.

To adjust the check frequency: set `POSITION_MONITOR_INTERVAL=<seconds>` in `.env`.

## Automatic trading loop

When `AUTO_TRADING_ENABLED=true`, a background task runs every
`AUTO_TRADING_INTERVAL_SECONDS` (minimum 30). For each symbol in `AUTO_TRADING_SYMBOLS`
(comma-separated), it loads candles (`AUTO_TRADING_TIMEFRAME`, `AUTO_TRADING_CANDLE_LIMIT`),
runs every strategy listed in `AUTO_TRADING_STRATEGIES`, picks the strongest BUY/SELL signal,
then either sends the bundle to the AI (`AUTO_TRADING_USE_AI=true`, same as `POST /agent/decide`)
or applies the strongest signal directly through the risk layer (`AUTO_TRADING_USE_AI=false`).

- `AUTO_TRADING_SKIP_IF_OPEN=true` skips symbols that already have an open position.
- `AUTO_TRADING_COOLDOWN_SECONDS` enforces a per-symbol quiet period after a successful auto order.

This remains **paper or testnet only** — controlled by `TRADING_MODE` like the rest of the app.
Restart the API after changing these variables (`get_settings()` is cached per process).

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
