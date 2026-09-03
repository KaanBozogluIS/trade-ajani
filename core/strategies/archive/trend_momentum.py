"""MACD + uzun EMA trend filtresi ile momentum stratejisi. Intraday'e de swing'e de uyarlanabilir."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Signal, Strategy, StrategyResult


class TrendMomentum(Strategy):
    name = "trend_momentum"

    def __init__(self, ema_trend: int = 100, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9):
        super().__init__(ema_trend=ema_trend, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal)
        self.ema_trend = ema_trend
        self.macd_fast, self.macd_slow, self.macd_signal = macd_fast, macd_slow, macd_signal

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        trend = ta.ema(df["close"], self.ema_trend)
        macd_df = ta.macd(df["close"], self.macd_fast, self.macd_slow, self.macd_signal)

        long_cond = (df["close"] > trend) & ta.crossover(macd_df["macd"], macd_df["signal"])
        short_cond = (df["close"] < trend) & ta.crossunder(macd_df["macd"], macd_df["signal"])
        # Trend yon degistirince pozisyonu kapat (macd karsi kesisimi beklemeden).
        flat_cond = (df["close"] > trend) != (df["close"].shift(1) > trend.shift(1))

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        lc, sc, fc = long_cond.to_numpy(), short_cond.to_numpy(), flat_cond.to_numpy()
        for i in range(len(df)):
            if fc[i]:
                pos = 0
            if lc[i]:
                pos = 1
            elif sc[i]:
                pos = -1
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"ema_trend": trend, "macd": macd_df["macd"], "macd_signal": macd_df["signal"]})
        return StrategyResult(signal=signal, diagnostics=diag)
