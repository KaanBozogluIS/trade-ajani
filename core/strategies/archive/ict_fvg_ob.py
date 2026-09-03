"""ICT tarzi FVG + Order Block geri cekilme stratejisi.

Mantik: once piyasa YAPISINI oku (yapi yukselisteyse sadece long dusun,
dususteyse sadece short). Sonra giris tetigi olarak fiyatin yapi yonunde
bir "verimsizlik/dengesizlik" bolgesine (FVG) ya da bir Order Block'a
(guclu harekete yol acan son ters yonlu mum) geri cekilmesini bekle - bu,
"kirilimin tepesinden kovalamak" yerine daha iyi bir fiyattan, trendin
devam ettigi varsayimiyla pozisyon almaya calisir.

Order Block tanimi (basitlestirilmis): bir BOS (yapi kirilimi) olustugu
anda, o kirilimdan hemen once gelen SON TERS YONLU mumun govdesi
(open-close araligi) - kurumsal emirlerin biriktigi varsayilan bolge.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import smc
from core.strategy import Strategy, StrategyResult


class IctFvgOb(Strategy):
    name = "ict_fvg_ob"

    def __init__(self, swing_left: int = 5, swing_right: int = 5, ob_lookback: int = 10):
        super().__init__(swing_left=swing_left, swing_right=swing_right, ob_lookback=ob_lookback)
        self.swing_left, self.swing_right, self.ob_lookback = swing_left, swing_right, ob_lookback

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        ms = smc.market_structure(df, self.swing_left, self.swing_right)
        fvg = smc.fair_value_gaps(df)

        structure = ms["structure"].to_numpy()
        bos_up_event = ms["structure_up_event"].to_numpy()
        bos_down_event = ms["structure_down_event"].to_numpy()
        open_, close_ = df["open"].to_numpy(), df["close"].to_numpy()
        high_, low_ = df["high"].to_numpy(), df["low"].to_numpy()
        bull_fvg, bull_top, bull_bot = (fvg["bull_fvg"].to_numpy(), fvg["bull_gap_top"].to_numpy(),
                                         fvg["bull_gap_bottom"].to_numpy())
        bear_fvg, bear_top, bear_bot = (fvg["bear_fvg"].to_numpy(), fvg["bear_gap_top"].to_numpy(),
                                         fvg["bear_gap_bottom"].to_numpy())

        n = len(df)
        pos = 0
        sig_values = np.zeros(n, dtype="int64")
        active_bull_zone = active_bear_zone = None  # (alt, ust)
        bull_ob = bear_ob = None

        for i in range(n):
            if bull_fvg[i]:
                active_bull_zone = (bull_bot[i], bull_top[i])
            if bear_fvg[i]:
                active_bear_zone = (bear_bot[i], bear_top[i])
            # bolge tamamen "dolduysa" (fiyat icinden gecip ustune ciktiysa) gecersiz say
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

            in_bull_zone = (active_bull_zone is not None and active_bull_zone[0] <= low_[i] <= active_bull_zone[1]) \
                or (bull_ob is not None and bull_ob[0] <= low_[i] <= bull_ob[1])
            in_bear_zone = (active_bear_zone is not None and active_bear_zone[0] <= high_[i] <= active_bear_zone[1]) \
                or (bear_ob is not None and bear_ob[0] <= high_[i] <= bear_ob[1])

            if pos == 0:
                if structure[i] == 1 and in_bull_zone:
                    pos = 1
                elif structure[i] == -1 and in_bear_zone:
                    pos = -1
            elif pos == 1 and structure[i] != 1:
                pos = 0
            elif pos == -1 and structure[i] != -1:
                pos = 0
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        diag = pd.DataFrame({"structure": ms["structure"]})
        return StrategyResult(signal=signal, diagnostics=diag)
