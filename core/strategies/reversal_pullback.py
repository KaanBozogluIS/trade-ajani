"""Tepe/Dip Avcisi - bize ozgu, sifirdan tasarlanmis, REJIM-UYARLANABILIR strateji.

Kullanicinin TradingView'de kendi kurdugu panel (RSI14, MACD Hist, EMA20/50,
Ana Trend EMA200, Hacim orani, ADX rejim, cok-dokunuşlu destek/direnc
seviyeleri) ile ayni faktorleri kullanir - ama burada HER FAKTOR nedensel
(t anindaki karar yalnizca <=t verisinden) ve gercek bir backtest motoruyla
dogrulanabilir.

IKI FARKLI REJIMDE IKI FARKLI MANTIK:
  1) TRENDLI (ADX >= adx_trend_min) VE fiyat EMA200'un dogru tarafinda:
     "duzeltmede alim/satim" - ana trend SURUYOR, kisa bir geri cekilme
     (COK derin olmayan bir RSI dususu) destek bolgesine kadar iniyor,
     momentum (MACD histogram) tekrar lehte donuyor -> trend YONUNDE giris.
     Bu, "artan bir coin'de duzeltmede alim yapip parayi buyutme" mantigi.
  2) YATAY (ADX < adx_trend_min, belirgin trend yok): "aralik ucundan donus"
     - fiyat COK-DOKUNUŞLU bir destek/direnc bolgesine COK derin bir RSI
     asiri-satim/asiri-alim ile geliyor, MACD histogram donuyor, hacim ve
     mum kapanisi reddedisi (rejection) teyit ediyor -> aralik ORTASINA
     dogru (mean-reversion) giris.

Ilk tasarimda 5 kosulun (deginme+momentum+hacim+mum+RSI) AYNI BARDA
birlesmesi sartiydi - bu pratikte neredeyse hic tetiklenmiyordu (108 sembol
x 1h taramasinda 5 islemin altinda kaldi). breakout_retest_recovery.py'de
DAHA ONCE dogrulanan "bekleyen kurulum" mimarisine gecildi:
  1) fiyat bir destek/direnc BOLGESINE (min_touches kez test edilmis) DEGDIGINDE
     bir "pending" (bekleyen) kurulum ACILIR - HENUZ giris yok.
  2) pending ACIKKEN, sonraki max_confirm_bars bar icinde HERHANGI BIRINDE
     asagidaki UCU birlikte gerceklesirse giris tetiklenir:
       a) RSI esik alaninda (rejime gore farkli esik - trendde sig, yatayda derin)
       b) MACD histogram YEREL DIP/TEPE yapip LEHTE DONUYOR (momentum kaymasi
          icin basit, nedensel bir vekil - gercek fiyat/gosterge uyumsuzlugu
          (divergence) tespiti çok daha karmasik/kirilgan olurdu)
       c) hacim, ortalamanin uzerinde (katilim teyidi)
       d) mum, seviyeye DOKUNUP GERI TEPTIGINI gosteriyor (reddedis mumu)
  3) fiyat, seviyeyi invalidate_atr_mult kadar KAPANISLA gecerse (kurulum
     gecersiz) ya da pencere dolarsa (zaman asimi) pending iptal edilir.

Cikis: stop, kirilan/test edilen seviyenin hemen otesinde; hedef riskin
sabit bir kati (tp_r_mult) - trend rejiminde daha genis (trend suruyor
varsayimi), yatay rejimde daha dar (aralik ortasina donus varsayimi).

TOLERANS BULGUSU (research/reversal_hunt.py ile 108 sembol IS/OOS): gevsek
bir bolge toleransi (%0.4-0.6) "destek/direnc" olarak asiri gevsek/kaba
seviyeleri de kabul ediyordu - bu, zayif kurulumlari filtrelemiyordu. Sikilik
%0.15'e cekilince (deginmelerin GERCEKTEN dar bir banda kumelenmesi
sartiyla) 14 sembollik ilk kesif kumesinde tam-tarih PF 1.28 -> 1.77'ye
cikti VE ayni ayarla 108 sembol evreninde tarandiginda 20 FARKLI 1sa
sembolde (ETHUSDT, DOTUSDT, LINKUSDT, UNIUSDT, ARUSDT, DOGEUSDT dahil)
bagimsiz olarak dogrulandi - varsayilan artik tolerance_pct=0.15.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core import smc
from core.strategy import Strategy, StrategyResult


class ReversalPullback(Strategy):
    # "TEPE/DIP Stratejisi" - rejime gore trend-ici duzeltme alimi/satimi
    # (ADX trendli) ya da aralik-ucu donus (ADX yatay) yapar.
    name = "tepe_dip_stratejisi"

    def __init__(self, swing_left: int = 5, swing_right: int = 5, lookback: int = 150,
                 tolerance_pct: float = 0.15, min_touches: int = 2, max_confirm_bars: int = 30,
                 invalidate_atr_mult: float = 2.0,
                 rsi_len: int = 14, rsi_oversold_range: float = 40.0, rsi_oversold_trend: float = 55.0,
                 macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 vol_len: int = 20, vol_mult: float = 1.0, recovery_body_ratio: float = 0.5,
                 atr_len: int = 14, sl_atr_buffer: float = 0.3,
                 adx_len: int = 14, adx_trend_min: float = 22.0, ema_trend_len: int = 200,
                 tp_r_mult_trend: float = 3.0, tp_r_mult_range: float = 1.5):
        super().__init__(swing_left=swing_left, swing_right=swing_right, lookback=lookback,
                          tolerance_pct=tolerance_pct, min_touches=min_touches,
                          max_confirm_bars=max_confirm_bars, invalidate_atr_mult=invalidate_atr_mult,
                          rsi_len=rsi_len, rsi_oversold_range=rsi_oversold_range,
                          rsi_oversold_trend=rsi_oversold_trend, macd_fast=macd_fast,
                          macd_slow=macd_slow, macd_signal=macd_signal, vol_len=vol_len,
                          vol_mult=vol_mult, recovery_body_ratio=recovery_body_ratio,
                          atr_len=atr_len, sl_atr_buffer=sl_atr_buffer, adx_len=adx_len,
                          adx_trend_min=adx_trend_min, ema_trend_len=ema_trend_len,
                          tp_r_mult_trend=tp_r_mult_trend, tp_r_mult_range=tp_r_mult_range)
        self.swing_left, self.swing_right, self.lookback = swing_left, swing_right, lookback
        self.tolerance_pct, self.min_touches = tolerance_pct, min_touches
        self.max_confirm_bars, self.invalidate_atr_mult = max_confirm_bars, invalidate_atr_mult
        self.rsi_len = rsi_len
        self.rsi_oversold_range, self.rsi_oversold_trend = rsi_oversold_range, rsi_oversold_trend
        # RSI ust esikleri asiri-satim esiklerinin aynasi (100 - deger).
        self.rsi_overbought_range = 100.0 - rsi_oversold_range
        self.rsi_overbought_trend = 100.0 - rsi_oversold_trend
        self.macd_fast, self.macd_slow, self.macd_signal = macd_fast, macd_slow, macd_signal
        self.vol_len, self.vol_mult, self.recovery_body_ratio = vol_len, vol_mult, recovery_body_ratio
        self.atr_len, self.sl_atr_buffer = atr_len, sl_atr_buffer
        self.adx_len, self.adx_trend_min, self.ema_trend_len = adx_len, adx_trend_min, ema_trend_len
        self.tp_r_mult_trend, self.tp_r_mult_range = tp_r_mult_trend, tp_r_mult_range

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        is_high, is_low = smc.swing_points(df, self.swing_left, self.swing_right)
        conf_high = is_high.shift(self.swing_right).fillna(False).to_numpy()
        conf_low = is_low.shift(self.swing_right).fillna(False).to_numpy()
        swing_high_price = df["high"].shift(self.swing_right).to_numpy()
        swing_low_price = df["low"].shift(self.swing_right).to_numpy()

        atr = ta.atr(df, self.atr_len).to_numpy()
        rsi = ta.rsi(df["close"], self.rsi_len).to_numpy()
        hist = ta.macd(df["close"], self.macd_fast, self.macd_slow, self.macd_signal)["hist"].to_numpy()
        adx = ta.adx(df, self.adx_len)["adx"].to_numpy()
        ema_trend = ta.ema(df["close"], self.ema_trend_len).to_numpy()
        vol_avg = df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean().to_numpy()

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
        min_warmup = max(self.ema_trend_len, self.vol_len, self.macd_slow, self.rsi_len, self.adx_len) + 2
        # Bekleyen kurulum: bolgeye deginme oldu, tetikleyici (RSI+momentum+
        # hacim+mum) bekleniyor. {'dir':1/-1, 'level':float, 'since':int}
        pending = None

        for i in range(n):
            # 0) Acik pozisyon varsa bracket'e carpip carpmadigini KENDI icinde
            #    de simule et - core/backtest.py ayni mantigi calistiracak
            #    (breakout_retest_recovery.py / ict_swing.py'deki ayni desen).
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

            if pos == 0 and i >= min_warmup and not np.isnan(atr[i]) and atr[i] > 0:
                buffer = self.sl_atr_buffer * atr[i]

                if pending is None:
                    resistance = _valid_zone(recent_highs, pick_max=True)
                    support = _valid_zone(recent_lows, pick_max=False)
                    # NOT: RSI'nin "en asiri" degeri VE momentumun "en az bir
                    # kez donmesi" pencere BOYUNCA izlenir - deginme ANINDA
                    # deger ve toparlanma mumu NADIREN ayni bara denk gelir
                    # (fiyat RSI dibini yaptiktan birkaç bar SONRA toparlanir).
                    # Aksi halde (hepsi ayni barda sart) neredeyse hic
                    # tetiklenmiyordu - bkz. research/reversal_hunt.py teshisi.
                    if support is not None and low_[i] <= support + buffer:
                        pending = {"dir": 1, "level": support, "since": i,
                                   "extreme_rsi": rsi[i], "mom_seen": False}
                    elif resistance is not None and high_[i] >= resistance - buffer:
                        pending = {"dir": -1, "level": resistance, "since": i,
                                   "extreme_rsi": rsi[i], "mom_seen": False}

                elif pending is not None:
                    lvl, d = pending["level"], pending["dir"]
                    trending = adx[i] >= self.adx_trend_min
                    uptrend = close_[i] > ema_trend[i]
                    downtrend = close_[i] < ema_trend[i]
                    vol_confirm = volume_[i] >= self.vol_mult * vol_avg[i]
                    bar_range = max(high_[i] - low_[i], 1e-12)
                    # MACD histogram YEREL DIP/TEPE yapip donuyor mu (basit,
                    # nedensel momentum-kaymasi vekili) - pencerede GORULDUYSE
                    # (mom_seen) yeter, tetikleyici barla ayni olmasi gerekmez.
                    if d == 1:
                        pending["extreme_rsi"] = min(pending["extreme_rsi"], rsi[i])
                        if hist[i] > hist[i - 1] <= hist[i - 2]:
                            pending["mom_seen"] = True

                        invalidated = close_[i] < lvl - self.invalidate_atr_mult * atr[i]
                        bullish_reject = (close_[i] - low_[i]) / bar_range >= self.recovery_body_ratio \
                            and close_[i] > open_[i]
                        rsi_ok = (trending and uptrend and pending["extreme_rsi"] <= self.rsi_oversold_trend) or \
                                 ((not trending) and pending["extreme_rsi"] <= self.rsi_oversold_range)
                        if invalidated:
                            pending = None
                        elif bullish_reject and vol_confirm and pending["mom_seen"] and rsi_ok:
                            pos = 1
                            active_sl = min(lvl, low_[i]) - buffer
                            risk = close_[i] - active_sl
                            tp_mult = self.tp_r_mult_trend if trending else self.tp_r_mult_range
                            active_tp = close_[i] + tp_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_confirm_bars:
                            pending = None
                    else:
                        pending["extreme_rsi"] = max(pending["extreme_rsi"], rsi[i])
                        if hist[i] < hist[i - 1] >= hist[i - 2]:
                            pending["mom_seen"] = True

                        invalidated = close_[i] > lvl + self.invalidate_atr_mult * atr[i]
                        bearish_reject = (high_[i] - close_[i]) / bar_range >= self.recovery_body_ratio \
                            and close_[i] < open_[i]
                        rsi_ok = (trending and downtrend and pending["extreme_rsi"] >= self.rsi_overbought_trend) or \
                                 ((not trending) and pending["extreme_rsi"] >= self.rsi_overbought_range)
                        if invalidated:
                            pending = None
                        elif bearish_reject and vol_confirm and pending["mom_seen"] and rsi_ok:
                            pos = -1
                            active_sl = max(lvl, high_[i]) + buffer
                            risk = active_sl - close_[i]
                            tp_mult = self.tp_r_mult_trend if trending else self.tp_r_mult_range
                            active_tp = close_[i] - tp_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_confirm_bars:
                            pending = None

            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        return StrategyResult(signal=signal, stop_loss=stop_loss, take_profit=take_profit)
