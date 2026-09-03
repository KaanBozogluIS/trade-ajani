"""Donchian kanal kirilimi - swing vadeli trend/kirilim stratejisi (Turtle benzeri)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Signal, Strategy, StrategyResult


class DonchianBreakout(Strategy):
    name = "donchian_breakout"

    def __init__(self, entry_len: int = 20, exit_len: int = 10, adx_min: float = 20.0):
        super().__init__(entry_len=entry_len, exit_len=exit_len, adx_min=adx_min)
        self.entry_len, self.exit_len, self.adx_min = entry_len, exit_len, adx_min

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        entry_ch = ta.donchian(df, self.entry_len)
        exit_ch = ta.donchian(df, self.exit_len)
        adx = ta.adx(df, 14)["adx"]

        trending = adx >= self.adx_min
        enter_long = (df["close"] > entry_ch["upper"]) & trending
        enter_short = (df["close"] < entry_ch["lower"]) & trending
        exit_long = df["close"] < exit_ch["lower"]
        exit_short = df["close"] > exit_ch["upper"]

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        el, es, xl, xs = enter_long.to_numpy(), enter_short.to_numpy(), exit_long.to_numpy(), exit_short.to_numpy()
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

        diag = pd.DataFrame({
            "entry_upper": entry_ch["upper"], "entry_lower": entry_ch["lower"],
            "exit_upper": exit_ch["upper"], "exit_lower": exit_ch["lower"], "adx": adx,
        })
        return StrategyResult(signal=signal, diagnostics=diag)
