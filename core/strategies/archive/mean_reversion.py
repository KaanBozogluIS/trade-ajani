"""Bollinger bandi ortalamaya donus - yatay/range piyasada calismasi beklenir.

trend_filter ONEMLI: guclu trend gunlerinde bantlar "asiri" gorunse de fiyat
trend yonunde gitmeye devam eder (ADX yuksekken mean-reversion tuzaga dusurur).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Signal, Strategy, StrategyResult


class BollingerMeanReversion(Strategy):
    name = "bollinger_mean_reversion"

    def __init__(self, length: int = 20, mult: float = 2.0, rsi_len: int = 14,
                 rsi_oversold: float = 30.0, rsi_overbought: float = 70.0, adx_max: float = 25.0):
        super().__init__(length=length, mult=mult, rsi_len=rsi_len,
                          rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought, adx_max=adx_max)
        self.length, self.mult = length, mult
        self.rsi_len, self.rsi_oversold, self.rsi_overbought = rsi_len, rsi_oversold, rsi_overbought
        self.adx_max = adx_max

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        bb = ta.bollinger(df["close"], self.length, self.mult)
        rsi = ta.rsi(df["close"], self.rsi_len)
        adx = ta.adx(df, 14)["adx"]
        ranging = adx <= self.adx_max

        long_entry = (df["close"] < bb["lower"]) & (rsi < self.rsi_oversold) & ranging
        short_entry = (df["close"] > bb["upper"]) & (rsi > self.rsi_overbought) & ranging
        exit_to_flat = (df["close"] >= bb["mid"]) & (df["close"].shift(1) < bb["mid"].shift(1)) | \
                       (df["close"] <= bb["mid"]) & (df["close"].shift(1) > bb["mid"].shift(1))

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        le, se, ex = long_entry.to_numpy(), short_entry.to_numpy(), exit_to_flat.to_numpy()
        for i in range(len(df)):
            if pos == 0:
                if le[i]:
                    pos = 1
                elif se[i]:
                    pos = -1
            elif ex[i]:
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"bb_mid": bb["mid"], "bb_upper": bb["upper"], "bb_lower": bb["lower"],
                              "rsi": rsi, "adx": adx})
        return StrategyResult(signal=signal, diagnostics=diag)
