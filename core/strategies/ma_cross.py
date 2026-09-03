"""Klasik hizli/yavas EMA kesisimi - trend takibi."""

from __future__ import annotations

import pandas as pd

from core import indicators as ta
from core.strategy import Signal, Strategy, StrategyResult


class EmaCross(Strategy):
    name = "ema_cross"

    def __init__(self, fast: int = 20, slow: int = 50, trend_filter: int = 200,
                 atr_stop_mult: float | None = None):
        super().__init__(fast=fast, slow=slow, trend_filter=trend_filter, atr_stop_mult=atr_stop_mult)
        self.fast, self.slow, self.trend_filter = fast, slow, trend_filter
        # None (varsayilan) = eski davranis, stop yok, hep kaldiracsiz (1.0x)
        # calisir. Bir deger verilirse GENIS bir ATR-tabanli koruma stopu
        # eklenir - amaci erken cikmak DEGIL (o zaman strateji bozulur),
        # sadece core/backtest.py'nin risk-bazli kaldirac boyutlandirmasini
        # (StrategyResult.stop_loss gerektirir) kullanabilmek. Yeterince genis
        # secilirse (ornegin 6-8x ATR) nadiren tetiklenir, kaldirac boyutlandirmasinda
        # kullanilir.
        self.atr_stop_mult = atr_stop_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        fast_ema = ta.ema(df["close"], self.fast)
        slow_ema = ta.ema(df["close"], self.slow)
        trend_ema = ta.ema(df["close"], self.trend_filter)

        long_cond = ta.crossover(fast_ema, slow_ema) & (df["close"] > trend_ema)
        short_cond = ta.crossunder(fast_ema, slow_ema) & (df["close"] < trend_ema)

        signal = pd.Series(Signal.FLAT, index=df.index, dtype="int64")
        signal[long_cond] = Signal.LONG
        signal[short_cond] = Signal.SHORT
        # Kesisimler arasi son sinyali tut (pozisyonda kal) - bir sonraki
        # zit sinyale kadar.
        signal = signal.replace(0, pd.NA).ffill().fillna(Signal.FLAT).astype(int)

        diag = pd.DataFrame({"ema_fast": fast_ema, "ema_slow": slow_ema, "ema_trend": trend_ema})

        stop_loss = None
        if self.atr_stop_mult is not None:
            atr = ta.atr(df, 14)
            entry_flag = (signal != signal.shift(1)) & (signal != Signal.FLAT)
            long_stop = df["close"] - self.atr_stop_mult * atr
            short_stop = df["close"] + self.atr_stop_mult * atr
            sl = long_stop.where(signal == Signal.LONG, short_stop.where(signal == Signal.SHORT))
            stop_loss = sl.where(entry_flag)

        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss)
