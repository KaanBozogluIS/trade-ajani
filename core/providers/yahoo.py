"""Yahoo Finance saglayicisi - ABD hisseleri ve BIST.

BIST sembolleri '.IS' son ekiyle gecer: THYAO.IS, ASELS.IS, GARAN.IS.
Fiyatlar TL cinsindendir.

ONEMLI KISITLAR (Yahoo tarafindan dayatiliyor, bizim secimimiz degil):
  * 1m  -> son 7 gun
  * <1d -> son 60 gun
  * 1d/1w -> tam gecmis
Bu yuzden intraday stratejilerin gecmisi kisa. Kripto tarafinda boyle bir
sinir yok; intraday arastirmayi once Binance uzerinde yapmak daha saglikli.
"""

from __future__ import annotations

import pandas as pd

from core.providers.base import DataProvider, DataProviderError, normalize

_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "1d": "1d", "1w": "1wk",
}

# gun cinsinden azami geriye bakis
_LOOKBACK_LIMIT_DAYS = {"1m": 7, "5m": 60, "15m": 60, "30m": 60, "1h": 60}


class YahooProvider(DataProvider):
    name = "yahoo"
    timeframes = tuple(_TF_MAP)

    def __init__(self, auto_adjust: bool = True):
        # auto_adjust=True: bolunme ve temettu duzeltmesi. Hisse backtestinde
        # sart, yoksa bolunme gunlerinde sahte %50 dususler cikar.
        self.auto_adjust = auto_adjust

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> pd.DataFrame:
        if not self.supports(timeframe):
            raise DataProviderError(
                f"{self.name} {timeframe} desteklemiyor (4h Yahoo'da yok - 1h cekip yeniden orneklemek gerekir)"
            )
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise DataProviderError("yfinance kurulu degil: pip install yfinance") from exc

        start_ts = _as_utc(start)
        end_ts = _as_utc(end) if end is not None else pd.Timestamp.now(tz="UTC")

        limit_days = _LOOKBACK_LIMIT_DAYS.get(timeframe)
        if limit_days is not None:
            earliest = end_ts - pd.Timedelta(days=limit_days - 1)
            if start_ts < earliest:
                start_ts = earliest

        raw = yf.download(
            tickers=symbol,
            interval=_TF_MAP[timeframe],
            start=start_ts.tz_convert(None),
            end=end_ts.tz_convert(None),
            auto_adjust=self.auto_adjust,
            progress=False,
            threads=False,
        )
        if raw is None or raw.empty:
            return normalize(pd.DataFrame())

        # yfinance tek sembolde de MultiIndex kolon dondurebiliyor.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        raw = raw.rename(columns=str.lower)
        return normalize(raw)


def _as_utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
