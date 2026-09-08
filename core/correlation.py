"""Sembollerin bir referansa (varsayilan BTC) gore korelasyon ve beta analizi.

Gunluk/kaldiracli trader'in "BTC hareket ettiginde hangi altcoin DAHA HIZLI/
BUYUK hareket eder" sorusuna nicel bir cevap arar:
  - YUKSEK korelasyon + YUKSEK beta -> BTC'nin "kaldiracli yansimasi" (BTC
    yon verince bu coin daha buyuk hareket eder - hizli hedefe ulasmak
    isteyen gunluk trader icin ilginc, ama risk de ayni oranda buyur).
  - DUSUK korelasyon -> BTC'den BAGIMSIZ, kendi dinamigi olan coin
    (portfoy cesitlendirmesi / BTC yatay giderken firsat).

Beta, klasik finans regresyon katsayisidir: y = alpha + beta*x + hata,
burada x = referansin (BTC) getirisi, y = hedef coin'in getirisi. beta=1.5
demek "BTC %1 hareket ettiginde bu coin ORTALAMA %1.5 hareket eder" demek.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def compute_correlation_beta(ref_returns: pd.Series, target_returns: pd.Series,
                              min_overlap: int = 30) -> tuple[float, float, int]:
    """Iki getiri serisi arasindaki Pearson korelasyonu ve beta'yi (regresyon
    egimi) hesaplar. Ortak (index kesisimi) bar sayisi min_overlap'in
    altindaysa (nan, nan, n) doner - istatistiksel olarak anlamsiz kabul
    edilir."""
    aligned = pd.concat([ref_returns, target_returns], axis=1, join="inner").dropna()
    n = len(aligned)
    if n < min_overlap:
        return float("nan"), float("nan"), n
    x, y = aligned.iloc[:, 0].to_numpy(), aligned.iloc[:, 1].to_numpy()
    var_x = np.var(x)
    if var_x <= 0:
        return float("nan"), float("nan"), n
    corr = float(np.corrcoef(x, y)[0, 1])
    beta = float(np.cov(x, y, ddof=1)[0, 1] / var_x)
    return corr, beta, n


def normalized_price(close: pd.Series) -> pd.Series:
    """Ilk degeri 100 kabul edip yuzdesel bazda endeksler - farkli fiyat
    olceklerindeki iki sembolu AYNI eksende karsilastirmak icin (ornegin
    BTC ~$80,000 ile bir altcoin ~$0.05 dogrudan ust uste cizilemez)."""
    close = close.dropna()
    if close.empty:
        return close
    return close / close.iloc[0] * 100.0
