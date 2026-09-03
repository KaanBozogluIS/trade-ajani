"""RSI(2) pullback - Larry Connors tarzi: guclu bir trend icindeyken kisa
sureli asiri satim/alim anlarinda trend yonunde pozisyon acar.

Bollinger ortalamaya donusten farki: o strateji YATAY piyasada simetrik
alim/satim yapar; bu strateji trend filtresi ZORUNLU - sadece trend
yonunde, trendin "nefes almasini" (gecici geri cekilme) hedefler. Cok
kisa RSI (uzunluk=2) kullanildigi icin sinyaller hizli ve sik gelir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class Rsi2Pullback(Strategy):
    name = "rsi2_pullback"

    def __init__(self, trend_len: int = 200, rsi_len: int = 2,
                 oversold: float = 10.0, overbought: float = 90.0, exit_rsi: float = 70.0):
        super().__init__(trend_len=trend_len, rsi_len=rsi_len, oversold=oversold,
                          overbought=overbought, exit_rsi=exit_rsi)
        self.trend_len, self.rsi_len = trend_len, rsi_len
        self.oversold, self.overbought, self.exit_rsi = oversold, overbought, exit_rsi

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        trend = ta.sma(df["close"], self.trend_len)
        rsi = ta.rsi(df["close"], self.rsi_len)

        uptrend = df["close"] > trend
        downtrend = df["close"] < trend

        long_entry = uptrend & (rsi < self.oversold)
        short_entry = downtrend & (rsi > self.overbought)
        long_exit = (rsi > self.exit_rsi) | ~uptrend
        short_exit = (rsi < (100.0 - self.exit_rsi)) | ~downtrend

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        le, se = long_entry.to_numpy(), short_entry.to_numpy()
        lx, sx = long_exit.to_numpy(), short_exit.to_numpy()
        for i in range(len(df)):
            if pos == 0:
                if le[i]:
                    pos = 1
                elif se[i]:
                    pos = -1
            elif pos == 1 and lx[i]:
                pos = 0
            elif pos == -1 and sx[i]:
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"trend_sma": trend, "rsi2": rsi})
        return StrategyResult(signal=signal, diagnostics=diag)
