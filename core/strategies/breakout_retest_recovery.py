"""Kirilim - Geri Cekilme - Toparlanma (bize ozgu, sifirdan tasarlanmis).

Bu, isimli bir gosterge ya da literatur stratejisinin uygulamasi DEGIL -
klasik fiyat hareketi mantigindan kendi kurallarimizi kurduk:

  1. DESTEK/DIRENC: bir fiyat seviyesi rastgele degildir - fiyat ayni
     bolgeye BIRDEN FAZLA kez gelip tepki verdiyse (min_touches) gercek
     kabul edilir. Tek bir swing noktasi yetmez.
  2. KARARLI KIRILIM: fiyatin bir ucu (fitil/wick) seviyeyi gecmesi
     kirilim SAYILMAZ - KAPANIS, seviyeyi anlamli bir marjla (break_atr_mult)
     gecmelidir. Bu, sahte kirilimlarin (fakeout) buyuk kismini eler.
  3. GERI CEKILME: kirilimdan sonra fiyat, KIRILAN SEVIYEYE geri doner
     (direnc artik destek olur, ya da tam tersi - klasik "polarite
     degisimi"). Bu donus max_retest_bars icinde gerceklesmezse kurulum
     iptal edilir.
  4. TOPARLANMA MUMU: geri cekilme sirasinda, fiyat seviyeye DOKUNUP
     GERI TEPTIGINI gosteren bir mum ariyoruz - dusuk (ya da yuksek)
     seviyenin YAKININA iner AMA KAPANIS seviyenin OTESINDE, kendi
     araliginin GUCLU bir kisminda kalir (reddedis mumu). Giris burada
     olur - kirilimin tepesini kovalamak yerine, ikinci bir onayla,
     genelde daha iyi bir fiyattan.

Cikis: stop, kirilan seviyenin hemen otesinde (kurulumun gecersiz oldugu
nokta); hedef, riskin sabit bir kati (tp_r_mult) - StrategyResult.stop_loss/
take_profit doldurdugu icin core/backtest.py'nin risk-bazli (kaldiracli)
pozisyon boyutlandirmasiyla dogrudan uyumlu.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core import smc
from core.strategy import Strategy, StrategyResult


class BreakoutRetestRecovery(Strategy):
    # "ALTCOIN Stratejisi" - orta/kucuk cap altcoinlerde (SEI, SHIB, FET,
    # BICO, WLD, ZKC, BMT, PENGU, ZEN) IS/OOS dogrulandi. BTC/ETH gibi
    # majorlerde CALISMIYOR (bkz. brr_hunt_sonuclari.csv) - kasitli olarak
    # sadece bu grupta kullanilmali.
    name = "altcoin_stratejisi"

    def __init__(self, swing_left: int = 5, swing_right: int = 5, lookback: int = 150,
                 tolerance_pct: float = 0.6, min_touches: int = 2, atr_len: int = 14,
                 break_atr_mult: float = 0.3, max_retest_bars: int = 30,
                 recovery_body_ratio: float = 0.5, sl_atr_buffer: float = 0.3, tp_r_mult: float = 2.0):
        super().__init__(swing_left=swing_left, swing_right=swing_right, lookback=lookback,
                          tolerance_pct=tolerance_pct, min_touches=min_touches, atr_len=atr_len,
                          break_atr_mult=break_atr_mult, max_retest_bars=max_retest_bars,
                          recovery_body_ratio=recovery_body_ratio, sl_atr_buffer=sl_atr_buffer,
                          tp_r_mult=tp_r_mult)
        self.swing_left, self.swing_right, self.lookback = swing_left, swing_right, lookback
        self.tolerance_pct, self.min_touches = tolerance_pct, min_touches
        self.atr_len, self.break_atr_mult, self.max_retest_bars = atr_len, break_atr_mult, max_retest_bars
        self.recovery_body_ratio = recovery_body_ratio
        self.sl_atr_buffer, self.tp_r_mult = sl_atr_buffer, tp_r_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        is_high, is_low = smc.swing_points(df, self.swing_left, self.swing_right)
        conf_high = is_high.shift(self.swing_right).fillna(False).to_numpy()
        conf_low = is_low.shift(self.swing_right).fillna(False).to_numpy()
        swing_high_price = df["high"].shift(self.swing_right).to_numpy()
        swing_low_price = df["low"].shift(self.swing_right).to_numpy()
        atr = ta.atr(df, self.atr_len).to_numpy()

        open_, close_ = df["open"].to_numpy(), df["close"].to_numpy()
        high_, low_ = df["high"].to_numpy(), df["low"].to_numpy()
        n = len(df)
        tol = self.tolerance_pct / 100.0

        recent_highs: list[tuple[int, float]] = []
        recent_lows: list[tuple[int, float]] = []

        pos = 0
        active_sl = active_tp = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        # Bekleyen kurulum: kirilim oldu, geri cekilme/toparlanma bekleniyor.
        pending = None  # {'dir':1/-1, 'level':float, 'since':int}

        def _valid_zone(points: list[tuple[int, float]], pick_max: bool) -> float | None:
            if len(points) < self.min_touches:
                return None
            prices = [p for _, p in points]
            anchor = max(prices) if pick_max else min(prices)
            cluster = [p for p in prices if abs(p - anchor) / anchor <= tol]
            if len(cluster) < self.min_touches:
                return None
            return sum(cluster) / len(cluster)

        for i in range(n):
            # 0) Acik pozisyon varsa, bu barin bracket'e (SL/TP) carpip
            #    carpmadigini KENDI icinde de simule et - core/backtest.py
            #    ayni mantigi calistiracak, burada da tutarli olmali ki
            #    sinyal dogru barda sifira donsun (aksi halde bir sonraki
            #    kurulum taze SL/TP olmadan acilir - scalp_mean_reversion'da
            #    daha once yakalanan hata ailesi).
            if pos != 0:
                sl_t = (pos > 0 and low_[i] <= active_sl) or (pos < 0 and high_[i] >= active_sl)
                tp_t = (pos > 0 and high_[i] >= active_tp) or (pos < 0 and low_[i] <= active_tp)
                if sl_t or tp_t:
                    pos = 0
                    active_sl = active_tp = None

            if conf_high[i]:
                recent_highs.append((i, swing_high_price[i]))
                recent_highs = [(j, p) for j, p in recent_highs if i - j <= self.lookback]
            if conf_low[i]:
                recent_lows.append((i, swing_low_price[i]))
                recent_lows = [(j, p) for j, p in recent_lows if i - j <= self.lookback]

            resistance = _valid_zone(recent_highs, pick_max=True)
            support = _valid_zone(recent_lows, pick_max=False)

            if not np.isnan(atr[i]) and atr[i] > 0:
                # 1) Kararli kirilim tespiti (yeni bekleyen kurulum baslat).
                if pending is None:
                    if resistance is not None and close_[i] > resistance + self.break_atr_mult * atr[i]:
                        pending = {"dir": 1, "level": resistance, "since": i}
                    elif support is not None and close_[i] < support - self.break_atr_mult * atr[i]:
                        pending = {"dir": -1, "level": support, "since": i}

                # 2) Bekleyen kurulum varsa: gecersiz mi oldu, geri cekilme+
                #    toparlanma mumu geldi mi, yoksa zaman asimi mi diye bak.
                elif pending is not None:
                    lvl, d = pending["level"], pending["dir"]
                    bar_range = max(high_[i] - low_[i], 1e-12)
                    strong_close_up = (close_[i] - low_[i]) / bar_range >= self.recovery_body_ratio
                    strong_close_down = (high_[i] - close_[i]) / bar_range >= self.recovery_body_ratio

                    if d == 1:
                        touched = low_[i] <= lvl + self.break_atr_mult * atr[i]
                        invalidated = close_[i] < lvl - self.break_atr_mult * atr[i]
                        if invalidated:
                            pending = None
                        elif pos == 0 and touched and close_[i] > lvl and strong_close_up and close_[i] > open_[i]:
                            pos = 1
                            active_sl = lvl - self.sl_atr_buffer * atr[i]
                            risk = close_[i] - active_sl
                            active_tp = close_[i] + self.tp_r_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_retest_bars:
                            pending = None
                    else:
                        touched = high_[i] >= lvl - self.break_atr_mult * atr[i]
                        invalidated = close_[i] > lvl + self.break_atr_mult * atr[i]
                        if invalidated:
                            pending = None
                        elif pos == 0 and touched and close_[i] < lvl and strong_close_down and close_[i] < open_[i]:
                            pos = -1
                            active_sl = lvl + self.sl_atr_buffer * atr[i]
                            risk = active_sl - close_[i]
                            active_tp = close_[i] - self.tp_r_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_retest_bars:
                            pending = None

            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        return StrategyResult(signal=signal, stop_loss=stop_loss, take_profit=take_profit)
