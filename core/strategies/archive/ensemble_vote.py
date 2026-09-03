"""Topluluk oylamasi (ensemble) - farkli stratejileri KOMBINE ederek en
basarili birlesimi bulmaya calisir.

Birden fazla bagimsiz stratejinin sinyalini alir; en az `min_votes` tanesi
AYNI yonde anlasirsa pozisyon acilir. Fikir: tek bir stratejinin yanlis
alarm vermesi olasidir, ama birbirinden BAGIMSIZ mantiklarla calisan
birden fazla strateji AYNI ANDA hemfikirse, bu daha guclu bir kanit sayilir
(sinyal gurultuye karsi daha dayanikli olur, ama daha az islem yapar).

research/scan.py PARAM_GRID'inde birden fazla HAZIR bilesim taniml - hangi
kombinasyonun gercekten daha basarili oldugu, digerleri gibi IS/OOS
taramasindan gecerek belirlenir.
"""

from __future__ import annotations

import pandas as pd

from core.strategy import Strategy, StrategyResult


class EnsembleVote(Strategy):
    name = "ensemble_vote"

    def __init__(self, components: str = "supertrend,volume_confirmed_trend,ichimoku", min_votes: int = 2):
        super().__init__(components=components, min_votes=min_votes)
        self.component_names = [c.strip() for c in components.split(",") if c.strip()]
        self.min_votes = min_votes

    def __repr__(self) -> str:
        return f"{self.name}(components={'+'.join(self.component_names)}, min_votes={self.min_votes})"

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        # Dongusel import: core.strategies.__init__ bu dosyayi REGISTRY
        # olustururken import ediyor, bu yuzden REGISTRY'yi ancak
        # generate() CAGRILDIGINDA (modul tam yuklendikten cok sonra) iceri
        # aliyoruz - modul seviyesinde import etseydik circular import hatasi olurdu.
        from core.strategies import REGISTRY

        votes = pd.DataFrame(index=df.index)
        for name in self.component_names:
            votes[name] = REGISTRY[name]().generate(df).signal

        vote_sum = votes.sum(axis=1)
        signal = pd.Series(0, index=df.index, dtype="int64")
        signal[vote_sum >= self.min_votes] = 1
        signal[vote_sum <= -self.min_votes] = -1

        return StrategyResult(signal=signal, diagnostics=votes)
