"""BTC Sikisma-Kirilim Stratejisi - buyuk/likit coinler icin, ozellikle
BTC'nin karakterine (uzun konsolidasyon + patlamali kirilim + COK UZUN
sureli trendler) gore sifirdan tasarlanmis strateji.

FIKIR: BTC gibi buyuk-hacimli, kurumsal agirlikli varliklar coklu-dokunuslu
destek/direnc gibi "teknik seviyelere" digerleri (kucuk/orta altcoinler)
kadar saygili degil (bkz. altcoin_stratejisi'nin BTC'de neden calismadigi -
core/strategies/breakout_retest_recovery.py docstring'i, ve major_stratejisi
- Donchian+ADX kirilim - BTC'de de saglam sonuc VERMEDI). Ama BTC'nin
GERCEKTEN belirgin bir davranisi var: UZUN SESSIZLIK (dusuk oynaklik,
"sikisma") donemleri, ardindan PATLAMALI, UZUN SURELI yon degisimleri
(bkz. major_trend_rider.py docstring'indeki "ZEC'in tum donem +binlerce %
hareketi" mantigi - ayni fikir burada OYNAKLIK REJIMI'ne uygulaniyor).

Bu strateji IKI ONCEKI DOGRULANMIS FIKRI birlestiriyor:
  1) GIRIS: "sikisma" tespiti - Bollinger bandi Keltner kanalinin ICINE
     girdiginde piyasa sikisir (oynaklik dusuk, enerji birikir); Bollinger
     tekrar disariya tastiginda ("sikisma acildi") + HACIM TEYIDI (factor_lab.py
     ile BIZIM dogruladigimiz gercek bir faktor - bkz. core/strategies/
     volume_confirmed_trend.py) ile giris. Klasik TTM Squeeze'den (core/
     strategies/archive/squeeze_breakout.py, hic dogrulanamadi) farki:
     hacim teyidi + asagidaki 2) maddesi.
  2) CIKIS: sabit bir hedef DEGIL, "chandelier" (candan) IZ SUREN STOP -
     major_trend_rider.py'de ETH/BNB icin DOGRULANMIS ayni mekanizma
     (pozisyon acildiktan sonraki en iyi fiyatin ATR kati kadar gerisi,
     sadece lehte hareket eder). Boylece BTC'nin UZUN SURELI trendlerinde
     erken cikip parayi masada birakmiyoruz - ayni zamanda squeeze_breakout'un
     "cikis mekanizmasi yok" eksikligini kapatiyor.

`emit_stop_loss=False` (varsayilan): saf sinyal-tabanli (major_trend_rider
ile AYNI onemli neden - risk-bazli kaldirac boyutlandirma icin `True`
yapilirsa bar-ici/gercek-zamanli bir stop emri varsayimina gecilir, sonuclar
KAPANIS-bazli moddan farkli cikar, bu bir hata degil iki farkli yurutme
varsayiminin dogal sonucu - bkz. major_trend_rider.py'deki ayni aciklama).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class SqueezeChandelier(Strategy):
    name = "sikisma_kirilim_stratejisi"

    def __init__(self, bb_len: int = 20, bb_mult: float = 2.0, kc_len: int = 20,
                 kc_mult: float = 1.5, vol_len: int = 20, vol_mult: float = 1.2,
                 atr_len: int = 14, chandelier_mult: float = 3.0,
                 emit_stop_loss: bool = False):
        super().__init__(bb_len=bb_len, bb_mult=bb_mult, kc_len=kc_len, kc_mult=kc_mult,
                          vol_len=vol_len, vol_mult=vol_mult, atr_len=atr_len,
                          chandelier_mult=chandelier_mult, emit_stop_loss=emit_stop_loss)
        self.bb_len, self.bb_mult, self.kc_len, self.kc_mult = bb_len, bb_mult, kc_len, kc_mult
        self.vol_len, self.vol_mult = vol_len, vol_mult
        self.atr_len, self.chandelier_mult = atr_len, chandelier_mult
        self.emit_stop_loss = emit_stop_loss

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        bb = ta.bollinger(df["close"], self.bb_len, self.bb_mult)
        kc = ta.keltner(df, self.kc_len, self.kc_len, self.kc_mult)
        atr = ta.atr(df, self.atr_len)
        vol_avg = df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean()

        # Sikisma: Bollinger TAMAMEN Keltner'in icinde (oynaklik dusuk).
        squeeze_on = (bb["upper"] < kc["upper"]) & (bb["lower"] > kc["lower"])
        # Kirilim ani: bir onceki barda sikisma VARDI, bu barda YOK (acildi).
        squeeze_fired = squeeze_on.shift(1).fillna(False) & ~squeeze_on
        vol_confirm = df["volume"] >= self.vol_mult * vol_avg

        close_ = df["close"].to_numpy()
        high_, low_, atr_ = df["high"].to_numpy(), df["low"].to_numpy(), atr.to_numpy()
        # Yon: kirilim aninda kapanis, Bollinger orta bandinin hangi tarafinda.
        enter_long = (squeeze_fired & vol_confirm & (close_ > bb["mid"].to_numpy())).to_numpy()
        enter_short = (squeeze_fired & vol_confirm & (close_ < bb["mid"].to_numpy())).to_numpy()

        n = len(df)
        pos = 0
        highest_since = lowest_since = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)

        for i in range(n):
            if pos == 1:
                highest_since = max(highest_since, high_[i])
                trail = highest_since - self.chandelier_mult * atr_[i]
                sl_arr[i] = trail
                if close_[i] < trail:
                    pos = 0
            elif pos == -1:
                lowest_since = min(lowest_since, low_[i])
                trail = lowest_since + self.chandelier_mult * atr_[i]
                sl_arr[i] = trail
                if close_[i] > trail:
                    pos = 0

            if pos == 0 and not np.isnan(atr_[i]) and atr_[i] > 0:
                if enter_long[i]:
                    pos, highest_since = 1, high_[i]
                    sl_arr[i] = highest_since - self.chandelier_mult * atr_[i]
                elif enter_short[i]:
                    pos, lowest_since = -1, low_[i]
                    sl_arr[i] = lowest_since + self.chandelier_mult * atr_[i]
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index) if self.emit_stop_loss else None
        diag = pd.DataFrame({"bb_upper": bb["upper"], "bb_lower": bb["lower"],
                              "kc_upper": kc["upper"], "kc_lower": kc["lower"], "squeeze_on": squeeze_on})
        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss)
