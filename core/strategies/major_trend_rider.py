"""MAJOR Stratejisi - buyuk/likit coinler icin sifirdan tasarlanmis.

Mantik: ALTCOIN Stratejisi'nin (breakout_retest_recovery) BTC/ETH gibi
coinlerde neden calismadigini gordukten sonra ("Neden calismadigini
anladik" bkz. brr_hunt_sonuclari.csv) tersinden dusunduk - kucuk/orta
cap altcoinler TEKNIK SEVIYELERE saygili, "kirilim-geri cekilme-toparlanma"
gibi temiz paternler cizer. BUYUK coinler ise derin likit, kurumsal
agirlikli - BUYUK, UZUN SOLUKLU trendlerle hareket eder ve genelde
sabit bir kar hedefine ULASMADAN cok daha fazla gider (bkz. ZECUSDT'nin
tum donem +binlerce % hareketi). Sabit bir take-profit koymak bu tur
trendlerde parayi MASADA BIRAKMAK demektir.

Bu yuzden BASKA bir cikis felsefesi kurduk - "candan" (chandelier) takip
eden stop: pozisyon acildiktan sonraki EN YUKSEK (long) / EN DUSUK (short)
fiyatin ATR kati kadar gerisinde bir stop tutulur, sadece LEHTE hareket
eder (sikismaz), fiyat oraya donerse cikilir. Boylece trend surdukce kar
kilitlenir ama pozisyon HICBIR SABIT HEDEFLE erken kapanmaz - trend ne
kadar uzun surerse, o kadar tasinir.

Giris: N-bar kirilim (Donchian tarzi, kendi barini haric tutar) + ADX
(gercek trend var mi) + hacim orani (katilim teyidi - factor_lab.py'de
BIZIM olcup dogruladigimiz iki faktor) + uzun EMA ile ana trend yonu
teyidi. Hicbir StrategyResult.stop_loss/take_profit DONDURMEZ (bilerek -
cikis TAMAMEN sinyal/candan mantigiyla, sabit bir bracket seviyesi degil)
- diger "buyuk trend" stratejilerimiz (ema_cross, supertrend, ichimoku) gibi
saf sinyal tabanli calisir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import indicators as ta
from core.strategy import Strategy, StrategyResult


class MajorTrendRider(Strategy):
    name = "major_stratejisi"

    def __init__(self, breakout_len: int = 20, adx_len: int = 14, adx_min: float = 25.0,
                 vol_len: int = 20, vol_mult: float = 1.3, ema_trend_len: int = 100,
                 atr_len: int = 14, chandelier_mult: float = 3.0, emit_stop_loss: bool = False):
        super().__init__(breakout_len=breakout_len, adx_len=adx_len, adx_min=adx_min,
                          vol_len=vol_len, vol_mult=vol_mult, ema_trend_len=ema_trend_len,
                          atr_len=atr_len, chandelier_mult=chandelier_mult, emit_stop_loss=emit_stop_loss)
        self.breakout_len, self.adx_len, self.adx_min = breakout_len, adx_len, adx_min
        self.vol_len, self.vol_mult, self.ema_trend_len = vol_len, vol_mult, ema_trend_len
        self.atr_len, self.chandelier_mult = atr_len, chandelier_mult
        # ONEMLI IKI MOD:
        #  False (varsayilan): stop_loss=None dondurur - motor SADECE sinyal
        #    (kapanis fiyatina gore) ile pozisyon acip kapatir. Tum
        #    dogrulanan sonuclar (research/scan.py, panel) bu modu kullanir.
        #  True: HER BARDA guncel chandelier seviyesini stop_loss olarak da
        #    dondurur - core/backtest.py'de trailing_stop=True ile birlikte
        #    kaldiracli pozisyon boyutlandirma icin GEREKLI. AMA: motorun
        #    bracket kontrolu bar-ICI (dusuk/yuksek) fiyata bakar, bu modun
        #    kendi ic sinyali ise KAPANIS fiyatina bakar - ikisi FARKLI
        #    (bar-ici versiyonu daha erken/sik tetiklenir, ama GERCEK bir
        #    trailing-stop emrinin canli piyasada davranisina daha yakindir -
        #    gercek bir stop emri kapanisi beklemez). Bu yuzden True modunda
        #    sonuclar False'tan FARKLI (genelde daha zayif) cikar - bu bir
        #    hata degil, iki farkli varsayimin (kapanista karar vs. gercek
        #    zamanli stop emri) dogal sonucu.
        self.emit_stop_loss = emit_stop_loss

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        # shift(1): kendi barinin yuksek/dusugunu kirilim seviyesine katmiyoruz
        # (Donchian icin daha once yakaladigimiz klasik ileriye-bakma hatasi).
        upper = df["high"].shift(1).rolling(self.breakout_len, min_periods=self.breakout_len).max()
        lower = df["low"].shift(1).rolling(self.breakout_len, min_periods=self.breakout_len).min()
        adx = ta.adx(df, self.adx_len)["adx"]
        vol_ratio = df["volume"] / df["volume"].rolling(self.vol_len, min_periods=self.vol_len).mean()
        ema_trend = ta.ema(df["close"], self.ema_trend_len)
        atr = ta.atr(df, self.atr_len)

        trending = adx >= self.adx_min
        vol_confirm = vol_ratio >= self.vol_mult
        enter_long = (df["close"] > upper) & trending & vol_confirm & (df["close"] > ema_trend)
        enter_short = (df["close"] < lower) & trending & vol_confirm & (df["close"] < ema_trend)

        high_, low_, close_, atr_ = (df["high"].to_numpy(), df["low"].to_numpy(),
                                      df["close"].to_numpy(), atr.to_numpy())
        el, es = enter_long.to_numpy(), enter_short.to_numpy()

        n = len(df)
        pos = 0
        highest_since = lowest_since = None
        sig_values = np.zeros(n, dtype="int64")
        # HER BARDA guncel "iz suren" (chandelier) stop seviyesi - sadece
        # giris barinda degil. core/backtest.py'nin trailing_stop=True modu
        # bunu her bar okuyup lehte hareket ettikce gunceller (bkz. o
        # dosyadaki aciklama). trailing_stop=False ile cagrilirsa motor
        # SADECE giris barindaki degeri kilitler - bu durumda strateji hala
        # DOGRU calisir (sinyal zaten kendi ic mantigiyla cikisi belirliyor),
        # yalnizca kaldiracli boyutlandirma ilk stop'a gore sabitlenmis olur.
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
                if el[i]:
                    pos, highest_since = 1, high_[i]
                    sl_arr[i] = highest_since - self.chandelier_mult * atr_[i]
                elif es[i]:
                    pos, lowest_since = -1, low_[i]
                    sl_arr[i] = lowest_since + self.chandelier_mult * atr_[i]
            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index) if self.emit_stop_loss else None
        diag = pd.DataFrame({"donchian_upper": upper, "donchian_lower": lower,
                              "adx": adx, "vol_ratio": vol_ratio, "ema_trend": ema_trend})
        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss)
