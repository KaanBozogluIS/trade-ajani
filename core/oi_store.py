"""Acik Pozisyon (OI) / long-short orani icin KALICI yerel onbellek.

`data/raw/` (core/datastore.py) ile FARKI: OHLCV verisi Binance'te
SINIRSIZ geriye gidiyor, o yuzden data/raw/ .gitignore'da - herhangi bir
ortam istedigi an tam gecmisi yeniden cekebilir. OI/long-short verisi ise
Binance'te SADECE SON ~30 GUN saklaniyor (core/providers/binance.py'deki
get_open_interest_hist() ust bilgisi) - bu yuzden bu dosyalar
data/oi/ altinda, .gitignore'da DEGIL, GitHub Actions'in her calistirmada
COMMIT ETTIGI kalici bir arsiv (tipki data/state/last_signal.json gibi).
Boylece Binance'in kendi 30-gunluk penceresi kayıp gitse bile, bizim
biriktirdigimiz gecmis KALICI olarak buyumeye devam eder.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.providers import binance

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "oi"


def _path(kind: str, symbol: str, period: str) -> Path:
    safe_symbol = symbol.upper().replace("/", "_")
    return DATA_ROOT / "binance" / kind / safe_symbol / f"{period}.parquet"


def _load(kind: str, symbol: str, period: str) -> pd.DataFrame:
    path = _path(kind, symbol, period)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df.sort_index()


def _save(df: pd.DataFrame, kind: str, symbol: str, period: str) -> None:
    path = _path(kind, symbol, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy")


def update_open_interest(symbol: str, period: str = "1h") -> pd.DataFrame:
    """Onbellegi Binance'in verdigi (en fazla ~30 gunluk) en son veriyle
    birlestirir - eskisi SILINMEZ, sadece yeni satirlar EKLENIR (tekrarlar
    son gelen kazanir). Boylece Binance'in penceresi kaysa bile bizim
    depomuz surekli buyur."""
    cached = _load("open_interest", symbol, period)
    fresh = binance.get_open_interest_hist(symbol, period=period, limit=500)
    if cached.empty:
        merged = fresh
    elif fresh.empty:
        merged = cached
    else:
        merged = pd.concat([cached, fresh])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    if not merged.empty:
        _save(merged, "open_interest", symbol, period)
    return merged


def update_long_short_ratio(symbol: str, period: str = "1h") -> pd.DataFrame:
    cached = _load("long_short", symbol, period)
    fresh = binance.get_long_short_ratio_hist(symbol, period=period, limit=500)
    if cached.empty:
        merged = fresh
    elif fresh.empty:
        merged = cached
    else:
        merged = pd.concat([cached, fresh])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    if not merged.empty:
        _save(merged, "long_short", symbol, period)
    return merged


def load_open_interest(symbol: str, period: str = "1h") -> pd.DataFrame:
    """Sadece onbellekten okur (aglamaz) - arastirma/backtest icin."""
    return _load("open_interest", symbol, period)


def load_long_short_ratio(symbol: str, period: str = "1h") -> pd.DataFrame:
    return _load("long_short", symbol, period)


def describe_cache() -> pd.DataFrame:
    """Onbellekte ne var, ne kadar gecmis birikmis - envanter tablosu."""
    rows = []
    for path in sorted(DATA_ROOT.glob("*/*/*/*.parquet")):
        kind, symbol = path.parent.parent.name, path.parent.name
        try:
            df = pd.read_parquet(path)
        except Exception as exc:
            rows.append({"kind": kind, "symbol": symbol, "period": path.stem,
                         "bars": 0, "start": None, "end": None, "note": f"HATA: {exc}"})
            continue
        rows.append({
            "kind": kind, "symbol": symbol, "period": path.stem, "bars": len(df),
            "start": df.index.min(), "end": df.index.max(),
        })
    return pd.DataFrame(rows)
