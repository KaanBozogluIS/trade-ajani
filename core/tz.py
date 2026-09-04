"""Turkiye saati (Europe/Istanbul) gosterim yardimcisi.

ONEMLI: veri her zaman UTC olarak saklanir ve islenir (backtest, sinyal
mantigi hep UTC) - bu modul SADECE kullaniciya GOSTERIRKEN/bildirim
gonderirken cevrim icindir. Islem mantigina karistirilmamali.
"""

from __future__ import annotations

import pandas as pd

TZ_ISTANBUL = "Europe/Istanbul"


def to_istanbul(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.tz_convert(TZ_ISTANBUL)


def format_istanbul(ts, fmt: str = "%Y-%m-%d %H:%M") -> str:
    return to_istanbul(ts).strftime(fmt) + " (TR saati)"
