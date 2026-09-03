"""RSI uyumsuzlugu (divergence) - klasik, deneyimli tuccarlarin en cok
guvendigi tersine donus sinyallerinden biri.

Kural: fiyat YENI BIR DIP yaparken RSI daha YUKSEK bir dip yapiyorsa
(satis baskisi azaliyor, fiyat hala dusse de) -> BOGA UYUMSUZLUGU (bullish
divergence), tersine donus adayi. Simetri: fiyat yeni zirve yaparken RSI
daha dusuk zirve yapiyorsa -> AYI UYUMSUZLUGU.

Arastirma notu: uyumsuzluk sinyalleri en cok UZUN, TEMIZ bir trendin
SONUNDA guvenilir; yatay/dar piyasada RSI zaten rastgele salinip surekli
sahte sinyal uretir. Bu yuzden ONCESINDE net bir trend sartı var (trend_len
EMA'nin egimi).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core import smc
from core.strategy import Strategy, StrategyResult


class DivergenceReversal(Strategy):
    name = "divergence_reversal"

    def __init__(self, swing_left: int = 5, swing_right: int = 5, rsi_len: int = 14,
                 trend_len: int = 100, max_hold: int = 60):
        super().__init__(swing_left=swing_left, swing_right=swing_right, rsi_len=rsi_len,
                          trend_len=trend_len, max_hold=max_hold)
        self.swing_left, self.swing_right = swing_left, swing_right
        self.rsi_len, self.trend_len, self.max_hold = rsi_len, trend_len, max_hold

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        is_high, is_low = smc.swing_points(df, self.swing_left, self.swing_right)
        conf_high = is_high.shift(self.swing_right).fillna(False).to_numpy()
        conf_low = is_low.shift(self.swing_right).fillna(False).to_numpy()

        rsi = ta.rsi(df["close"], self.rsi_len)
        trend = ta.ema(df["close"], self.trend_len)
        downtrend = (df["close"] < trend).to_numpy()
        uptrend = (df["close"] > trend).to_numpy()

        price_high = df["high"].shift(self.swing_right).to_numpy()
        price_low = df["low"].shift(self.swing_right).to_numpy()
        rsi_high = rsi.shift(self.swing_right).to_numpy()
        rsi_low = rsi.shift(self.swing_right).to_numpy()
        close_ = df["close"].to_numpy()

        n = len(df)
        pos, entry_i = 0, -1
        sig_values = np.zeros(n, dtype="int64")
        prev_low_price = prev_low_rsi = None
        prev_high_price = prev_high_rsi = None
        bull_div = np.zeros(n, dtype=bool)
        bear_div = np.zeros(n, dtype=bool)

        for i in range(n):
            if conf_low[i] and not np.isnan(rsi_low[i]):
                if (prev_low_price is not None and downtrend[i]
                        and price_low[i] < prev_low_price and rsi_low[i] > prev_low_rsi):
                    bull_div[i] = True
                prev_low_price, prev_low_rsi = price_low[i], rsi_low[i]
            if conf_high[i] and not np.isnan(rsi_high[i]):
                if (prev_high_price is not None and uptrend[i]
                        and price_high[i] > prev_high_price and rsi_high[i] < prev_high_rsi):
                    bear_div[i] = True
                prev_high_price, prev_high_rsi = price_high[i], rsi_high[i]

            if pos == 0:
                if bull_div[i]:
                    pos, entry_i = 1, i
                elif bear_div[i]:
                    pos, entry_i = -1, i
            elif pos == 1 and (bear_div[i] or (i - entry_i) >= self.max_hold):
                pos = 0
            elif pos == -1 and (bull_div[i] or (i - entry_i) >= self.max_hold):
                pos = 0
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        diag = pd.DataFrame({"rsi": rsi, "ema_trend": trend})
        return StrategyResult(signal=signal, diagnostics=diag)
