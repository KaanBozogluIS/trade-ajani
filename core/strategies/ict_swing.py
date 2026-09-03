"""ICT tarzi swing - yapi + FVG/OB girisi, ATR stop + BUYUK hedef (R kati).

`ict_fvg_ob`'dan farki: o strateji cikisi icin yapi kirilimini bekler (ne
zaman kapanacagi belirsiz - bazen cok kisa, bazen cok uzun surer). Bu
versiyon NET bir risk/odul cercevesi kullanir - stop, giris bolgesinin
hemen otesinde (ICT mantigindaki dogal gecersizlik noktasi); hedef ise
riskin sabit bir kati (tp_r_mult). BOYLECE:
  - Kazanma orani DUSUK/ORTA olabilir (stop siki), AMA
  - Her kazanc, her kayiptan tp_r_mult kati BUYUK olur,
  - StrategyResult.stop_loss/take_profit doldugu icin core/backtest.py'nin
    risk-bazli (kaldiracli) pozisyon buyuklugu ile dogrudan uyumludur.
Bu, gunluk/birkaç gunde bir islem yapan, kaldirac kullanan traderlarin
tipik R:R yaklasimini modeller - "az ve OZ, ama buyuk kazanan" felsefesi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core import smc
from core.strategy import Strategy, StrategyResult


class IctSwing(Strategy):
    name = "ict_swing"

    def __init__(self, swing_left: int = 5, swing_right: int = 5, ob_lookback: int = 10,
                 atr_len: int = 14, sl_atr_buffer: float = 0.5, tp_r_mult: float = 2.5):
        super().__init__(swing_left=swing_left, swing_right=swing_right, ob_lookback=ob_lookback,
                          atr_len=atr_len, sl_atr_buffer=sl_atr_buffer, tp_r_mult=tp_r_mult)
        self.swing_left, self.swing_right, self.ob_lookback = swing_left, swing_right, ob_lookback
        self.atr_len, self.sl_atr_buffer, self.tp_r_mult = atr_len, sl_atr_buffer, tp_r_mult

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ms = smc.market_structure(df, self.swing_left, self.swing_right)
        fvg = smc.fair_value_gaps(df)
        atr = ta.atr(df, self.atr_len)

        structure = ms["structure"].to_numpy()
        bos_up_event = ms["structure_up_event"].to_numpy()
        bos_down_event = ms["structure_down_event"].to_numpy()
        open_, close_ = df["open"].to_numpy(), df["close"].to_numpy()
        high_, low_, atr_ = df["high"].to_numpy(), df["low"].to_numpy(), atr.to_numpy()
        bull_fvg, bull_top, bull_bot = (fvg["bull_fvg"].to_numpy(), fvg["bull_gap_top"].to_numpy(),
                                         fvg["bull_gap_bottom"].to_numpy())
        bear_fvg, bear_top, bear_bot = (fvg["bear_fvg"].to_numpy(), fvg["bear_gap_top"].to_numpy(),
                                         fvg["bear_gap_bottom"].to_numpy())

        n = len(df)
        pos = 0
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        active_bull_zone = active_bear_zone = None
        bull_ob = bear_ob = None
        active_sl = active_tp = None

        for i in range(n):
            if bull_fvg[i]:
                active_bull_zone = (bull_bot[i], bull_top[i])
            if bear_fvg[i]:
                active_bear_zone = (bear_bot[i], bear_top[i])
            if active_bull_zone is not None and low_[i] < active_bull_zone[0]:
                active_bull_zone = None
            if active_bear_zone is not None and high_[i] > active_bear_zone[1]:
                active_bear_zone = None

            if bos_up_event[i]:
                for j in range(i - 1, max(i - self.ob_lookback, 0) - 1, -1):
                    if close_[j] < open_[j]:
                        bull_ob = (min(open_[j], close_[j]), max(open_[j], close_[j]))
                        break
            if bos_down_event[i]:
                for j in range(i - 1, max(i - self.ob_lookback, 0) - 1, -1):
                    if close_[j] > open_[j]:
                        bear_ob = (min(open_[j], close_[j]), max(open_[j], close_[j]))
                        break
            if bull_ob is not None and low_[i] < bull_ob[0]:
                bull_ob = None
            if bear_ob is not None and high_[i] > bear_ob[1]:
                bear_ob = None

            # ONEMLI: pozisyon acikken bu barin bracket'e carpip carpmadigini
            # KENDI icinde de simule ediyoruz (core/backtest.py'nin bracket
            # mantigiyla tutarli) - aksi halde sinyal hicbir zaman sifira
            # donmez ve yeni giris taze SL/TP olmadan acilir (scalp_mean_reversion'da
            # daha once yakalanan hatanin ayni ailesi).
            if pos != 0:
                sl_t = active_sl is not None and (
                    (pos > 0 and low_[i] <= active_sl) or (pos < 0 and high_[i] >= active_sl))
                tp_t = active_tp is not None and (
                    (pos > 0 and high_[i] >= active_tp) or (pos < 0 and low_[i] <= active_tp))
                if sl_t or tp_t:
                    pos = 0
                    active_sl = active_tp = None
                elif structure[i] != pos:
                    pos = 0
                    active_sl = active_tp = None

            if pos == 0 and not np.isnan(atr_[i]):
                in_bull_zone = (active_bull_zone is not None and active_bull_zone[0] <= low_[i] <= active_bull_zone[1]) \
                    or (bull_ob is not None and bull_ob[0] <= low_[i] <= bull_ob[1])
                in_bear_zone = (active_bear_zone is not None and active_bear_zone[0] <= high_[i] <= active_bear_zone[1]) \
                    or (bear_ob is not None and bear_ob[0] <= high_[i] <= bear_ob[1])

                if structure[i] == 1 and in_bull_zone:
                    zone_low = min(z for z in [
                        active_bull_zone[0] if active_bull_zone else None,
                        bull_ob[0] if bull_ob else None,
                    ] if z is not None)
                    pos = 1
                    active_sl = zone_low - self.sl_atr_buffer * atr_[i]
                    risk = close_[i] - active_sl
                    active_tp = close_[i] + self.tp_r_mult * risk
                    sl_arr[i], tp_arr[i] = active_sl, active_tp
                elif structure[i] == -1 and in_bear_zone:
                    zone_high = max(z for z in [
                        active_bear_zone[1] if active_bear_zone else None,
                        bear_ob[1] if bear_ob else None,
                    ] if z is not None)
                    pos = -1
                    active_sl = zone_high + self.sl_atr_buffer * atr_[i]
                    risk = active_sl - close_[i]
                    active_tp = close_[i] - self.tp_r_mult * risk
                    sl_arr[i], tp_arr[i] = active_sl, active_tp
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        diag = pd.DataFrame({"structure": ms["structure"]})
        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss, take_profit=take_profit)
