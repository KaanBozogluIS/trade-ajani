"""Hacim-Fiyat Uyumsuzlugu (Absorbsiyon) Stratejisi - bize ozgu, sifirdan
tasarlanmis, Wyckoff'un "efor vs sonuc" (effort vs result) fikrinden
esinlenen ama TAMAMEN kendi kurallarimizla kodlanmis bir strateji.

FIKIR: Bir mumda hacim (EFOR) anormal derecede YUKSEKSE ama fiyat araligi
(SONUC) ATR'a gore KUCUKSE, bu bir UYUMSUZLUK'tur - buyuk bir taraf (satici
ya da alici) agresif girmis ama fiyati beklendigi kadar hareket ettirememis.
Bu, o seviyede KARSI tarafin (buyuk oyuncu) emrini "EMDIGINI" (absorbe
ettigini) gosteren dolayli bir izdir - klasik Wyckoff "spring"/"upthrust"
mantiginin nedensel, olculebilir bir vekili.

Bu TEK BASINA yeterli degil - rastgele bir mumda da olabilir. Bu yuzden
COKLU-DOKUNUSLU bir destek/direnc BOLGESINDE gerceklesmesi sartlaniyor
(breakout_retest_recovery.py / reversal_pullback.py'de dogrulanan "bekleyen
kurulum" mimarisiyle): seviyeye deginme -> pencere icinde bir ABSORBSIYON
mumu ariyoruz -> gorulduyse, fiyatin O ABSORBSIYON MUMUNUN UCUNU KIRMASI
(gercek yon teyidi) ile giris tetiklenir. Boylece emilimin GERCEKTEN ise
yaradigini (fiyat lehte donduğunu) TEYIT ETMEDEN girmiyoruz - tek basina
"buyuk hacim + kucuk aralik" cok gurultulu bir sinyal, teyitle guclendirildi.

Opsiyonel EMA rejim filtresi (require_trend_align): acik ise LONG sadece
fiyat uzun-EMA'nin USTUNDEYKEN, SHORT sadece ALTINDAYKEN aliniyor - "ana
akinti yonunde emilim ara" mantigi. Kapaliysa (varsayilan) saf mean-
reversion/dip-tepe avciligi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core import smc
from core.strategy import Strategy, StrategyResult


class VolumeAbsorption(Strategy):
    name = "hacim_uyumsuzlugu_stratejisi"

    def __init__(self, swing_left: int = 5, swing_right: int = 5, lookback: int = 150,
                 tolerance_pct: float = 0.15, min_touches: int = 2, max_confirm_bars: int = 30,
                 invalidate_atr_mult: float = 2.0,
                 vol_len: int = 20, absorb_vol_mult: float = 1.2, absorb_range_mult: float = 1.1,
                 atr_len: int = 14, sl_atr_buffer: float = 0.3, tp_r_mult: float = 2.0,
                 ema_trend_len: int = 100, require_trend_align: bool = False):
        super().__init__(swing_left=swing_left, swing_right=swing_right, lookback=lookback,
                          tolerance_pct=tolerance_pct, min_touches=min_touches,
                          max_confirm_bars=max_confirm_bars, invalidate_atr_mult=invalidate_atr_mult,
                          vol_len=vol_len, absorb_vol_mult=absorb_vol_mult,
                          absorb_range_mult=absorb_range_mult, atr_len=atr_len,
                          sl_atr_buffer=sl_atr_buffer, tp_r_mult=tp_r_mult,
                          ema_trend_len=ema_trend_len, require_trend_align=require_trend_align)
        self.swing_left, self.swing_right, self.lookback = swing_left, swing_right, lookback
        self.tolerance_pct, self.min_touches = tolerance_pct, min_touches
        self.max_confirm_bars, self.invalidate_atr_mult = max_confirm_bars, invalidate_atr_mult
        self.vol_len, self.absorb_vol_mult, self.absorb_range_mult = vol_len, absorb_vol_mult, absorb_range_mult
        self.atr_len, self.sl_atr_buffer, self.tp_r_mult = atr_len, sl_atr_buffer, tp_r_mult
        self.ema_trend_len, self.require_trend_align = ema_trend_len, require_trend_align

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        is_high, is_low = smc.swing_points(df, self.swing_left, self.swing_right)
        conf_high = is_high.shift(self.swing_right).fillna(False).to_numpy()
        conf_low = is_low.shift(self.swing_right).fillna(False).to_numpy()
        swing_high_price = df["high"].shift(self.swing_right).to_numpy()
        swing_low_price = df["low"].shift(self.swing_right).to_numpy()

        atr = ta.atr(df, self.atr_len).to_numpy()
        vol_avg = df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean().to_numpy()
        ema_trend = ta.ema(df["close"], self.ema_trend_len).to_numpy()

        open_, close_ = df["open"].to_numpy(), df["close"].to_numpy()
        high_, low_ = df["high"].to_numpy(), df["low"].to_numpy()
        volume_ = df["volume"].to_numpy()
        n = len(df)
        tol = self.tolerance_pct / 100.0

        recent_highs: list[tuple[int, float]] = []
        recent_lows: list[tuple[int, float]] = []

        def _valid_zone(points: list[tuple[int, float]], pick_max: bool) -> float | None:
            if len(points) < self.min_touches:
                return None
            prices = [p for _, p in points]
            anchor = max(prices) if pick_max else min(prices)
            cluster = [p for p in prices if abs(p - anchor) / anchor <= tol]
            if len(cluster) < self.min_touches:
                return None
            return sum(cluster) / len(cluster)

        pos = 0
        active_sl = active_tp = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        min_warmup = max(self.ema_trend_len, self.vol_len, self.atr_len) + 2
        # Bekleyen kurulum: bolgeye deginme oldu, ABSORBSIYON mumu + yon
        # teyidi bekleniyor. {'dir', 'level', 'since', 'absorb_seen',
        # 'confirm_level'} - confirm_level, absorbsiyon mumunun ucu (LONG'da
        # high, SHORT'ta low) - fiyat bunu KIRARSA teyit sayilir.
        pending = None

        for i in range(n):
            # 0) Acik pozisyon varsa bracket'e carpip carpmadigini KENDI
            #    icinde de simule et (backtest.py ile ayni mantik).
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

            if pos == 0 and i >= min_warmup and not np.isnan(atr[i]) and atr[i] > 0 and not np.isnan(vol_avg[i]):
                buffer = self.sl_atr_buffer * atr[i]
                vol_ratio = volume_[i] / vol_avg[i] if vol_avg[i] > 0 else 0.0
                range_ratio = (high_[i] - low_[i]) / atr[i]
                is_absorption_bar = vol_ratio >= self.absorb_vol_mult and range_ratio <= self.absorb_range_mult

                if pending is None:
                    resistance = _valid_zone(recent_highs, pick_max=True)
                    support = _valid_zone(recent_lows, pick_max=False)
                    if support is not None and low_[i] <= support + buffer:
                        pending = {"dir": 1, "level": support, "since": i,
                                   "absorb_seen": False, "confirm_level": None}
                    elif resistance is not None and high_[i] >= resistance - buffer:
                        pending = {"dir": -1, "level": resistance, "since": i,
                                   "absorb_seen": False, "confirm_level": None}

                elif pending is not None:
                    lvl, d = pending["level"], pending["dir"]
                    trend_up = close_[i] > ema_trend[i]
                    trend_down = close_[i] < ema_trend[i]

                    if d == 1:
                        invalidated = close_[i] < lvl - self.invalidate_atr_mult * atr[i]
                        if invalidated:
                            pending = None
                        else:
                            # Absorbsiyon mumu, pending ACIKKEN (yani seviyeye
                            # zaten yakinken, invalidasyon uzaklasmayi zaten
                            # sinirliyor) buyuk hacim + kucuk aralik ile
                            # olusuyorsa kaydedilir - "satis EMILDI". Ayrica
                            # 'tam o barda tekrar deginme' sarti ARANMIYOR -
                            # bu, ilk tasarimda (reversal_pullback'te de
                            # yakalanan) ayni-barda-cok-kosul tuzagiydi.
                            if is_absorption_bar:
                                pending["absorb_seen"] = True
                                pending["confirm_level"] = max(pending["confirm_level"] or 0.0, high_[i])
                            trend_ok = (not self.require_trend_align) or trend_up
                            if pending["absorb_seen"] and pending["confirm_level"] is not None \
                                    and close_[i] > pending["confirm_level"] and trend_ok:
                                pos = 1
                                active_sl = min(lvl, low_[i]) - buffer
                                risk = close_[i] - active_sl
                                active_tp = close_[i] + self.tp_r_mult * risk
                                sl_arr[i], tp_arr[i] = active_sl, active_tp
                                pending = None
                            elif i - pending["since"] > self.max_confirm_bars:
                                pending = None
                    else:
                        invalidated = close_[i] > lvl + self.invalidate_atr_mult * atr[i]
                        if invalidated:
                            pending = None
                        else:
                            if is_absorption_bar:
                                pending["absorb_seen"] = True
                                prev = pending["confirm_level"]
                                pending["confirm_level"] = low_[i] if prev is None else min(prev, low_[i])
                            trend_ok = (not self.require_trend_align) or trend_down
                            if pending["absorb_seen"] and pending["confirm_level"] is not None \
                                    and close_[i] < pending["confirm_level"] and trend_ok:
                                pos = -1
                                active_sl = max(lvl, high_[i]) + buffer
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
