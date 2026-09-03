"""Binance spot ve USDT-M futures OHLCV saglayicisi.

Genel klines ucu anahtar istemez; sadece veri cekiyoruz, emir gondermiyoruz.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

from core.providers.base import DataProvider, DataProviderError, normalize

_SPOT_URL = "https://api.binance.com/api/v3/klines"
_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
_TICKER_24H_URL = "https://api.binance.com/api/v3/ticker/24hr"
_TICKER_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
_MAX_LIMIT = 1000  # Binance tek istekte en fazla bu kadar mum verir

# Kaldiracli/token urunleri (BTCUP, BTCDOWN, BTCBULL...) gercek spot coin
# degil - evrene ve canli fiyat listesine sizdirmamak icin filtreliyoruz.
_LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")

# kanonik -> Binance lehcesi (bu ikisi ayni ama esleme acik dursun)
_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
}


class BinanceProvider(DataProvider):
    name = "binance"
    timeframes = tuple(_TF_MAP)

    def __init__(self, market: str = "spot", timeout: int = 20, max_retries: int = 4):
        if market not in ("spot", "futures"):
            raise ValueError("market 'spot' veya 'futures' olmali")
        self.market = market
        self.url = _SPOT_URL if market == "spot" else _FUTURES_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()

    def __repr__(self) -> str:
        return f"BinanceProvider(market={self.market!r})"

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> pd.DataFrame:
        if not self.supports(timeframe):
            raise DataProviderError(f"{self.name} {timeframe} desteklemiyor")

        symbol = symbol.upper().replace("/", "")
        start_ms = int(pd.Timestamp(start).tz_localize("UTC").timestamp() * 1000) \
            if pd.Timestamp(start).tzinfo is None \
            else int(pd.Timestamp(start).timestamp() * 1000)
        end_ms = None
        if end is not None:
            ts_end = pd.Timestamp(end)
            ts_end = ts_end.tz_localize("UTC") if ts_end.tzinfo is None else ts_end
            end_ms = int(ts_end.timestamp() * 1000)

        rows: list[list] = []
        cursor = start_ms
        while True:
            params = {
                "symbol": symbol,
                "interval": _TF_MAP[timeframe],
                "startTime": cursor,
                "limit": _MAX_LIMIT,
            }
            if end_ms is not None:
                params["endTime"] = end_ms

            batch = self._get(params)
            if not batch:
                break
            rows.extend(batch)

            # Bir sonraki sayfa son mumun acilisindan 1ms sonrasi.
            next_cursor = int(batch[-1][0]) + 1
            if next_cursor <= cursor or len(batch) < _MAX_LIMIT:
                break
            cursor = next_cursor
            if end_ms is not None and cursor >= end_ms:
                break

        if not rows:
            return normalize(pd.DataFrame())

        df = pd.DataFrame(rows).iloc[:, :6]
        df.columns = ["ts", "open", "high", "low", "close", "volume"]
        df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
        return normalize(df.set_index("ts"))

    def _get(self, params: dict) -> list:
        """Ustel geri cekilmeli istek. 429/418 = hiz limiti, beklemek gerekir."""
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                r = self._session.get(self.url, params=params, timeout=self.timeout)
                if r.status_code in (418, 429) or r.status_code >= 500:
                    retry_after = float(r.headers.get("Retry-After", delay))
                    time.sleep(min(retry_after, 60))
                    delay *= 2
                    last_error = DataProviderError(f"HTTP {r.status_code}: {r.text[:200]}")
                    continue
                r.raise_for_status()
                return r.json()
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(delay)
                delay *= 2
        raise DataProviderError(f"Binance istegi {self.max_retries} denemede basarisiz: {last_error}")


def _request_json(url: str, params: dict | None = None, timeout: int = 20, max_retries: int = 4):
    delay = 1.0
    last_error: Exception | None = None
    for _ in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code in (418, 429) or r.status_code >= 500:
                time.sleep(min(float(r.headers.get("Retry-After", delay)), 60))
                delay *= 2
                last_error = DataProviderError(f"HTTP {r.status_code}: {r.text[:200]}")
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(delay)
            delay *= 2
    raise DataProviderError(f"Binance istegi basarisiz: {last_error}")


def _is_clean_symbol(base_asset: str) -> bool:
    return not any(base_asset.endswith(suf) for suf in _LEVERAGED_SUFFIXES)


def get_usdt_spot_symbols() -> list[str]:
    """Su an TRADING durumunda olan, kaldiracli olmayan tum USDT spot paritelerini dondurur."""
    info = _request_json(_EXCHANGE_INFO_URL)
    out = []
    for s in info["symbols"]:
        if (s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
                and s["isSpotTradingAllowed"] and _is_clean_symbol(s["baseAsset"])):
            out.append(s["symbol"])
    return sorted(out)


def get_24h_stats(symbols: list[str] | None = None) -> pd.DataFrame:
    """24 saatlik hacim/degisim istatistikleri.

    Evreni hacme gore siralamak (en likit altcoin'leri secmek) ve panelde
    canli bir ozet tablo gostermek icin kullanilir. Tum semboller icin tek
    istekte doner - Binance bunun icin `symbols` parametresi almiyor.
    """
    data = _request_json(_TICKER_24H_URL)
    df = pd.DataFrame(data)
    if df.empty:
        return df
    numeric_cols = ["lastPrice", "priceChangePercent", "quoteVolume", "volume", "highPrice", "lowPrice"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.rename(columns={
        "symbol": "symbol", "lastPrice": "price", "priceChangePercent": "change_24h_pct",
        "quoteVolume": "quote_volume_24h", "volume": "base_volume_24h",
        "highPrice": "high_24h", "lowPrice": "low_24h",
    })[["symbol", "price", "change_24h_pct", "quote_volume_24h", "base_volume_24h", "high_24h", "low_24h"]]
    if symbols is not None:
        df = df[df["symbol"].isin(symbols)]
    return df.reset_index(drop=True)


def get_live_prices(symbols: list[str] | None = None) -> pd.Series:
    """En hafif uctan anlik son islem fiyatlari (sembol -> fiyat)."""
    data = _request_json(_TICKER_PRICE_URL)
    df = pd.DataFrame(data)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if symbols is not None:
        df = df[df["symbol"].isin(symbols)]
    return df.set_index("symbol")["price"]
