"""Yuksek-kazanma-oranli scalp - kucuk sabit kar hedefi + genis stop.

MEKANIK: yuksek kazanma orani, ATR'a gore KUCUK bir kar hedefi (tp_atr_mult)
ile GENIS bir zarar-durdur (sl_atr_mult) birlestirerek insa edilir. Kucuk
hedef sik sik vurulur (yuksek kazanma orani); genis stop nadiren vurulur
ama vurulunca kayip, kazancin kat kat ustunde olabilir. Bu YUZDEN kazanma
orani tek basina yeterli degildir - profit factor (toplam kazanc/toplam
kayip) ve ortalama islem % ile BIRLIKTE okunmalidir; aksi halde "sik kazan,
nadiren batir" tuzagina dusulur.

Giris SADECE uzun vadeli trend yonunde (EMA filtresi) - trend tersine
donerse guvenlik agi olarak pozisyon duz kapatilir, TP/SL beklenmez.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class ScalpMeanReversion(Strategy):
    name = "scalp_mean_reversion"

    def __init__(self, ema_len: int = 200, rsi_len: int = 2, oversold: float = 10.0,
                 overbought: float = 90.0, atr_len: int = 14,
                 tp_atr_mult: float = 0.8, sl_atr_mult: float = 2.5, use_safety_exit: bool = True,
                 adx_max: float = 100.0):
        super().__init__(ema_len=ema_len, rsi_len=rsi_len, oversold=oversold, overbought=overbought,
                          atr_len=atr_len, tp_atr_mult=tp_atr_mult, sl_atr_mult=sl_atr_mult,
                          use_safety_exit=use_safety_exit, adx_max=adx_max)
        self.ema_len, self.rsi_len = ema_len, rsi_len
        self.oversold, self.overbought = oversold, overbought
        self.atr_len, self.tp_atr_mult, self.sl_atr_mult = atr_len, tp_atr_mult, sl_atr_mult
        # False ise trend-tersine-donme guvenlik agi KAPALI - pozisyon
        # SADECE TP ya da SL'ye carpinca kapanir. Kazanma oranini
        # yukseltebilir (erken, kucuk kayipli cikislar olmaz) AMA tek bir
        # islemde cok daha buyuk kayip riski dogurur (SL genis olabilir).
        self.use_safety_exit = use_safety_exit
        # ONEMLI BULGU: mean-reversion sadece YATAY piyasada (dusuk ADX)
        # mantiklidir - guclu trend sirasinda "dip alimi" trendin devamina
        # yakalanip stop'a gider. adx_max=100 (varsayilan) filtre KAPALI
        # demektir (geriye uyumluluk); dusurmek (ornegin 15-20) mean-reversion
        # kurgusunu SADECE gercekten yatay barlarda tetikler.
        self.adx_max = adx_max

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ema_trend = ta.ema(df["close"], self.ema_len)
        rsi = ta.rsi(df["close"], self.rsi_len)
        atr = ta.atr(df, self.atr_len)

        adx = ta.adx(df, 14)["adx"]
        ranging = adx <= self.adx_max

        uptrend = df["close"] > ema_trend
        downtrend = df["close"] < ema_trend
        long_entry = uptrend & (rsi < self.oversold) & ranging
        short_entry = downtrend & (rsi > self.overbought) & ranging
        long_safety_exit = ~uptrend
        short_safety_exit = ~downtrend

        close_, high_, low_, atr_ = (df["close"].to_numpy(), df["high"].to_numpy(),
                                      df["low"].to_numpy(), atr.to_numpy())
        le, se = long_entry.to_numpy(), short_entry.to_numpy()
        lsx, ssx = long_safety_exit.to_numpy(), short_safety_exit.to_numpy()

        n = len(df)
        pos = 0
        active_sl = active_tp = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)

        for i in range(n):
            # ONEMLI: pozisyon acikken, bu barin kendi TP/SL'sine carpip
            # carpmayacagini BURADA da simule ediyoruz (core/backtest.py'nin
            # yapacagi gibi) - aksi halde sinyal "pozisyondayim" sanip hicbir
            # zaman sifira donmez, bracket kapandiktan SONRA yeni bir giris
            # taze SL/TP olmadan sonsuza kadar acik kalir (ciddi bir hataydi).
            if pos != 0:
                sl_touched = active_sl is not None and (
                    (pos > 0 and low_[i] <= active_sl) or (pos < 0 and high_[i] >= active_sl))
                tp_touched = active_tp is not None and (
                    (pos > 0 and high_[i] >= active_tp) or (pos < 0 and low_[i] <= active_tp))
                if sl_touched or tp_touched:
                    pos = 0
                    active_sl = active_tp = None
                elif self.use_safety_exit and ((pos == 1 and lsx[i]) or (pos == -1 and ssx[i])):
                    pos = 0
                    active_sl = active_tp = None

            if pos == 0:
                if not np.isnan(atr_[i]) and atr_[i] > 0:
                    if le[i]:
                        pos = 1
                        active_sl = close_[i] - self.sl_atr_mult * atr_[i]
                        active_tp = close_[i] + self.tp_atr_mult * atr_[i]
                        sl_arr[i], tp_arr[i] = active_sl, active_tp
                    elif se[i]:
                        pos = -1
                        active_sl = close_[i] + self.sl_atr_mult * atr_[i]
                        active_tp = close_[i] - self.tp_atr_mult * atr_[i]
                        sl_arr[i], tp_arr[i] = active_sl, active_tp
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        # ONEMLI: SL/TP seviyeleri SADECE giris kararinin verildigi barda
        # dolu, digerlerinde NaN (ileri-doldurma YOK) - core/backtest.py bu
        # degeri sadece pozisyon acilirken BIR KEZ okuyup pozisyon boyunca
        # sabit tutuyor (gercek bir bracket emri gibi).
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        diag = pd.DataFrame({"ema_trend": ema_trend, "rsi": rsi, "atr": atr, "adx": adx})
        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss, take_profit=take_profit)
