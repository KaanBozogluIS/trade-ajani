"""Teknik gostergeler - saf pandas/numpy.

TA-Lib bilerek kullanilmadi: Windows'ta C derleme derdi cikariyor ve
buradaki her gostergenin kaynagini gormek, kara kutuya guvenmekten iyi.

ORTAK KURAL: her fonksiyon girdiyle ayni indeksli bir Series/DataFrame dondurur
ve GELECEGE BAKMAZ. t anindaki deger yalnizca <= t verisinden hesaplanir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Ortalamalar
# --------------------------------------------------------------------------
def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    # adjust=False -> ozyinelemeli EMA; canli hesapla birebir ayni sonucu verir.
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder yumusatmasi - RSI, ATR ve ADX'in kullandigi ortalama."""
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


# --------------------------------------------------------------------------
# Momentum
# --------------------------------------------------------------------------
def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain, avg_loss = rma(gain, length), rma(loss, length)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 -> hic dusus yok -> RSI 100
    return out.where(avg_loss != 0.0, 100.0).where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def roc(close: pd.Series, length: int = 10) -> pd.Series:
    """Degisim orani, yuzde."""
    return close.pct_change(length) * 100.0


# --------------------------------------------------------------------------
# Oynaklik
# --------------------------------------------------------------------------
def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return rma(true_range(df), length)


def bollinger(close: pd.Series, length: int = 20, mult: float = 2.0) -> pd.DataFrame:
    mid = sma(close, length)
    # ddof=0: nufus standart sapmasi, TradingView ile ayni.
    sd = close.rolling(length, min_periods=length).std(ddof=0)
    return pd.DataFrame({
        "mid": mid, "upper": mid + mult * sd, "lower": mid - mult * sd,
        "width": (2 * mult * sd) / mid,
    })


def realized_vol(close: pd.Series, length: int = 20) -> pd.Series:
    """Getirilerin kayan standart sapmasi - pozisyon buyuklugu icin."""
    return close.pct_change().rolling(length, min_periods=length).std(ddof=0)


# --------------------------------------------------------------------------
# Trend / kanal
# --------------------------------------------------------------------------
def donchian(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """Donchian kanali - SADECE gecmis mumlardan.

    shift(1) kritik: t anindaki mumun kendi high/low'unu kanala dahil edersek
    'kanali kirdi' sinyali her zaman kendiliginden dogru cikar. Klasik hata.
    """
    upper = df["high"].shift(1).rolling(length, min_periods=length).max()
    lower = df["low"].shift(1).rolling(length, min_periods=length).min()
    return pd.DataFrame({"upper": upper, "lower": lower, "mid": (upper + lower) / 2.0})


def keltner(df: pd.DataFrame, ema_len: int = 20, atr_len: int = 20, mult: float = 2.0) -> pd.DataFrame:
    """Keltner kanali - Bollinger'a benzer ama std yerine ATR kullanir, bu
    yuzden ani oynaklik sicramalarina Bollinger'dan daha farkli tepki verir.
    """
    mid = ema(df["close"], ema_len)
    band = mult * atr(df, atr_len)
    return pd.DataFrame({"mid": mid, "upper": mid + band, "lower": mid - band})


def supertrend(df: pd.DataFrame, length: int = 10, mult: float = 3.0) -> pd.DataFrame:
    """Supertrend - ATR bantlarinin fiyati "takip etmesiyle" olusan, her zaman
    long ya da short'ta olan (flat yok) klasik trend-takip gostergesi.

    Bant sadece fiyat lehine daralabilir (trend yonunde), aksi yonde
    genisleyemez - bu yuzden bir onceki barin degerine bagli, iteratif
    hesaplaniyor. trend: 1=yukselis (fiyat alt bandin ustunde), -1=dusus.
    """
    tr = true_range(df)
    a = rma(tr, length)
    hl2 = (df["high"] + df["low"]) / 2.0
    basic_upper = (hl2 + mult * a).to_numpy()
    basic_lower = (hl2 - mult * a).to_numpy()
    close = df["close"].to_numpy()

    n = len(df)
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    trend = np.zeros(n, dtype="int64")

    for i in range(n):
        if np.isnan(basic_upper[i]) or np.isnan(basic_lower[i]):
            continue  # warmup: ATR henuz yok, trend=0 (flat) kalir
        if trend[i - 1] == 0:
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            trend[i] = 1
            continue
        final_upper[i] = basic_upper[i] if (basic_upper[i] < final_upper[i - 1]
                                             or close[i - 1] > final_upper[i - 1]) else final_upper[i - 1]
        final_lower[i] = basic_lower[i] if (basic_lower[i] > final_lower[i - 1]
                                             or close[i - 1] < final_lower[i - 1]) else final_lower[i - 1]
        if trend[i - 1] == 1 and close[i] < final_lower[i]:
            trend[i] = -1
        elif trend[i - 1] == -1 and close[i] > final_upper[i]:
            trend[i] = 1
        else:
            trend[i] = trend[i - 1]

    line = np.where(trend == 1, final_lower, final_upper)
    return pd.DataFrame({"supertrend": line, "trend": trend}, index=df.index)


def vwap_session(df: pd.DataFrame) -> pd.DataFrame:
    """Gunluk (UTC takvim gunu) sifirlanan hacim-agirlikli ortalama fiyat -
    kurumsal islemlerin "adil deger" referansi. Kripto 7/24 islem gordugu
    icin gercek bir borsa seansi yok; literatur "senkron UTC gunu" kullanmayi
    onerir (bkz. modul disi arastirma notlari).

    `std` sutunu, tipik fiyatin VWAP'tan hacim-agirlikli sapmasidir - bant
    olusturmak icin (ornegin vwap +/- 2*std) kullanilir.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    day = df.index.floor("1D")
    pv = typical * df["volume"]

    cum_pv = pv.groupby(day).cumsum()
    cum_vol = df["volume"].groupby(day).cumsum()
    vwap = cum_pv / cum_vol.replace(0.0, np.nan)

    sq_diff = (typical - vwap) ** 2 * df["volume"]
    cum_sqdiff = sq_diff.groupby(day).cumsum()
    var = cum_sqdiff / cum_vol.replace(0.0, np.nan)
    std = np.sqrt(var.clip(lower=0.0))

    return pd.DataFrame({"vwap": vwap, "std": std})


def ichimoku(df: pd.DataFrame, tenkan_len: int = 9, kijun_len: int = 26,
             senkou_b_len: int = 52, displacement: int = 26) -> pd.DataFrame:
    """Ichimoku bulutu. Senkou (bulut) cizgileri, grafikte oldugu gibi
    `displacement` bar ILERI kaydirilir - boylece t anindaki "bulut" gercekte
    t-displacement anindaki veriden hesaplanir (ileriye bakma yok, sadece
    klasik Ichimoku'nun kendi tanimi geregi bulut "gecikmeli" gorunur).
    """
    tenkan = (df["high"].rolling(tenkan_len).max() + df["low"].rolling(tenkan_len).min()) / 2.0
    kijun = (df["high"].rolling(kijun_len).max() + df["low"].rolling(kijun_len).min()) / 2.0
    senkou_a = ((tenkan + kijun) / 2.0).shift(displacement)
    senkou_b = ((df["high"].rolling(senkou_b_len).max()
                 + df["low"].rolling(senkou_b_len).min()) / 2.0).shift(displacement)
    return pd.DataFrame({"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b})


def parabolic_sar(df: pd.DataFrame, af_start: float = 0.02, af_step: float = 0.02,
                   af_max: float = 0.2) -> pd.DataFrame:
    """Wilder'in Parabolic SAR'i - hep pozisyonda olan, hizlanan bir iz suren
    stop sistemi. Fiyat SAR'i gecince trend aninda tersine doner.
    """
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    sar = np.full(n, np.nan)
    trend = np.zeros(n, dtype="int64")
    if n == 0:
        return pd.DataFrame({"sar": sar, "trend": trend}, index=df.index)

    trend[0] = 1
    sar[0] = low[0]
    ep = high[0]
    af = af_start
    for i in range(1, n):
        prev_low = low[i - 2] if i >= 2 else low[i - 1]
        prev_high = high[i - 2] if i >= 2 else high[i - 1]
        if trend[i - 1] == 1:
            cur = sar[i - 1] + af * (ep - sar[i - 1])
            cur = min(cur, low[i - 1], prev_low)
            if low[i] < cur:
                trend[i], sar[i], ep, af = -1, ep, low[i], af_start
            else:
                trend[i], sar[i] = 1, cur
                if high[i] > ep:
                    ep, af = high[i], min(af + af_step, af_max)
        else:
            cur = sar[i - 1] + af * (ep - sar[i - 1])
            cur = max(cur, high[i - 1], prev_high)
            if high[i] > cur:
                trend[i], sar[i], ep, af = 1, ep, high[i], af_start
            else:
                trend[i], sar[i] = -1, cur
                if low[i] < ep:
                    ep, af = low[i], min(af + af_step, af_max)
    return pd.DataFrame({"sar": sar, "trend": trend}, index=df.index)


def adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Yon hareket endeksi. ADX > 25 kabaca 'trend var' demektir."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)

    tr = rma(true_range(df), length)
    plus_di = 100.0 * rma(plus_dm, length) / tr.replace(0.0, np.nan)
    minus_di = 100.0 * rma(minus_dm, length) / tr.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return pd.DataFrame({"adx": rma(dx, length), "plus_di": plus_di, "minus_di": minus_di})


def slope(series: pd.Series, length: int = 20) -> pd.Series:
    """Kayan dogrusal regresyon egimi, mum basina yuzde olarak."""
    x = np.arange(length, dtype="float64")
    x_centered = x - x.mean()
    denom = (x_centered ** 2).sum()

    def _fit(window: np.ndarray) -> float:
        return float((x_centered * (window - window.mean())).sum() / denom)

    raw = series.rolling(length, min_periods=length).apply(_fit, raw=True)
    return raw / series * 100.0


# --------------------------------------------------------------------------
# Yardimci
# --------------------------------------------------------------------------
def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """a, b'yi asagidan yukari kesti mi (bu mumda)."""
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


def zscore(series: pd.Series, length: int = 20) -> pd.Series:
    mean = series.rolling(length, min_periods=length).mean()
    sd = series.rolling(length, min_periods=length).std(ddof=0)
    return (series - mean) / sd.replace(0.0, np.nan)


def percent_rank(series: pd.Series, length: int = 100) -> pd.Series:
    """Son deger, gecmis `length` mum icinde hangi yuzdelik dilimde (0-100)."""
    return series.rolling(length, min_periods=length).apply(
        lambda w: float((w[:-1] < w[-1]).mean() * 100.0), raw=True
    )
