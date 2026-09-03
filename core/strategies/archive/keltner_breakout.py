"""Keltner kanali kirilimi - oynaklik genislemesi stratejisi.

Donchian kirilimindan farki: Donchian sabit N-bar en yuksek/en dusuk
kullanir (yavas, "temiz" seviyeler); Keltner EMA+ATR bandi kullanir
(daha hizli tepki verir, oynakligin ANI genislemesini yakalamayi hedefler
- ozellikle sikismadan sonraki patlamalarda).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class KeltnerBreakout(Strategy):
    name = "keltner_breakout"

    def __init__(self, ema_len: int = 20, atr_len: int = 20, mult: float = 1.5, adx_min: float = 20.0):
        super().__init__(ema_len=ema_len, atr_len=atr_len, mult=mult, adx_min=adx_min)
        self.ema_len, self.atr_len, self.mult, self.adx_min = ema_len, atr_len, mult, adx_min

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        kc = ta.keltner(df, self.ema_len, self.atr_len, self.mult)
        adx = ta.adx(df, 14)["adx"]
        trending = adx >= self.adx_min

        enter_long = (df["close"] > kc["upper"]) & trending
        enter_short = (df["close"] < kc["lower"]) & trending
        exit_long = df["close"] < kc["mid"]
        exit_short = df["close"] > kc["mid"]

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        el, es = enter_long.to_numpy(), enter_short.to_numpy()
        xl, xs = exit_long.to_numpy(), exit_short.to_numpy()
        for i in range(len(df)):
            if pos == 0:
                if el[i]:
                    pos = 1
                elif es[i]:
                    pos = -1
            elif pos == 1 and xl[i]:
                pos = 0
            elif pos == -1 and xs[i]:
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"kc_mid": kc["mid"], "kc_upper": kc["upper"], "kc_lower": kc["lower"], "adx": adx})
        return StrategyResult(signal=signal, diagnostics=diag)
