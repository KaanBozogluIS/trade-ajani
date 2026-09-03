"""Parabolic SAR (Wilder, 1978) - hep pozisyonda olan, hizlanan iz suren stop.

Supertrend'den farki: bant genisligi oynaklikla degil, ZAMANLA hizlanir
(acceleration factor her yeni zirve/dip ile artar) - bu yuzden uzun suren
trendlerde SAR gitgide fiyata yaklasir ve kucuk bir geri cekilmede bile
tetiklenebilir. Klasik, guvenlik-once bir trend-takip yaklasimidir.
"""

from __future__ import annotations

import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class ParabolicSar(Strategy):
    name = "parabolic_sar"

    def __init__(self, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2):
        super().__init__(af_start=af_start, af_step=af_step, af_max=af_max)
        self.af_start, self.af_step, self.af_max = af_start, af_step, af_max

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ps = ta.parabolic_sar(df, self.af_start, self.af_step, self.af_max)
        signal = ps["trend"].astype("int64")
        return StrategyResult(signal=signal, diagnostics=ps)
