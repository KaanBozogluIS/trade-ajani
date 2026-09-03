"""Ichimoku bulutu - Japon kaynakli, cok bilesenli trend sistemi.

Kural: fiyat bulutun USTUNDEYSE sadece long, ALTINDAYSE sadece short bakilir
(bulut ana trend filtresi); Tenkan/Kijun kesisimi giris tetigidir. Fiyat
bulutun icine girerse (kararsizlik bolgesi) pozisyon kapatilir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class IchimokuCloud(Strategy):
    name = "ichimoku"

    def __init__(self, tenkan_len: int = 9, kijun_len: int = 26, senkou_b_len: int = 52,
                 displacement: int = 26):
        super().__init__(tenkan_len=tenkan_len, kijun_len=kijun_len,
                          senkou_b_len=senkou_b_len, displacement=displacement)
        self.tenkan_len, self.kijun_len = tenkan_len, kijun_len
        self.senkou_b_len, self.displacement = senkou_b_len, displacement

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ich = ta.ichimoku(df, self.tenkan_len, self.kijun_len, self.senkou_b_len, self.displacement)
        kumo_top = ich[["senkou_a", "senkou_b"]].max(axis=1)
        kumo_bottom = ich[["senkou_a", "senkou_b"]].min(axis=1)

        above_cloud = df["close"] > kumo_top
        below_cloud = df["close"] < kumo_bottom
        in_cloud = ~above_cloud & ~below_cloud

        bull_cross = ta.crossover(ich["tenkan"], ich["kijun"])
        bear_cross = ta.crossunder(ich["tenkan"], ich["kijun"])

        long_entry = above_cloud & bull_cross
        short_entry = below_cloud & bear_cross
        exit_flat = in_cloud

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        le, se, ex = long_entry.to_numpy(), short_entry.to_numpy(), exit_flat.to_numpy()
        bc, brc = bear_cross.to_numpy(), bull_cross.to_numpy()
        for i in range(len(df)):
            if pos == 0:
                if le[i]:
                    pos = 1
                elif se[i]:
                    pos = -1
            elif pos == 1 and (ex[i] or bc[i]):
                pos = 0
            elif pos == -1 and (ex[i] or brc[i]):
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({"tenkan": ich["tenkan"], "kijun": ich["kijun"],
                              "kumo_top": kumo_top, "kumo_bottom": kumo_bottom})
        return StrategyResult(signal=signal, diagnostics=diag)
