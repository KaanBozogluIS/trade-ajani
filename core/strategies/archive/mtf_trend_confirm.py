"""Coklu zaman dilimi teyidi - "ust zaman diliminin trendine asla karsi
islem acma" kuralinin sarmalayicisi (meta-strateji).

Herhangi bir mevcut stratejiyi (base_strategy) alir, sinyallerini SADECE
DAHA BUYUK bir zaman diliminin trend yonuyle AYNI ISE gecerli sayar.
Profesyonel gunluk tuccarlarin en temel kurallarindan biri budur: kucuk
zaman diliminde "iyi gorunen" bir giris, buyuk resimde ters yondeki bir
trende karsi acilmissa cok daha riskli olur.

Ust zaman dilimi verisi, GIRDI DataFrame'inin KENDISINDEN yeniden
orneklenerek (resample) turetilir - disaridan ayrica veri cekmeye gerek
yok. ONEMLI: ust zaman dilimi barinin degeri, o bar TAM KAPANANA kadar
kullanilamaz - bu yuzden bir bar KAYDIRILIR (shift), sonra alt zaman
dilimine geri yayilir (ffill). Bu kaydirma atlanirsa klasik bir
ileriye-bakma hatasi olusur (henuz kapanmamis ust-TF barinin kapanisini
kullanmak).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.datastore import resample
from core.strategy import Strategy, StrategyResult


class MtfTrendConfirm(Strategy):
    name = "mtf_trend_confirm"

    def __init__(self, base_strategy: str = "ict_swing", htf_rule: str = "4h", htf_ema_len: int = 50):
        super().__init__(base_strategy=base_strategy, htf_rule=htf_rule, htf_ema_len=htf_ema_len)
        self.base_strategy_name, self.htf_rule, self.htf_ema_len = base_strategy, htf_rule, htf_ema_len

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        from core.strategies import REGISTRY  # dongusel import onlemi - bkz. ensemble_vote.py

        base = REGISTRY[self.base_strategy_name]()
        base_result = base.generate(df)

        htf_df = resample(df, self.htf_rule)
        if len(htf_df) < self.htf_ema_len + 2:
            flat = pd.Series(0, index=df.index, dtype="int64")
            return StrategyResult(signal=flat)

        htf_ema = ta.ema(htf_df["close"], self.htf_ema_len)
        htf_trend_raw = np.sign(htf_df["close"] - htf_ema)
        htf_trend_known = htf_trend_raw.shift(1)  # bar TAM KAPANANA kadar bilinmez
        htf_trend_ltf = htf_trend_known.reindex(df.index, method="ffill").fillna(0.0)

        base_signal = base_result.signal.reindex(df.index).fillna(0).astype(int)
        agree = (base_signal == htf_trend_ltf) & (base_signal != 0)
        filtered = base_signal.where(agree, 0).astype("int64")

        stop_loss = base_result.stop_loss.where(agree) if base_result.stop_loss is not None else None
        take_profit = base_result.take_profit.where(agree) if base_result.take_profit is not None else None

        diag = pd.DataFrame({"htf_trend": htf_trend_ltf})
        return StrategyResult(signal=filtered, diagnostics=diag, stop_loss=stop_loss, take_profit=take_profit)
