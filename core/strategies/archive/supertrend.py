"""Supertrend - ATR bantli, her zaman piyasada olan (flat yok) trend takibi.

EMA kesisiminden farki: bant genisligi oynaklikla (ATR) orantili buyudugu
icin, sakin piyasada dar/hassas, oynak piyasada genis/gec tepki veren
kendiliginden uyarlanan bir esik kullanir.
"""

from __future__ import annotations

import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class Supertrend(Strategy):
    name = "supertrend"

    def __init__(self, length: int = 10, mult: float = 3.0):
        super().__init__(length=length, mult=mult)
        self.length, self.mult = length, mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        st = ta.supertrend(df, self.length, self.mult)
        signal = st["trend"].astype("int64")
        return StrategyResult(signal=signal, diagnostics=st)
