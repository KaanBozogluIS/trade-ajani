"""Veri saglayici arayuzu.

Her saglayici ayni sozlesmeyi doldurur: UTC indeksli, artan sirali,
[open, high, low, close, volume] kolonlu bir DataFrame dondurur.
Boylece strateji ve backtest katmani hangi piyasada oldugunu bilmek
zorunda kalmaz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataProviderError(RuntimeError):
    """Saglayicidan veri cekilemedi."""


class DataProvider(ABC):
    #: config/config.yaml icinde ve sembol adreslerinde kullanilan kisa ad
    name: str = "base"

    #: bu saglayicinin destekledigi zaman dilimleri
    timeframes: tuple[str, ...] = ()

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: pd.Timestamp,
        end: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """[start, end] araligindaki mumları dondurur.

        Donen DataFrame: UTC DatetimeIndex (adi 'ts'), OHLCV_COLUMNS kolonlari,
        artan sirali, tekrarsiz. Son mum HENUZ KAPANMAMIS olabilir; kapali mum
        garantisi `drop_unclosed_bar` ile saglanir.
        """

    def supports(self, timeframe: str) -> bool:
        return timeframe in self.timeframes


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Ham saglayici ciktisini ortak sozlesmeye oturtur."""
    if df.empty:
        return empty_ohlcv()

    df = df.copy()
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise DataProviderError(f"eksik kolonlar: {missing}")

    df = df[OHLCV_COLUMNS].astype("float64")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataProviderError("indeks DatetimeIndex olmali")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df.index.name = "ts"

    df = df[~df.index.duplicated(keep="last")].sort_index()
    # Fiyati olmayan satir strateji icin gurultu; hacim 0 olabilir (tatil/dusuk likidite).
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


def empty_ohlcv() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz="UTC", name="ts")
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in OHLCV_COLUMNS}, index=idx)


def drop_unclosed_bar(df: pd.DataFrame, timeframe: str, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Henuz kapanmamis son mumu atar.

    Kapanmamis mum uzerinde sinyal uretmek, backtest ile canli sonuclarin
    ayrismasinin en yaygin sebebidir: mum kapanana kadar degerleri degisir.
    """
    if df.empty:
        return df
    from core.timeframes import to_timedelta

    now = pd.Timestamp.utcnow() if now is None else now
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    delta = to_timedelta(timeframe)
    last_open = df.index[-1]
    if last_open + delta > now:
        return df.iloc[:-1]
    return df
