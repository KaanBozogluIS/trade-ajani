"""Yuvarlak Sayi Manyetizmasi Stratejisi - psikolojik olarak "yuvarlak"
fiyat seviyelerinin (100.000, 50.000, 0.05 gibi) - GECMISTE ORAYA DOKUNULMUS
OLMASINDAN BAGIMSIZ OLARAK - davranis uzerindeki etkisini test eder.

FIKIR: cok sayida trader/bot ayni "yuvarlak" sayilara (100k, 50k, 0.10,
1.00 gibi - insan zihninin dogal olarak yuvarladigi degerler) stop/kar-al/
yeni-pozisyon emri koyar. Bu, o seviyede GERCEK bir emir yogunlasmasi
yaratir - kalabaligin AYNI YERE bakmasindan dogan, kendi kendini
gerceklestiren bir psikolojik manyetizma (bkz. sohbet notlari).

BU, `altcoin_stratejisi`/`tepe_dip_stratejisi`nin kullandigi "cok-dokunuslu
destek/direnc" (smc.swing_points ile o SEMBOLUN KENDI GECMISINDE fiilen
test edilmis seviyeler) mantigindan FARKLI bir hipotez: burada seviye,
fiyatin daha once oraya UGRAMIS OLMASINDAN degil, SAYININ KENDISININ
"yuvarlak" olmasindan (1-2-5-10 dizisi, klasik grafik ekseni araliklari)
geliyor - hic test edilmemis, taze bir sembolde bile ISLEYEBILIR (cunku
gecmis fiyat verisine degil, SAYININ BUYUKLUGUNE bagli).

Mimari: reversal_pullback.py'de dogrulanan "bekleyen kurulum" (pending)
deseni - fiyat yuvarlak seviyeye deginince pencere acilir, hacim+mum
reddi+RSI toparlanmasi teyidi gelirse giris tetiklenir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult

# 1-2-5-10 dizisi: klasik grafik ekseni araliklarinin ta kendisi - insan
# gozunun "yuvarlak" kabul ettigi carpanlar.
_ROUND_MULTIPLIERS = np.array([1.0, 2.0, 2.5, 5.0, 10.0])


def _nearest_round_level(price: float) -> float:
    if price <= 0 or np.isnan(price):
        return np.nan
    magnitude = 10.0 ** np.floor(np.log10(price))
    candidates = _ROUND_MULTIPLIERS * magnitude
    return float(candidates[np.argmin(np.abs(candidates - price))])


class RoundNumberMagnet(Strategy):
    name = "yuvarlak_sayi_stratejisi"

    def __init__(self, tolerance_pct: float = 0.3, max_confirm_bars: int = 20,
                 invalidate_atr_mult: float = 2.0,
                 vol_len: int = 20, vol_mult: float = 1.1, recovery_body_ratio: float = 0.5,
                 rsi_len: int = 14, rsi_min: float = 35.0, rsi_max: float = 65.0,
                 atr_len: int = 14, sl_atr_buffer: float = 0.3, tp_r_mult: float = 2.0):
        super().__init__(tolerance_pct=tolerance_pct, max_confirm_bars=max_confirm_bars,
                          invalidate_atr_mult=invalidate_atr_mult, vol_len=vol_len, vol_mult=vol_mult,
                          recovery_body_ratio=recovery_body_ratio, rsi_len=rsi_len,
                          rsi_min=rsi_min, rsi_max=rsi_max, atr_len=atr_len,
                          sl_atr_buffer=sl_atr_buffer, tp_r_mult=tp_r_mult)
        self.tolerance_pct, self.max_confirm_bars = tolerance_pct, max_confirm_bars
        self.invalidate_atr_mult = invalidate_atr_mult
        self.vol_len, self.vol_mult, self.recovery_body_ratio = vol_len, vol_mult, recovery_body_ratio
        self.rsi_len, self.rsi_min, self.rsi_max = rsi_len, rsi_min, rsi_max
        self.atr_len, self.sl_atr_buffer, self.tp_r_mult = atr_len, sl_atr_buffer, tp_r_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        close_ = df["close"].to_numpy()
        open_ = df["open"].to_numpy()
        high_, low_ = df["high"].to_numpy(), df["low"].to_numpy()
        volume_ = df["volume"].to_numpy()
        n = len(df)

        round_level = np.array([_nearest_round_level(c) for c in close_])
        atr = ta.atr(df, self.atr_len).to_numpy()
        rsi = ta.rsi(df["close"], self.rsi_len).to_numpy()
        vol_avg = df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean().to_numpy()

        min_warmup = max(self.vol_len, self.rsi_len, self.atr_len) + 2
        tol = self.tolerance_pct / 100.0

        pos = 0
        active_sl = active_tp = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        pending = None  # {'dir':1/-1, 'level':float, 'since':int}

        for i in range(n):
            if pos != 0:
                sl_t = (pos > 0 and low_[i] <= active_sl) or (pos < 0 and high_[i] >= active_sl)
                tp_t = (pos > 0 and high_[i] >= active_tp) or (pos < 0 and low_[i] <= active_tp)
                if sl_t or tp_t:
                    pos = 0
                    active_sl = active_tp = None

            if pos == 0 and i >= min_warmup and not np.isnan(atr[i]) and atr[i] > 0 \
                    and not np.isnan(round_level[i]):
                lvl = round_level[i]
                buffer = self.sl_atr_buffer * atr[i]
                near = abs(close_[i] - lvl) / lvl <= tol

                if pending is None:
                    if near:
                        # Yon: fiyat seviyenin ALTINDAYSA yukaridan gelen
                        # direnc gibi (SHORT adayi), USTUNDEYSE destek gibi
                        # (LONG adayi) davranmasi beklenir - klasik destek/
                        # direnc polarite mantigi, ama seviye SABIT/yuvarlak.
                        d = 1 if close_[i] >= lvl else -1
                        pending = {"dir": d, "level": lvl, "since": i}
                else:
                    d, lvl_p = pending["dir"], pending["level"]
                    vol_confirm = volume_[i] >= self.vol_mult * vol_avg[i] if not np.isnan(vol_avg[i]) else False
                    bar_range = max(high_[i] - low_[i], 1e-12)
                    rsi_ok_long = not np.isnan(rsi[i]) and self.rsi_min <= rsi[i] <= self.rsi_max
                    if d == 1:
                        invalidated = close_[i] < lvl_p - self.invalidate_atr_mult * atr[i]
                        bullish_reject = (close_[i] - low_[i]) / bar_range >= self.recovery_body_ratio \
                            and close_[i] > open_[i]
                        if invalidated:
                            pending = None
                        elif bullish_reject and vol_confirm and rsi_ok_long:
                            pos = 1
                            active_sl = lvl_p - buffer
                            risk = close_[i] - active_sl
                            active_tp = close_[i] + self.tp_r_mult * risk
                            sl_arr[i], tp_arr[i] = active_sl, active_tp
                            pending = None
                        elif i - pending["since"] > self.max_confirm_bars:
                            pending = None
                    else:
                        invalidated = close_[i] > lvl_p + self.invalidate_atr_mult * atr[i]
                        bearish_reject = (high_[i] - close_[i]) / bar_range >= self.recovery_body_ratio \
                            and close_[i] < open_[i]
                        if invalidated:
                            pending = None
                        elif bearish_reject and vol_confirm and rsi_ok_long:
                            pos = -1
                            active_sl = lvl_p + buffer
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
