"""Acilis Araligi Kirilimi (ORB) - klasik gunluk trader stratejisi.

Borsalarda "gunun ilk N dakikasinin araligi" kullanilir; kripto 7/24 islem
gordugu icin gercek bir acilis yok - literatur "senkron UTC gunu"
kullanmayi onerir (gunun ilk `range_hours` saati = acilis araligi). O
aralik disina, HACIM TEYIDIYLE (sahte kirilimlari elemek icin) kapanan
ilk mum tetigi olusturur.

Arastirma notu: iyi bir ORB kazanma orani ~%40-60 kabul edilir - yuksek
kazanma oranina degil, trend gunlerinde riskin kat kati kazanmaya
dayanir (tp_r_mult) - bu yuzden ATR-tabanli stop + R-kati hedef kullanir,
StrategyResult.stop_loss/take_profit ile kaldirac boyutlandirmaya uygundur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class OrbBreakout(Strategy):
    name = "orb_breakout"

    def __init__(self, range_hours: float = 4.0, vol_mult: float = 1.5,
                 atr_len: int = 14, sl_atr_mult: float = 1.0, tp_r_mult: float = 2.0):
        super().__init__(range_hours=range_hours, vol_mult=vol_mult, atr_len=atr_len,
                          sl_atr_mult=sl_atr_mult, tp_r_mult=tp_r_mult)
        self.range_hours, self.vol_mult = range_hours, vol_mult
        self.atr_len, self.sl_atr_mult, self.tp_r_mult = atr_len, sl_atr_mult, tp_r_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        day = df.index.floor("1D")
        hour_of_day = df.index.hour + df.index.minute / 60.0
        in_window = hour_of_day < self.range_hours

        window_high = df["high"].where(in_window)
        window_low = df["low"].where(in_window)
        orb_high = window_high.groupby(day).transform("max")
        orb_low = window_low.groupby(day).transform("min")
        vol_ratio = df["volume"] / df["volume"].rolling(20, min_periods=20).mean()
        atr = ta.atr(df, self.atr_len)

        breakout_up = (df["close"] > orb_high) & (~in_window) & (vol_ratio >= self.vol_mult)
        breakout_down = (df["close"] < orb_low) & (~in_window) & (vol_ratio >= self.vol_mult)

        close_, atr_ = df["close"].to_numpy(), atr.to_numpy()
        bu, bd = breakout_up.to_numpy(), breakout_down.to_numpy()
        oh, ol = orb_high.to_numpy(), orb_low.to_numpy()

        n = len(df)
        pos = 0
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        active_sl = active_tp = None

        for i in range(n):
            if pos != 0:
                sl_t = active_sl is not None and (
                    (pos > 0 and df["low"].iat[i] <= active_sl) or (pos < 0 and df["high"].iat[i] >= active_sl))
                tp_t = active_tp is not None and (
                    (pos > 0 and df["high"].iat[i] >= active_tp) or (pos < 0 and df["low"].iat[i] <= active_tp))
                if sl_t or tp_t:
                    pos = 0
                    active_sl = active_tp = None

            if pos == 0 and not np.isnan(atr_[i]) and atr_[i] > 0:
                if bu[i]:
                    pos = 1
                    # Stop: aralik altiyla ATR-tabanli mesafeden HANGISI ENTRY'YE
                    # DAHA YAKINSA (daha siki, tanimli risk) - ikisinin en
                    # gevsegi degil.
                    active_sl = max(ol[i], close_[i] - self.sl_atr_mult * atr_[i])
                    risk = close_[i] - active_sl
                    active_tp = close_[i] + self.tp_r_mult * risk
                    sl_arr[i], tp_arr[i] = active_sl, active_tp
                elif bd[i]:
                    pos = -1
                    active_sl = min(oh[i], close_[i] + self.sl_atr_mult * atr_[i])
                    risk = active_sl - close_[i]
                    active_tp = close_[i] - self.tp_r_mult * risk
                    sl_arr[i], tp_arr[i] = active_sl, active_tp
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        diag = pd.DataFrame({"orb_high": orb_high, "orb_low": orb_low, "vol_ratio": vol_ratio})
        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss, take_profit=take_profit)
