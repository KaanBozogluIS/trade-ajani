"""Backtest performans metrikleri.

Tek bir sayiya (ornegin toplam getiri) guvenmek yanlis stratejiyi
secmenin en kisa yolu - bu yuzden bir DUZINE metrigi birlikte hesaplayip
rapor ediyoruz: getiri, risk-ayarli getiri, drawdown, islem istatistikleri.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.backtest import BacktestResult
from core.timeframes import bars_per_year


def max_drawdown(equity: pd.Series) -> tuple[float, pd.Timedelta]:
    """Dondurur: (en derin dususun yuzdesi (negatif), en uzun toparlanma suresi)."""
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    depth = float(drawdown.min()) if len(drawdown) else 0.0

    underwater = drawdown < 0
    longest = pd.Timedelta(0)
    if underwater.any():
        start = None
        for t, is_under in underwater.items():
            if is_under and start is None:
                start = t
            elif not is_under and start is not None:
                longest = max(longest, t - start)
                start = None
        if start is not None:
            longest = max(longest, equity.index[-1] - start)
    return depth, longest


def sharpe(returns: pd.Series, timeframe: str, market: str = "crypto", rf: float = 0.0) -> float:
    r = returns.dropna()
    if r.std(ddof=0) == 0 or len(r) < 2:
        return 0.0
    periods = bars_per_year(timeframe, market)
    excess = r - rf / periods
    return float(excess.mean() / excess.std(ddof=0) * np.sqrt(periods))


def sortino(returns: pd.Series, timeframe: str, market: str = "crypto", rf: float = 0.0) -> float:
    r = returns.dropna()
    downside = r[r < 0]
    if downside.std(ddof=0) == 0 or len(r) < 2:
        return 0.0
    periods = bars_per_year(timeframe, market)
    excess = r - rf / periods
    return float(excess.mean() / downside.std(ddof=0) * np.sqrt(periods))


def summarize(result: BacktestResult, timeframe: str, market: str = "crypto") -> dict:
    equity, trades = result.equity, result.trades
    if len(equity) < 2:
        return {"error": "yetersiz veri"}

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.25 * 86400)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0) if years > 0 else 0.0
    dd, dd_duration = max_drawdown(equity)

    n_trades = len(trades)
    win_rate = float((trades["pnl"] > 0).mean()) if n_trades else 0.0
    gross_win = float(trades.loc[trades["pnl"] > 0, "pnl"].sum()) if n_trades else 0.0
    gross_loss = float(-trades.loc[trades["pnl"] < 0, "pnl"].sum()) if n_trades else 0.0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    avg_trade_pct = float(trades["return_pct"].mean()) if n_trades else 0.0

    time_in_market = float((result.position != 0).mean())

    return {
        "toplam_getiri_%": round(total_return * 100, 2),
        "cagr_%": round(cagr * 100, 2),
        "sharpe": round(sharpe(result.returns, timeframe, market), 2),
        "sortino": round(sortino(result.returns, timeframe, market), 2),
        "max_drawdown_%": round(dd * 100, 2),
        "max_dd_suresi": str(dd_duration),
        "islem_sayisi": n_trades,
        "kazanma_orani_%": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 2) if np.isfinite(profit_factor) else float("inf"),
        "ortalama_islem_%": round(avg_trade_pct, 3),
        "piyasada_gecen_sure_%": round(time_in_market * 100, 1),
        "toplam_komisyon_bps": result.costs.total_bps,
    }
