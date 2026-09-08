"""Kaldirac/pozisyon boyutu onerisi - core/backtest.py'nin risk-bazli
boyutlandirma formuluyle AYNI (bkz. o dosyanin ust bilgisi): her islemde
sermayenin sadece kucuk bir yuzdesi (risk_per_trade_pct) riske atilir,
kaldirac SADECE stop mesafesine gore pozisyon buyuklugunu ayarlamak icin
kullanilir - "sermayenin tamamini N kat kaldiracla ac" DEGIL.

Canli Telegram sinyallerinde "nereden gireyim, stopum nerede, kac kat
kaldirac kullanayim" sorusuna somut bir sayi vermek icin kullanilir.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizeSuggestion:
    stop_distance_pct: float   # giris ile stop arasi mesafe, yuzde
    suggested_leverage: float  # onerilen kaldirac (pozisyon buyuklugu carpani)
    risk_per_trade_pct: float  # bu onerinin varsaydigi islem-basi risk yuzdesi


def suggest_leverage(entry_price: float, stop_price: float, risk_per_trade_pct: float = 1.5,
                      max_leverage: float = 10.0) -> PositionSizeSuggestion | None:
    """entry/stop fiyatlarindan, core/backtest.py'deki AYNI formulle bir
    kaldirac onerisi hesaplar: stop ne kadar DAR ise o kadar YUKSEK kaldirac
    (riski sabit tutmak icin daha buyuk pozisyon gerekir), stop ne kadar
    GENIS ise o kadar DUSUK kaldirac onerilir - max_leverage'i asmaz."""
    if entry_price <= 0 or stop_price is None:
        return None
    stop_dist_pct = abs(entry_price - stop_price) / entry_price
    if stop_dist_pct <= 1e-9:
        return None
    leverage = min(max_leverage, (risk_per_trade_pct / 100.0) / stop_dist_pct)
    return PositionSizeSuggestion(
        stop_distance_pct=stop_dist_pct * 100.0,
        suggested_leverage=leverage,
        risk_per_trade_pct=risk_per_trade_pct,
    )
