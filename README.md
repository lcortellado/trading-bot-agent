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
├── services/           # Orchestration: MarketDataService, SignalService
└── api/routes/         # FastAPI thin routes: /health /strategy /signal
```

**Key design decisions:**
- Strategies are pure functions: candles in → Signal out. No exchange, no risk logic.
- Risk Manager is stateless: caller provides capital/positions/drawdown state.
- Exchange client is abstract: swap Binance for any other exchange without touching services.
- TA-Lib excluded: SMA computed with pandas rolling mean (zero C compilation needed).
- Trading mode defaults to `paper` — no live trading mode exists (by design).

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
