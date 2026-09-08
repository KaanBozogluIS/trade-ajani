"""Konfluens (Coklu Onay) Stratejisi - "kesin tepe/dip" arayisi yerine,
BIRBIRINDEN BAGIMSIZ mantiklarla calisan, zaten AYRI AYRI dogrulanmis
stratejilerin AYNI ANDA hemfikir oldugu anlari yakalar.

Fikir: tek bir stratejinin yanlis alarm vermesi olasidir, ama farkli
matematiksel temellerden (bolge+RSI+MACD+hacim rejimi vs. Wyckoff hacim-
emilim vs. coklu-dokunuşlu kirilim-toparlanma) gelen birden fazla bagimsiz
sinyal AYNI ANDA anlasirsa, bu daha guclu bir kanit sayilir - sinyal
gurultuye karsi daha dayanikli olur (ama daha AZ islem yapar, cunku hepsi
nadiren ayni anda hizalanir).

`core/strategies/archive/ensemble_vote.py`'nin (bu projenin genel amacli
oylama motoru) ozel bir kullanimi - varsayilan bilesenler artik bu
oturumda dogrulanan 3 "bolge/donus" ailesi strateji: tepe_dip_stratejisi,
hacim_uyumsuzlugu_stratejisi, altcoin_stratejisi.
"""

from __future__ import annotations

import pandas as pd

from core.strategy import Strategy, StrategyResult


class ConfluenceVote(Strategy):
    name = "konfluens_stratejisi"

    def __init__(self, components: str = "tepe_dip_stratejisi,hacim_uyumsuzlugu_stratejisi,altcoin_stratejisi",
                 min_votes: int = 2):
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
