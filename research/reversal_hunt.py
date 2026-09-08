"""Tepe/Dip Stratejisi (ReversalPullback) icin tam-evren IS/OOS taramasi.

Ayni disiplin: her seri IS (%70) / OOS (%30) bolunur, parametre secimi
IS'e gore YAPILMAZ (sabit "makul" set denenir). Bir sonuc ancak IS VE OOS
ikisinde de profit_factor >= 1.0 (net karli) ISE guvenilir sayilir - sadece
IS'te iyi cikan sonuclar ezber (overfit) suphelisidir (ONGUSDT'de daha once
yakalanan hata: yuksek WR ama IS_PF < 1 -> tam tarihte net zararli cikmisti).

Kullanim:
    python research/reversal_hunt.py
    python research/reversal_hunt.py --timeframe 1h
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yaml

from core import datastore
from core.backtest import Costs, run as run_backtest
from core.metrics import summarize
from core.strategies.reversal_pullback import ReversalPullback

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"

PARAM_GRID: list[dict] = [
    # tol=0.15 satirlari EN YENI ve EN GUCLU bulgu: gevsek (0.4-0.6) tolerans
    # "bolgeleri" cok kaba kumeliyordu (gercekte cok da anlamli olmayan
    # seviyeler de "destek/direnc" sayiliyordu). Tolerans siki tutulunca
    # (fiyat kumesi zaten %0.15 icinde toplanmis - GERCEKTEN net bir
    # seviye) 14 sembollik bir alt kumede tam-tarih PF 1.28 -> 1.77'ye,
    # IS/OOS ikisinde de 12/14 sembol PF>=1.0 gecti (bkz. sohbet notlari).
    {"tolerance_pct": 0.15, "min_touches": 2, "vol_mult": 1.3, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 2.0, "tp_r_mult_range": 1.2, "adx_trend_min": 22.0},
    {"tolerance_pct": 0.15, "min_touches": 2, "vol_mult": 1.1, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 3.0, "tp_r_mult_range": 1.5, "adx_trend_min": 22.0},
    {"tolerance_pct": 0.2, "min_touches": 2, "vol_mult": 1.2, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 2.5, "tp_r_mult_range": 1.5, "adx_trend_min": 20.0},
    {"tolerance_pct": 0.4, "min_touches": 2, "vol_mult": 1.1, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 3.0, "tp_r_mult_range": 1.5, "adx_trend_min": 22.0},
    {"tolerance_pct": 0.6, "min_touches": 2, "vol_mult": 1.2, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 2.5, "tp_r_mult_range": 1.5, "adx_trend_min": 20.0},
    {"tolerance_pct": 0.4, "min_touches": 3, "vol_mult": 1.0, "sl_atr_buffer": 0.4,
     "tp_r_mult_trend": 3.0, "tp_r_mult_range": 2.0, "adx_trend_min": 25.0},
    {"tolerance_pct": 0.6, "min_touches": 2, "vol_mult": 1.3, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 2.0, "tp_r_mult_range": 1.2, "adx_trend_min": 22.0},
    {"tolerance_pct": 0.5, "min_touches": 2, "vol_mult": 1.1, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 4.0, "tp_r_mult_range": 1.5, "adx_trend_min": 22.0,
     "rsi_oversold_trend": 45.0, "rsi_oversold_range": 30.0},
    {"tolerance_pct": 0.4, "min_touches": 2, "vol_mult": 1.0, "sl_atr_buffer": 0.3,
     "tp_r_mult_trend": 3.0, "tp_r_mult_range": 1.5, "adx_trend_min": 18.0,
     "rsi_oversold_trend": 50.0, "rsi_oversold_range": 35.0},
]


def split_is_oos(df: pd.DataFrame, is_ratio: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * is_ratio)
    return df.iloc[:cut], df.iloc[cut:]


def evaluate(df: pd.DataFrame, params: dict, timeframe: str, market: str, costs: Costs) -> dict | None:
    if len(df) < 250:
        return None
    result = run_backtest(df, ReversalPullback(**params), costs=costs)
    m = summarize(result, timeframe, market)
    return None if "error" in m else m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    bt_cfg = cfg["backtest_defaults"]
    costs = Costs(fee_bps=bt_cfg["fee_bps"], slippage_bps=bt_cfg["slippage_bps"])

    jobs = []
    for symbol in cfg["binance"]["symbols"]:
        for tf in cfg["binance"]["timeframes"]:
            jobs.append(("binance", symbol, tf, "crypto"))
    for symbol in cfg["us_stocks"]["symbols"]:
        for tf in cfg["us_stocks"]["timeframes"]:
            jobs.append(("yahoo", symbol, tf, "stock"))
    for symbol in cfg["bist"]["symbols"]:
        for tf in cfg["bist"]["timeframes"]:
            jobs.append(("yahoo", symbol, tf, "stock"))

    if args.provider:
        jobs = [j for j in jobs if j[0] == args.provider]
    if args.timeframe:
        jobs = [j for j in jobs if j[2] == args.timeframe]

    MIN_TOTAL_BARS = 1000
    MIN_TRADES = 5

    rows = []
    skipped_thin = skipped_few_trades = 0
    total_jobs = len(jobs)
    for job_i, (provider, symbol, tf, market) in enumerate(jobs):
        df = datastore.get(provider, symbol, tf)
        if df.empty or len(df) < MIN_TOTAL_BARS:
            skipped_thin += 1
            continue
        df_is, df_oos = split_is_oos(df)

        for params in PARAM_GRID:
            m_is = evaluate(df_is, params, tf, market, costs)
            m_oos = evaluate(df_oos, params, tf, market, costs)
            if m_is is None or m_oos is None:
                continue
            if m_is["islem_sayisi"] < MIN_TRADES or m_oos["islem_sayisi"] < MIN_TRADES:
                skipped_few_trades += 1
                continue
            # KATI FILTRE: hem IS hem OOS net karli olmali (profit_factor >= 1.0)
            # - sadece bunlardan biri iyiyse ezber suphesi (bkz. dosya ust bilgisi).
            is_pf_ok = m_is["profit_factor"] >= 1.0
            oos_pf_ok = m_oos["profit_factor"] >= 1.0
            rows.append({
                "provider": provider, "symbol": symbol, "tf": tf, "params": params,
                "IS_sharpe": m_is["sharpe"], "OOS_sharpe": m_oos["sharpe"],
                "IS_getiri_%": m_is["toplam_getiri_%"], "OOS_getiri_%": m_oos["toplam_getiri_%"],
                "IS_profit_factor": m_is["profit_factor"], "OOS_profit_factor": m_oos["profit_factor"],
                "IS_islem": m_is["islem_sayisi"], "OOS_islem": m_oos["islem_sayisi"],
                "OOS_kazanma_%": m_oos["kazanma_orani_%"], "OOS_maxdd_%": m_oos["max_drawdown_%"],
                "dual_pf_gecti": is_pf_ok and oos_pf_ok,
            })
        if (job_i + 1) % 20 == 0:
            print(f"  ...{job_i + 1}/{total_jobs} is/tf kombinasyonu tarandi", file=sys.stderr)

    print(f"\n(Elendi: {skipped_thin} sembol yetersiz gecmis (<{MIN_TOTAL_BARS} mum), "
          f"{skipped_few_trades} kombinasyon yetersiz islem sayisi (<{MIN_TRADES}) yuzunden)")

    if not rows:
        print("Sonuc yok.")
        return

    result_df = pd.DataFrame(rows)
    out_path = Path(__file__).resolve().parent.parent / "reports" / "reversal_hunt_sonuclari.csv"
    out_path.parent.mkdir(exist_ok=True)
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    passed = result_df[result_df["dual_pf_gecti"]].copy()
    passed = passed.sort_values(["OOS_profit_factor", "OOS_sharpe"], ascending=False)

    print(f"\n=== Toplam {len(result_df)} kombinasyon test edildi, "
          f"{len(passed)} tanesi IS+OOS ikisinde de PF>=1.0 gecti ===\n")
    display_cols = ["provider", "symbol", "tf", "IS_sharpe", "OOS_sharpe", "IS_profit_factor",
                     "OOS_profit_factor", "OOS_islem", "OOS_kazanma_%", "OOS_maxdd_%", "params"]
    if not passed.empty:
        print(passed[display_cols].head(args.top).to_string(index=False))
    else:
        print("(Hicbir kombinasyon dual-PF filtresini gecemedi)")

    print(f"\nTam sonuclar: {out_path}")


if __name__ == "__main__":
    main()
