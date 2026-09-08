"""AKTIF strateji kutuphanesi - sadece IS/OOS dogrulanmis, watchlist'te
kullanilan stratejiler.

Bu oturumda 24 strateji denendi, IS/OOS dogrulamali genis taramalardan
(bkz. reports/*_hunt_sonuclari.csv) sadece bunlar gercekten tutarli edge
gosterdi. Digerleri core/strategies/archive/ klasorune tasindi (SILINMEDI -
arastirma degeri korunuyor, gerekirse geri REGISTRY'ye eklenebilir).

Hangi stratejinin hangi coin'de calistigi icin dashboard/pages/5_Strateji_Rehberi.py'ye bak.
"""

from __future__ import annotations

from core.strategies.breakout_retest_recovery import BreakoutRetestRecovery
from core.strategies.ict_swing import IctSwing
from core.strategies.ma_cross import EmaCross
from core.strategies.major_trend_rider import MajorTrendRider
from core.strategies.reversal_pullback import ReversalPullback
from core.strategies.volume_absorption import VolumeAbsorption

REGISTRY = {
    "ema_cross": EmaCross,
    "ict_swing": IctSwing,
    "altcoin_stratejisi": BreakoutRetestRecovery,
    "major_stratejisi": MajorTrendRider,
    "tepe_dip_stratejisi": ReversalPullback,
    "hacim_uyumsuzlugu_stratejisi": VolumeAbsorption,
}

__all__ = ["REGISTRY", "EmaCross", "IctSwing", "BreakoutRetestRecovery", "MajorTrendRider",
           "ReversalPullback", "VolumeAbsorption"]
