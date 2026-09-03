"""Hacim Onayli Trend - bize ozgu, ampirik olarak turetilmis strateji.

Kaynak: research/factor_lab.py ile evrendeki 40 coin / 1.2M+ bar uzerinde
yapilan faktor arastirmasi (2026-09). Havuzlanan veride en guclu VE MONOTON
iki iliski bulundu:

  * ADX yuksekken (guclu trend) 24-bar ileri getiri ortalamasi ~0.02%'den
    ~0.37%'ye cikiyor - yatay piyasada (dusuk ADX) pratikte edge yok.
  * Hacim, 20-bar ortalamasinin (vol_mult) katina siciradiginda ileri
    getiri ortalamasi ~0.01%'den ~0.27%'ye cikiyor - hacim teyidi gercek.

Diger 11 stratejimizin HICBIRI hacmi sinyal olarak kullanmiyordu - bu, bu
stratejinin ayirt edici, bize ozgu tarafi. Kural: sadece trend GERCEKTEN
guclu VE o anda hacim sicramasiyla teyit edilmisse pozisyon ac; ikisinden
biri kaybolunca kapat.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class VolumeConfirmedTrend(Strategy):
    name = "volume_confirmed_trend"

    def __init__(self, ema_len: int = 50, adx_len: int = 14, adx_min: float = 25.0,
                 vol_len: int = 20, vol_mult: float = 1.5):
        super().__init__(ema_len=ema_len, adx_len=adx_len, adx_min=adx_min,
                          vol_len=vol_len, vol_mult=vol_mult)
        self.ema_len, self.adx_len, self.adx_min = ema_len, adx_len, adx_min
        self.vol_len, self.vol_mult = vol_len, vol_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ema_trend = ta.ema(df["close"], self.ema_len)
        adx = ta.adx(df, self.adx_len)["adx"]
        vol_ratio = df["volume"] / df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean()

        trending = adx >= self.adx_min
        vol_spike = vol_ratio >= self.vol_mult
        uptrend = df["close"] > ema_trend
        downtrend = df["close"] < ema_trend

        long_entry = trending & vol_spike & uptrend
        short_entry = trending & vol_spike & downtrend
        # Trend GERCEKTEN zayiflarsa (ADX dustu) ya da yon degistiyse cik -
        # hacim sicramasinin gecmis olmasi onemli degil, giris tetigiydi.
        exit_long = (adx < self.adx_min) | downtrend
        exit_short = (adx < self.adx_min) | uptrend

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        le, se = long_entry.to_numpy(), short_entry.to_numpy()
        xl, xs = exit_long.to_numpy(), exit_short.to_numpy()
        for i in range(len(df)):
            if pos == 0:
                if le[i]:
                    pos = 1
                elif se[i]:
                    pos = -1
            elif pos == 1 and xl[i]:
                pos = 0
            elif pos == -1 and xs[i]:
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"ema_trend": ema_trend, "adx": adx, "vol_ratio": vol_ratio})
        return StrategyResult(signal=signal, diagnostics=diag)
