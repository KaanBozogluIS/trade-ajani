"""Log-Regresyon Koridoru Stratejisi - kullanicinin TradingView'de gordugu
"Log-Regression Probability Corridor" indikatorunun NEDENSEL (lookahead'siz,
gercekten islenebilir) versiyonu.

ORIJINAL INDIKATORLE FARKI (KRITIK): TradingView versiyonu `barstate.islast`
ile SADECE en son barda, o anki son N barin verisiyle BIR KEZ regresyon
uyduruyor, sonra bu tek egriyi TUM GECMISIN uzerine cizip gosteriyor. Bu,
gecmisteki her nokta icin GELECEGI BILEREK cizilmis bir cizgi demek - o
tarihte gercekten o egri elde YOKTU, cunku henuz sonraki barlar gerceklesmemisti.
Grafikte "dogru cagirdi" gibi gorunen her nokta bu yuzden supheli.

Burada regresyon HER BARDA, o bara kadarki (yalnizca <=t) `window` genislikli
kayan pencereyle YENIDEN hesaplaniyor - gercek zamanli, canli piyasada
hesaplanabilecek TEK versiyon budur. Kapali-form OLS toplam formulleriyle
(rolling sum) vektorize edildi - pencere basina O(1), toplamda O(n).

FIKIR (mean-reversion): fiyat (log olcekte) uzun-vadeli trend cizgisinden
COK sapmissa (z-skor >= esik), "adil deger"e (fitted trend) donus beklenir.
Giris esigi, hedef ve stop hepsi ORIJINAL indikatordeki gibi std-sapma (σ)
cinsinden tanimlanir - "Hedef" = adil deger, "Stop" = daha uzak bir σ.

NEDEN ARSIVLENDI (2026-09-08, basarisiz - REGISTRY'YE EKLENMEDI):
Lookahead duzeltmesinden SONRA bile 108 sembol IS/OOS taramasinda (bkz.
research/log_regresyon_hunt.py, reports/log_regresyon_hunt_sonuclari.csv)
sonuclar ISTATISTIKSEL OLARAK GUVENILMEZ cikti - kar faktoru "inf",
"%100 kazanma orani" gibi degerler AYNI satirda "-%100 maxDD" (TAM IFLAS)
ile birlikte gorunuyordu. Somut dogrulama: XRPUSDT 1h IS doneminde equity
gercekten SIFIRA (0.0'a) kadar dustu (tam iflas), ama backtest.py'nin
sinirsiz bilesik buyume varsayimi (capital = capital*(1+getiri), gercek
hesap likidasyonu YOK) matematiksel olarak bunu "10^17% getiri"ye
"toparlatabildi" - sifira yakin bir sermayeden sonraki tek bir buyuk
kazancin ORANSAL olarak devasa gorunmesi yuzunden. GERCEK bir hesap boyle
bir noktada COKTAN likide edilmis olurdu - bu "toparlanma" saf matematiksel
bir illuzyon, gercek bir edge degil. Ders: kar faktoru/kazanma orani TEK
BASINA yeterli degil, DUSUK EKUITI/YAKLASIK-SIFIR noktalari da ayrica
kontrol edilmeli (bkz. [[strateji-arastirma-metodolojisi]] guncellemesi).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy import Strategy, StrategyResult


def _rolling_regression(y: pd.Series, window: int) -> tuple[pd.Series, pd.Series]:
    """log(fiyat) serisinin bar-indeksine (x) gore kayan-pencereli OLS'i.
    HER t icin sadece [t-window+1, t] barlari kullanilir (nedensel).
    Dondurur: (t barindaki tahmini/adil deger, artik std sapmasi)."""
    x = pd.Series(np.arange(len(y), dtype="float64"), index=y.index)
    n = float(window)
    sum_x = x.rolling(window).sum()
    sum_y = y.rolling(window).sum()
    sum_xy = (x * y).rolling(window).sum()
    sum_x2 = (x * x).rolling(window).sum()
    sum_y2 = (y * y).rolling(window).sum()
    mean_x, mean_y = sum_x / n, sum_y / n
    sxx = sum_x2 - sum_x * sum_x / n
    sxy = sum_xy - sum_x * sum_y / n
    syy = sum_y2 - sum_y * sum_y / n
    slope = sxy / sxx.replace(0.0, np.nan)
    intercept = mean_y - slope * mean_x
    fitted = slope * x + intercept
    sse = (syy - slope * sxy).clip(lower=0.0)
    stderr = np.sqrt(sse / n)
    return fitted, stderr


class LogRegressionCorridor(Strategy):
    name = "regresyon_koridoru_stratejisi"

    def __init__(self, window: int = 200, entry_z: float = 2.0, target_z: float = 0.0,
                 stop_z: float = 3.0):
        super().__init__(window=window, entry_z=entry_z, target_z=target_z, stop_z=stop_z)
        self.window, self.entry_z, self.target_z, self.stop_z = window, entry_z, target_z, stop_z

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        log_close = np.log(df["close"])
        fitted, stderr = _rolling_regression(log_close, self.window)
        fitted_arr, stderr_arr = fitted.to_numpy(), stderr.to_numpy()
        log_close_arr = log_close.to_numpy()
        # z-skor: fiyatin (log olcekte) o barin regresyon cizgisinden kac
        # std-sapma uzakta oldugu - pozitif = trendin USTUNDE (asiri pahali
        # gorunuyor), negatif = ALTINDA (asiri ucuz gorunuyor).
        z = np.where(stderr_arr > 0, (log_close_arr - fitted_arr) / stderr_arr, np.nan)

        high_, low_, close_ = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        n = len(df)

        def _price_at_z(i: int, zval: float) -> float:
            return float(np.exp(fitted_arr[i] + zval * stderr_arr[i]))

        pos = 0
        active_sl = active_tp = None
        sig_values = np.zeros(n, dtype="int64")
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)

        for i in range(n):
            if pos != 0:
                sl_t = (pos > 0 and low_[i] <= active_sl) or (pos < 0 and high_[i] >= active_sl)
                tp_t = (pos > 0 and high_[i] >= active_tp) or (pos < 0 and low_[i] <= active_tp)
                # ONEMLI DUZELTME: sabit (giriste kilitlenen) TP fiyati tek
                # basina YETERSIZ - eger giriste stderr anormal genisse (ya
                # da sonraki barlarda trend GUCLU sekilde devam ederse) bu
                # fiyat hicbir zaman gelmeyebilir ve pozisyon YILLARCA acik
                # kalir (ilk testte 10^14% gibi anlamsiz sonuclar verdi -
                # tek bir "sonsuz suren" islemin domine ettigi kirilgan bir
                # kenar, gercek bir edge degil). Bu yuzden HER BARDA yeniden
                # hesaplanan GUNCEL z-skor da bagimsiz bir cikis sinyali:
                # fiyat (o barin KENDI regresyonuna gore) adil degere/hedefe
                # DONDUYSE, sabit fiyat bandi tetiklenmemis olsa bile cikilir.
                z_exit = (pos > 0 and not np.isnan(z[i]) and z[i] >= self.target_z) or \
                         (pos < 0 and not np.isnan(z[i]) and z[i] <= self.target_z)
                if sl_t or tp_t or z_exit:
                    pos = 0
                    active_sl = active_tp = None

            if pos == 0 and not np.isnan(z[i]):
                if z[i] <= -self.entry_z:
                    pos = 1
                    active_sl = _price_at_z(i, -self.stop_z)
                    active_tp = _price_at_z(i, self.target_z)
                    sl_arr[i], tp_arr[i] = active_sl, active_tp
                elif z[i] >= self.entry_z:
                    pos = -1
                    active_sl = _price_at_z(i, self.stop_z)
                    active_tp = _price_at_z(i, self.target_z)
                    sl_arr[i], tp_arr[i] = active_sl, active_tp

            sig_values[i] = pos

        signal = pd.Series(sig_values, index=df.index, dtype="int64")
        stop_loss = pd.Series(sl_arr, index=df.index)
        take_profit = pd.Series(tp_arr, index=df.index)
        diag = pd.DataFrame({"fitted_fair_value": np.exp(fitted_arr), "z_score": z}, index=df.index)
        return StrategyResult(signal=signal, diagnostics=diag, stop_loss=stop_loss, take_profit=take_profit)
