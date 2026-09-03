"""Yerel OHLCV onbellegi (parquet).

Amac: her backtestte agi dovmemek ve internet olmadan da calisabilmek.
Dosya duzeni:  data/raw/<saglayici>/<SEMBOL>/<zaman_dilimi>.parquet

Guncelleme artimlidir: elde olanin son mumundan itibaren ceker, birlestirir,
tekrarlari son gelen kazanacak sekilde temizler.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.providers import OHLCV_COLUMNS, drop_unclosed_bar, empty_ohlcv, get_provider
from core.timeframes import to_timedelta

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"


def _path(provider: str, symbol: str, timeframe: str) -> Path:
    safe_symbol = symbol.upper().replace("/", "_").replace("\\", "_")
    return DATA_ROOT / provider.lower() / safe_symbol / f"{timeframe}.parquet"


def load(provider: str, symbol: str, timeframe: str) -> pd.DataFrame:
    """Onbellekten okur; yoksa bos DataFrame."""
    path = _path(provider, symbol, timeframe)
    if not path.exists():
        return empty_ohlcv()
    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df.sort_index()


def save(df: pd.DataFrame, provider: str, symbol: str, timeframe: str) -> Path:
    path = _path(provider, symbol, timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy")
    return path


def update(
    provider: str,
    symbol: str,
    timeframe: str,
    start: str | pd.Timestamp = "2019-01-01",
    end: str | pd.Timestamp | None = None,
    force_full: bool = False,
) -> pd.DataFrame:
    """Onbellegi tazeler ve tam seriyi dondurur."""
    cached = empty_ohlcv() if force_full else load(provider, symbol, timeframe)

    if cached.empty:
        fetch_from = pd.Timestamp(start)
    else:
        # Son mumu yeniden cekiyoruz: onbellege kapanmamis halde girmis olabilir.
        fetch_from = cached.index[-1]

    fresh = get_provider(provider).fetch_ohlcv(symbol, timeframe, fetch_from, end)

    if cached.empty:
        merged = fresh
    elif fresh.empty:
        merged = cached
    else:
        merged = pd.concat([cached, fresh])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()

    merged = merged[OHLCV_COLUMNS] if not merged.empty else merged
    if not merged.empty:
        save(merged, provider, symbol, timeframe)
    return merged


def get(
    provider: str,
    symbol: str,
    timeframe: str,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    refresh: bool = False,
    closed_only: bool = True,
) -> pd.DataFrame:
    """Backtest ve arastirma icin ana giris noktasi.

    refresh=False ise sadece onbellekten okur (hizli, tekrarlanabilir).
    closed_only=True kapanmamis son mumu atar - ileriye bakma kacagini onler.
    """
    df = update(provider, symbol, timeframe, start=start or "2019-01-01", end=end) if refresh \
        else load(provider, symbol, timeframe)

    if df.empty:
        return df
    if closed_only:
        df = drop_unclosed_bar(df, timeframe)
    if start is not None:
        df = df[df.index >= _as_utc(start)]
    if end is not None:
        df = df[df.index <= _as_utc(end)]
    return df


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Daha kucuk mumlari daha buyugune toplar (or. 1h -> 4h).

    Yahoo'da 4h yok; 1h cekip burada toplamak dogru yol.
    """
    if df.empty:
        return df
    rule = to_timedelta(timeframe)
    out = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna(subset=["open", "high", "low", "close"])


def describe_cache() -> pd.DataFrame:
    """Onbellekte ne var? Envanter tablosu."""
    rows = []
    for path in sorted(DATA_ROOT.glob("*/*/*.parquet")):
        provider, symbol = path.parent.parent.name, path.parent.name
        try:
            df = pd.read_parquet(path)
        except Exception as exc:  # bozuk dosyayi gormezden gelme, raporla
            rows.append({"provider": provider, "symbol": symbol, "tf": path.stem,
                         "bars": 0, "start": None, "end": None, "note": f"HATA: {exc}"})
            continue
        rows.append({
            "provider": provider, "symbol": symbol, "tf": path.stem, "bars": len(df),
            "start": df.index.min(), "end": df.index.max(),
            "note": f"{path.stat().st_size / 1024:.0f} KB",
        })
    return pd.DataFrame(rows)


def _as_utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
