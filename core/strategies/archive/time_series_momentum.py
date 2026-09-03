"""Zaman-serisi (mutlak) momentum - Moskowitz, Ooi & Pedersen (2012) "Time
Series Momentum" makalesinin kurallarina dayanir: bir varligin son N
donemlik getirisinin isareti, bir sonraki donemin yonunu tahmin eder.

Diger stratejilerden temel farki: gostergeye degil DOGRUDAN GETIRIYE bakar,
ve akademik calismadaki gibi periyodik olarak "yeniden dengelenir"
(rebalance_every) - her mumda degil, sadece N mumda bir pozisyon yonu
kontrol edilir. Bu, asiri sik islem yapmayi (ve komisyon asinmasini) onler.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy import Strategy, StrategyResult


class TimeSeriesMomentum(Strategy):
    name = "time_series_momentum"

    def __init__(self, lookback: int = 90, rebalance_every: int = 20, threshold_pct: float = 0.0):
        super().__init__(lookback=lookback, rebalance_every=rebalance_every, threshold_pct=threshold_pct)
        self.lookback, self.rebalance_every, self.threshold_pct = lookback, rebalance_every, threshold_pct

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ret = df["close"].pct_change(self.lookback)
        ret_arr = ret.to_numpy()

        n = len(df)
        sig_values = np.zeros(n, dtype="int64")
        pos = 0
        threshold = self.threshold_pct / 100.0
        for i in range(n):
            if i % self.rebalance_every == 0:
                r = ret_arr[i]
                if np.isnan(r):
                    pos = 0
                elif r > threshold:
                    pos = 1
                elif r < -threshold:
                    pos = -1
                else:
                    pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"lookback_getiri_%": ret * 100.0})
        return StrategyResult(signal=signal, diagnostics=diag)
