"""
Abstract strategy base.
Strategies are pure functions over candle data → Signal.
They have NO knowledge of orders, risk, or exchange clients.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.models import Candle, Signal


@dataclass
class StrategyConfig:
    """Base config class. Subclasses add strategy-specific parameters."""
    name: str
    description: str = ""


class Strategy(ABC):
    """
    Base class for all trading strategies.

    Strategies are responsible ONLY for signal generation.
    Risk evaluation, position sizing, and order execution live in services.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def description(self) -> str:
        return self.config.description

    @abstractmethod
    def generate_signal(self, candles: list[Candle]) -> Signal:
        """
        Analyse candle history and return a Signal.

        Args:
            candles: Historical candles in ascending time order (oldest first).

        Returns:
            A Signal with action, confidence, and mandatory reason.

        Raises:
            ValueError: If candle data is insufficient or malformed.
        """
        ...

    @abstractmethod
    def min_candles_required(self) -> int:
        """Minimum number of candles needed to produce a valid signal."""
        ...

    def validate_candles(self, candles: list[Candle]) -> None:
        if len(candles) < self.min_candles_required():
            raise ValueError(
                f"Strategy '{self.name}' requires at least "
                f"{self.min_candles_required()} candles, got {len(candles)}"
            )
