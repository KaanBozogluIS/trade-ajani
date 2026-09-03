"""Strateji arayuzu.

Bir strateji, OHLCV + gostergeleri girdi olarak alir, her mum icin bir
Signal (LONG/SHORT/FLAT) uretir. Pozisyon yonetimi, komisyon, slipaj
BURADA DEGIL backtest.py'de - stratejiler her zaman 'saf sinyal' uretir,
boylece ayni strateji hem backtestte hem canli sinyal servisinde
degismeden calisir.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum

import pandas as pd


class Signal(IntEnum):
    SHORT = -1
    FLAT = 0
    LONG = 1


@dataclass
class StrategyResult:
    signal: pd.Series          # Signal degerleri, df ile ayni indeks
    diagnostics: pd.DataFrame = field(default_factory=pd.DataFrame)  # grafikte gosterilecek gostergeler
    stop_loss: pd.Series | None = None    # opsiyonel, fiyat seviyesi
    take_profit: pd.Series | None = None  # opsiyonel, fiyat seviyesi


class Strategy(ABC):
    """Alt siniflar `params` sozlugunu __init__'te tuketmeli - optimizer bunu kullanir."""

    name: str = "base"

    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def generate(self, df: pd.DataFrame) -> StrategyResult:
        """df: OHLCV, UTC DatetimeIndex, artan sirali, YALNIZCA KAPALI mumlar."""

    def __repr__(self) -> str:
        p = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.name}({p})"
