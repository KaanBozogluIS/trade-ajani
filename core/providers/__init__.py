"""Veri saglayicilari ve kayit defteri."""

from __future__ import annotations

from core.providers.base import (
    OHLCV_COLUMNS,
    DataProvider,
    DataProviderError,
    drop_unclosed_bar,
    empty_ohlcv,
    normalize,
)
from core.providers.binance import BinanceProvider
from core.providers.yahoo import YahooProvider

_REGISTRY: dict[str, DataProvider] = {}


def get_provider(name: str) -> DataProvider:
    """Saglayiciyi adiyla dondurur (tekil ornek).

    Adlar: 'binance' (spot), 'binance_futures', 'yahoo'.
    """
    name = name.lower()
    if name not in _REGISTRY:
        if name == "binance":
            _REGISTRY[name] = BinanceProvider(market="spot")
        elif name == "binance_futures":
            _REGISTRY[name] = BinanceProvider(market="futures")
        elif name == "yahoo":
            _REGISTRY[name] = YahooProvider()
        else:
            raise KeyError(f"bilinmeyen saglayici: {name!r}")
    return _REGISTRY[name]


__all__ = [
    "OHLCV_COLUMNS",
    "BinanceProvider",
    "DataProvider",
    "DataProviderError",
    "YahooProvider",
    "drop_unclosed_bar",
    "empty_ohlcv",
    "get_provider",
    "normalize",
]
