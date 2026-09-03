"""Likidite avi (stop-hunt) tersine donusu - ICT/SMC'nin "liquidity sweep"
kavrami.

Fikir: birden fazla swing tepe/dip birbirine yakinsa (esit tepe/dip), o
seviyenin hemen otesinde bircok tuccarin stop-loss'u/emri kumelenmis
demektir - "likidite havuzu". Fiyat bu seviyeyi kisaca DELIP GECIP (o
likiditeyi "avlayip") geri iceri KAPANIRSA, bu genelde o yondeki hareketin
tukendigini ve tersine donusun basladigini gosteren guclu bir reddediş
mumudur.

Not: gercek likidasyon verisi yerine "esit tepe/dip" kullaniyoruz - bkz.
core/smc.py dosyasinin basindaki durustluk notu.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import smc
from core.strategy import Strategy, StrategyResult


class LiquiditySweepReversal(Strategy):
    name = "liquidity_sweep_reversal"

    def __init__(self, swing_left: int = 5, swing_right: int = 5,
                 tolerance_pct: float = 0.15, lookback: int = 100, max_hold: int = 48):
        super().__init__(swing_left=swing_left, swing_right=swing_right,
                          tolerance_pct=tolerance_pct, lookback=lookback, max_hold=max_hold)
        self.swing_left, self.swing_right = swing_left, swing_right
        self.tolerance_pct, self.lookback, self.max_hold = tolerance_pct, lookback, max_hold

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        is_high, is_low = smc.swing_points(df, self.swing_left, self.swing_right)
        conf_high_flag = is_high.shift(self.swing_right).fillna(False).to_numpy()
        conf_low_flag = is_low.shift(self.swing_right).fillna(False).to_numpy()
        swing_high_price = df["high"].shift(self.swing_right).to_numpy()
        swing_low_price = df["low"].shift(self.swing_right).to_numpy()
        high_, low_, close_ = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()

        n = len(df)
        recent_highs: list[tuple[int, float]] = []
        recent_lows: list[tuple[int, float]] = []
        pos, entry_i = 0, -1
        sig_values = np.zeros(n, dtype="int64")
        tol = self.tolerance_pct / 100.0

        for i in range(n):
            if conf_high_flag[i]:
                recent_highs.append((i, swing_high_price[i]))
                recent_highs = [(j, p) for j, p in recent_highs if i - j <= self.lookback]
            if conf_low_flag[i]:
                recent_lows.append((i, swing_low_price[i]))
                recent_lows = [(j, p) for j, p in recent_lows if i - j <= self.lookback]

            equal_high_level = None
            if len(recent_highs) >= 2:
                top = max(p for _, p in recent_highs)
                cluster = [p for _, p in recent_highs if abs(p - top) / top <= tol]
                if len(cluster) >= 2:
                    equal_high_level = max(cluster)

            equal_low_level = None
            if len(recent_lows) >= 2:
                bottom = min(p for _, p in recent_lows)
                cluster = [p for _, p in recent_lows if abs(p - bottom) / bottom <= tol]
                if len(cluster) >= 2:
                    equal_low_level = min(cluster)

            bearish_sweep = equal_high_level is not None and high_[i] > equal_high_level and close_[i] < equal_high_level
            bullish_sweep = equal_low_level is not None and low_[i] < equal_low_level and close_[i] > equal_low_level

            if pos == 0:
                if bullish_sweep:
                    pos, entry_i = 1, i
                elif bearish_sweep:
                    pos, entry_i = -1, i
            elif pos == 1 and (bearish_sweep or (i - entry_i) >= self.max_hold):
                pos = 0
            elif pos == -1 and (bullish_sweep or (i - entry_i) >= self.max_hold):
                pos = 0
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        return StrategyResult(signal=signal)
