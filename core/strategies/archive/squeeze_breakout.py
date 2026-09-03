"""TTM Squeeze - John Carter'in oynaklik sikismasi + momentum kirilim sistemi.

Fikir: Bollinger bandi Keltner kanalinin ICINE girdiginde piyasa "sikisir"
(oynaklik cok dusuktur, enerji birikir). Bollinger tekrar Keltner'in disina
tastiginda "sikisma acilir" - bu, patlamali bir hareketin baslangici olma
egilimindedir. Yon, o anki kisa vadeli momentumla (ROC) belirlenir.

Diger kirilim stratejilerimizden (Donchian, Keltner) farki: kirilim
SEVIYESI degil, OYNAKLIK REJIMI degisimini yakalar - "fiyat X seviyesini
gecti" degil, "piyasa sessizlikten harekete geciyor" sorusuna cevap arar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class SqueezeBreakout(Strategy):
    name = "squeeze_breakout"

    def __init__(self, bb_len: int = 20, bb_mult: float = 2.0, kc_len: int = 20,
                 kc_mult: float = 1.5, mom_len: int = 12):
        super().__init__(bb_len=bb_len, bb_mult=bb_mult, kc_len=kc_len, kc_mult=kc_mult, mom_len=mom_len)
        self.bb_len, self.bb_mult = bb_len, bb_mult
        self.kc_len, self.kc_mult = kc_len, kc_mult
        self.mom_len = mom_len

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        bb = ta.bollinger(df["close"], self.bb_len, self.bb_mult)
        kc = ta.keltner(df, self.kc_len, self.kc_len, self.kc_mult)
        momentum = ta.roc(df["close"], self.mom_len)

        squeeze_on = (bb["upper"] < kc["upper"]) & (bb["lower"] > kc["lower"])
        squeeze_fired = squeeze_on.shift(1).fillna(False) & ~squeeze_on

        long_entry = squeeze_fired & (momentum > 0)
        short_entry = squeeze_fired & (momentum < 0)
        # Cikis: sikisma tekrar basladiginda (hareket tukendi) ya da momentum
        # yon degistirdiginde.
        long_exit = squeeze_on | (momentum < 0)
        short_exit = squeeze_on | (momentum > 0)

        pos = 0
        sig_values = np.zeros(len(df), dtype="int64")
        le, se = long_entry.to_numpy(), short_entry.to_numpy()
        lx, sx = long_exit.to_numpy(), short_exit.to_numpy()
        for i in range(len(df)):
            if pos == 0:
                if le[i]:
                    pos = 1
                elif se[i]:
                    pos = -1
            elif pos == 1 and lx[i]:
                pos = 0
            elif pos == -1 and sx[i]:
                pos = 0
            sig_values[i] = pos
        signal = pd.Series(sig_values, index=df.index, dtype="int64")

        diag = pd.DataFrame({
            "bb_upper": bb["upper"], "bb_lower": bb["lower"],
            "kc_upper": kc["upper"], "kc_lower": kc["lower"],
            "squeeze_on": squeeze_on, "momentum": momentum,
        })
        return StrategyResult(signal=signal, diagnostics=diag)
