"""Fibonacci Geri Cekilme Stratejisi - klasik Fibonacci retracement
seviyelerini (kalabaligin GERCEKTEN izledigi, kendini gerceklestiren
psikolojik seviyeler) hacim+momentum onay katmanlarimizla birlestirir.

FIKIR: Fiyat belirgin bir yon hareketi (swing) yaptiktan sonra, cogu zaman
o hareketin bir kismini "geri verir" (duzeltme). Fibonacci geri cekilme
seviyeleri (%38.2-%61.8 - "altin bolge") tarihsel olarak COK IZLENEN
seviyeler - bircok trader/bot ayni seviyeye bakip orada emir bekletir, bu
da kendi kendini gerceklestiren bir manyetizma yaratir (bkz. modul
docstring'i disindaki sohbet notlari). TEK BASINA bu yeterli degil - bu
yuzden altin bolgeye deginme + hacim teyidi + RSI/momentum toparlanmasi
BIRLIKTE sart kosuluyor (reversal_pullback.py'de dogrulanan "bekleyen
kurulum" mimarisi).

Swing tanimi: son `swing_lookback` bar icindeki EN YUKSEK ve EN DUSUK
fiyat (nedensel - shift(1) ile kendi barini kanala katmiyor, klasik
Donchian ileriye-bakma hatasindan kacinma). Bu swing'in YONU (yukselis mi
dusus mu daha yeni) ana trend kabul edilir; fiyat bu swing'in
%38.2-%61.8 bandina GERI CEKILIRSE ve toparlanma teyidi gelirse, swing
YONUNDE (trend devami) giris yapilir - klasik "trend'de Fibonacci ile
pullback alimi" mantigi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class FibonacciPullback(Strategy):
    name = "fibonacci_stratejisi"

    def __init__(self, swing_lookback: int = 100, fib_low: float = 0.382, fib_high: float = 0.618,
                 max_confirm_bars: int = 20, invalidate_fib: float = 1.0,
                 vol_len: int = 20, vol_mult: float = 1.1, recovery_body_ratio: float = 0.5,
                 rsi_len: int = 14, rsi_min: float = 35.0, rsi_max: float = 65.0,
                 atr_len: int = 14, sl_atr_buffer: float = 0.3, tp_r_mult: float = 2.0):
        super().__init__(swing_lookback=swing_lookback, fib_low=fib_low, fib_high=fib_high,
                          max_confirm_bars=max_confirm_bars, invalidate_fib=invalidate_fib,
                          vol_len=vol_len, vol_mult=vol_mult, recovery_body_ratio=recovery_body_ratio,
                          rsi_len=rsi_len, rsi_min=rsi_min, rsi_max=rsi_max,
                          atr_len=atr_len, sl_atr_buffer=sl_atr_buffer, tp_r_mult=tp_r_mult)
        self.swing_lookback, self.fib_low, self.fib_high = swing_lookback, fib_low, fib_high
        self.max_confirm_bars, self.invalidate_fib = max_confirm_bars, invalidate_fib
        self.vol_len, self.vol_mult, self.recovery_body_ratio = vol_len, vol_mult, recovery_body_ratio
        self.rsi_len, self.rsi_min, self.rsi_max = rsi_len, rsi_min, rsi_max
        self.atr_len, self.sl_atr_buffer, self.tp_r_mult = atr_len, sl_atr_buffer, tp_r_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        # Nedensel swing kanali: t barinda SADECE t-1'e kadarki veriyle
        # hesaplanan en yuksek/en dusuk (core/indicators.py'deki donchian()
        # ile ayni ileriye-bakma onlemi).
        swing_high = df["high"].shift(1).rolling(self.swing_lookback, min_periods=self.swing_lookback).max()
        swing_low = df["low"].shift(1).rolling(self.swing_lookback, min_periods=self.swing_lookback).min()
        # Hangisi DAHA YENI (swing'in yonu): en yuksegin mi en dusugun mu
        # indeksi daha yakin - argmax/argmin pencere ici pozisyon.
        high_pos = df["high"].shift(1).rolling(self.swing_lookback, min_periods=self.swing_lookback).apply(
            lambda w: float(np.argmax(w)), raw=True)
        low_pos = df["low"].shift(1).rolling(self.swing_lookback, min_periods=self.swing_lookback).apply(
            lambda w: float(np.argmin(w)), raw=True)
        uptrend_swing = high_pos > low_pos  # en yuksek daha SONRA olustu -> son hareket YUKARI

        atr = ta.atr(df, self.atr_len)
        rsi = ta.rsi(df["close"], self.rsi_len)
        vol_avg = df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean()

        sh, sl_ = swing_high.to_numpy(), swing_low.to_numpy()
        up = uptrend_swing.to_numpy()
        atr_arr, rsi_arr = atr.to_numpy(), rsi.to_numpy()
        vol_avg_arr = vol_avg.to_numpy()
        open_, close_ = df["open"].to_numpy(), df["close"].to_numpy()
        high_, low_, volume_ = df["high"].to_numpy(), df["low"].to_numpy(), df["volume"].to_numpy()
        n = len(df)
        min_warmup = max(self.swing_lookback, self.vol_len, self.rsi_len, self.atr_len) + 2

        pos = 0
        active_sl = active_tp = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        pending = None  # {'dir':1/-1, 'since':int, 'swing_top':float, 'swing_bot':float}

        for i in range(n):
            if pos != 0:
                sl_t = (pos > 0 and low_[i] <= active_sl) or (pos < 0 and high_[i] >= active_sl)
                tp_t = (pos > 0 and high_[i] >= active_tp) or (pos < 0 and low_[i] <= active_tp)
                if sl_t or tp_t:
                    pos = 0
                    active_sl = active_tp = None

            if pos == 0 and i >= min_warmup and not np.isnan(atr_arr[i]) and atr_arr[i] > 0 \
                    and not np.isnan(sh[i]) and not np.isnan(sl_[i]) and sh[i] > sl_[i]:
                swing_range = sh[i] - sl_[i]
                # Fib seviyeleri: %0 = hareketin BASLADIGI uc, %100 = VARDIGI uc.
                if up[i]:
                    # Yukselen swing (dip->tepe): geri cekilme TEPEDEN asagi olculuyor.
                    fib_lo_price = sh[i] - self.fib_high * swing_range
                    fib_hi_price = sh[i] - self.fib_low * swing_range
                else:
                    fib_lo_price = sl_[i] + self.fib_low * swing_range
                    fib_hi_price = sl_[i] + self.fib_high * swing_range

                if pending is None:
                    in_zone = fib_lo_price <= close_[i] <= fib_hi_price
                    if in_zone:
                        pending = {"dir": 1 if up[i] else -1, "since": i,
                                   "swing_top": sh[i], "swing_bot": sl_[i]}
                else:
                    d = pending["dir"]
                    top, bot = pending["swing_top"], pending["swing_bot"]
                    rng = top - bot
                    vol_confirm = volume_[i] >= self.vol_mult * vol_avg_arr[i] if not np.isnan(vol_avg_arr[i]) else False
                    bar_range = max(high_[i] - low_[i], 1e-12)
                    if d == 1:
                        invalidated = close_[i] < bot - self.invalidate_fib * (top - bot) * 0.1
                        bullish_reject = (close_[i] - low_[i]) / bar_range >= self.recovery_body_ratio \
                            and close_[i] > open_[i]
                        rsi_ok = not np.isnan(rsi_arr[i]) and self.rsi_min <= rsi_arr[i] <= self.rsi_max
                        if invalidated:
                            pending = None
                        elif bullish_reject and vol_confirm and rsi_ok:
                            pos = 1
                            active_sl = bot - self.sl_atr_buffer * atr_arr[i]
                            risk = close_[i] - active_sl
                            active_tp = close_[i] + self.tp_r_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_confirm_bars:
                            pending = None
                    else:
                        invalidated = close_[i] > top + self.invalidate_fib * (top - bot) * 0.1
                        bearish_reject = (high_[i] - close_[i]) / bar_range >= self.recovery_body_ratio \
                            and close_[i] < open_[i]
                        rsi_ok = not np.isnan(rsi_arr[i]) and self.rsi_min <= rsi_arr[i] <= self.rsi_max
                        if invalidated:
                            pending = None
                        elif bearish_reject and vol_confirm and rsi_ok:
                            pos = -1
                            active_sl = top + self.sl_atr_buffer * atr_arr[i]
                            risk = active_sl - close_[i]
                            active_tp = close_[i] - self.tp_r_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_confirm_bars:
                            pending = None

            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        return StrategyResult(signal=signal, stop_loss=stop_loss, take_profit=take_profit)
