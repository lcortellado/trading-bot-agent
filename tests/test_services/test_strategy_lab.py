"""Unit tests for paper strategy lab simulation (no I/O)."""
from decimal import Decimal

import pytest

from app.domain.enums import SignalAction
from app.services.strategy_lab import PaperLane, StrategyLabRuntime, apply_signal_to_lane, build_leaderboard
from app.strategies.base import Strategy
from app.strategies.sma_crossover import SmaCrossoverConfig, SmaCrossoverStrategy, get_available_strategies


def test_buy_then_sell_realizes_pnl() -> None:
    lane = PaperLane(strategy_name="sma_test", symbol="BTCUSDT")
    notional = Decimal("1000")
    apply_signal_to_lane(lane, SignalAction.BUY, Decimal("100"), notional, 0.8, "x")
    assert lane.in_position
    assert lane.entry_price == Decimal("100")
    apply_signal_to_lane(lane, SignalAction.SELL, Decimal("110"), notional, 0.8, "y")
    assert not lane.in_position
    assert lane.trades == 1
    # qty = 1000/100 = 10, pnl = (110-100)*10 = 100
    assert lane.realized_pnl == Decimal("100")
    assert lane.wins == 1
    assert lane.losses == 0


def test_sell_when_flat_is_ignored() -> None:
    lane = PaperLane(strategy_name="a", symbol="X")
    apply_signal_to_lane(lane, SignalAction.SELL, Decimal("1"), Decimal("1000"), 0.5, "")
    assert lane.trades == 0


def test_leaderboard_aggregates_two_symbols() -> None:
    strat: dict[str, Strategy] = {
        "s1": SmaCrossoverStrategy(
            SmaCrossoverConfig(name="s1", description="d1", short_period=3, long_period=5)
        ),
    }
    rt = StrategyLabRuntime(notional_usd=Decimal("1000"))
    a = rt.ensure_lane("s1", "BTCUSDT")
    a.realized_pnl = Decimal("50")
    a.trades = 2
    a.wins = 1
    a.losses = 1
    b = rt.ensure_lane("s1", "ETHUSDT")
    b.realized_pnl = Decimal("25")
    b.trades = 1
    b.wins = 1
    b.losses = 0
    lb = build_leaderboard(rt, strat)
    assert len(lb) == 1
    assert lb[0]["strategy_name"] == "s1"
    assert lb[0]["total_pnl"] == "75"
    assert lb[0]["total_trades"] == 3


@pytest.mark.parametrize(
    ("short", "long", "name"),
    [(9, 21, "sma_crossover"), (5, 15, "sma_5_15"), (13, 34, "sma_13_34")],
)
def test_registry_has_three_sma_presets(short: int, long: int, name: str) -> None:
    reg = get_available_strategies()
    s = reg[name]
    assert isinstance(s, SmaCrossoverStrategy)
    assert s._cfg.short_period == short
    assert s._cfg.long_period == long
