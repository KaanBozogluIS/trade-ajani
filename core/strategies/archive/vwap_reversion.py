"""VWAP ortalamaya donus - kurumsal gunluk trader tekniği.

Fikir (kurumsal masalarda yaygin): gunluk VWAP, o gunun "adil deger"
referansidir - buyuk oyuncular VWAP'in altinda almaya, ustunde satmaya
calisir. Fiyat VWAP'tan 2+ standart sapma uzaklastiginda ve piyasa GUCLU
TREND'de DEGILSE (ADX filtresi), VWAP'a geri donme egilimi yuksektir.
Arastirmalar ~%63 geri donus orani bildiriyor (2-std asimlarindan).

Diger mean-reversion stratejilerimizden (Bollinger, RSI2) farki: referans
noktasi bir hareketli ortalama degil, HACIM AGIRLIKLI gercek islem
fiyatidir - buyuk hacimli barlar VWAP'i daha çok etkiler, bu da onu
"gercek" bir denge fiyatina Bollinger'in SMA'sindan daha yakin yapar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class VwapReversion(Strategy):
    name = "vwap_reversion"

    def __init__(self, std_mult: float = 2.0, exit_std_mult: float = 0.3, adx_max: float = 25.0):
        super().__init__(std_mult=std_mult, exit_std_mult=exit_std_mult, adx_max=adx_max)
        self.std_mult, self.exit_std_mult, self.adx_max = std_mult, exit_std_mult, adx_max

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        vw = ta.vwap_session(df)
        adx = ta.adx(df, 14)["adx"]
        ranging = adx <= self.adx_max

        upper = vw["vwap"] + self.std_mult * vw["std"]
        lower = vw["vwap"] - self.std_mult * vw["std"]
        exit_upper = vw["vwap"] + self.exit_std_mult * vw["std"]
        exit_lower = vw["vwap"] - self.exit_std_mult * vw["std"]

        long_entry = (df["close"] < lower) & ranging
        short_entry = (df["close"] > upper) & ranging
        long_exit = df["close"] >= exit_lower
        short_exit = df["close"] <= exit_upper

        pos = 0
        n = len(df)
        sig_values = np.zeros(n, dtype="int64")
        le, se = long_entry.to_numpy(), short_entry.to_numpy()
        lx, sx = long_exit.to_numpy(), short_exit.to_numpy()
        for i in range(n):
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

        diag = pd.DataFrame({"vwap": vw["vwap"], "upper": upper, "lower": lower, "adx": adx})
        return StrategyResult(signal=signal, diagnostics=diag)
