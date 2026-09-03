"""Coklu-faktor skor modeli - "matematiksel algoritma" ile yon tahmini.

research/factor_lab.py'deki ampirik faktor arastirmasinda ISPATLANMIS uc
ozelligi (trend gucu=ADX, hacim teyidi=vol_ratio, "genislemis" momentum=
dip'ten uzaklik) AGIRLIKLI bir bilesik skora donusturur. Skor -1 (guclu
short) ile +1 (guclu long) arasinda; esik degerlerin ustune/altina
gectiginde pozisyon acilir.

Kara-kutu bir ML modeli DEGIL - her bilesenin agirligi acikca yazili ve
degistirilebilir, boylece "neden bu sinyal geldi" sorusuna her zaman cevap
verilebilir. Agirliklar factor_lab.py'deki |IC| buyuklugune gore secildi:
ADX ve hacim en guclu/monotonik oldugu icin en yuksek agirligi tasiyor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class MultiFactorScore(Strategy):
    name = "multi_factor_score"

    def __init__(self, ema_len: int = 50, adx_len: int = 14, vol_len: int = 20, rank_window: int = 200,
                 w_adx: float = 0.45, w_vol: float = 0.35, w_ext: float = 0.20,
                 long_threshold: float = 0.5, short_threshold: float = -0.5, exit_threshold: float = 0.15):
        super().__init__(ema_len=ema_len, adx_len=adx_len, vol_len=vol_len, rank_window=rank_window,
                          w_adx=w_adx, w_vol=w_vol, w_ext=w_ext, long_threshold=long_threshold,
                          short_threshold=short_threshold, exit_threshold=exit_threshold)
        self.ema_len, self.adx_len, self.vol_len, self.rank_window = ema_len, adx_len, vol_len, rank_window
        self.w_adx, self.w_vol, self.w_ext = w_adx, w_vol, w_ext
        self.long_threshold, self.short_threshold, self.exit_threshold = long_threshold, short_threshold, exit_threshold

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        rw = self.rank_window
        min_p = max(rw // 2, 20)

        ema_trend = ta.ema(df["close"], self.ema_len)
        adx = ta.adx(df, self.adx_len)["adx"]
        vol_ratio = df["volume"] / df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean()
        dist_low20 = (df["close"] - df["low"].rolling(20, min_periods=20).min()) / df["close"] * 100.0
        dist_high20 = (df["high"].rolling(20, min_periods=20).max() - df["close"]) / df["close"] * 100.0

        adx_rank = adx.rolling(rw, min_periods=min_p).rank(pct=True)
        vol_rank = vol_ratio.rolling(rw, min_periods=min_p).rank(pct=True)
        ext_up_rank = dist_low20.rolling(rw, min_periods=min_p).rank(pct=True)
        ext_down_rank = dist_high20.rolling(rw, min_periods=min_p).rank(pct=True)

        trend_dir = np.sign(df["close"] - ema_trend)
        extension_rank = pd.Series(np.where(trend_dir > 0, ext_up_rank, ext_down_rank), index=df.index)

        score = trend_dir * (self.w_adx * adx_rank + self.w_vol * vol_rank + self.w_ext * extension_rank)
        s = score.to_numpy()

        n = len(df)
        sig_values = np.zeros(n, dtype="int64")
        pos = 0
        for i in range(n):
            if np.isnan(s[i]):
                sig_values[i] = pos
                continue
            if pos == 0:
                if s[i] >= self.long_threshold:
                    pos = 1
                elif s[i] <= self.short_threshold:
                    pos = -1
            elif pos == 1 and s[i] < self.exit_threshold:
                pos = 0
            elif pos == -1 and s[i] > -self.exit_threshold:
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"score": score, "adx_rank": adx_rank, "vol_rank": vol_rank,
                              "extension_rank": extension_rank})
        return StrategyResult(signal=signal, diagnostics=diag)
