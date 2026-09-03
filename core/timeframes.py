"""Zaman dilimi yardimcilari.

Tek bir kanonik gosterim kullaniyoruz: 1m 5m 15m 30m 1h 4h 1d 1w
Saglayicilarin kendi lehcesine cevrim ilgili saglayicinin isi.
"""

from __future__ import annotations

import re

import pandas as pd

CANONICAL = ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w")

_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse(timeframe: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d+)([mhdw])", timeframe.strip().lower())
    if not m:
        raise ValueError(f"gecersiz zaman dilimi: {timeframe!r} (ornek: 15m, 4h, 1d)")
    return int(m.group(1)), m.group(2)


def to_seconds(timeframe: str) -> int:
    n, unit = parse(timeframe)
    return n * _UNIT_SECONDS[unit]


def to_timedelta(timeframe: str) -> pd.Timedelta:
    return pd.Timedelta(seconds=to_seconds(timeframe))


def bars_per_year(timeframe: str, market: str = "crypto") -> float:
    """Yillik mum sayisi - Sharpe gibi metrikleri yillandirmak icin.

    Kripto 7/24 islem gorur; hisse senedi piyasasi gormez. Bu ayrimi
    yapmazsak hisse stratejilerinin Sharpe'i sistematik olarak sisirilir.
    """
    seconds = to_seconds(timeframe)
    if market == "crypto":
        return 365 * 24 * 3600 / seconds
    # hisse: ~252 islem gunu, gunde 6.5 saat
    if seconds >= 86400:
        return 252 * 86400 / seconds
    return 252 * 6.5 * 3600 / seconds


def is_intraday(timeframe: str) -> bool:
    return to_seconds(timeframe) < 86400
