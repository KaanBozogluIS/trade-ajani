"""Konfluens (Coklu Onay) Stratejisi icin tam-evren IS/OOS taramasi.
Ayni disiplin: IS(%70)/OOS(%30), profit_factor>=1.0 HEM IS HEM OOS'ta.

Bilesenler zaten AYRI AYRI dogrulanmis (tepe_dip_stratejisi,
hacim_uyumsuzlugu_stratejisi, altcoin_stratejisi) - burada soru bunlarin
AYNI ANDA hemfikir oldugu anlarin, herhangi biri tek basina calisandan
DAHA GUCLU bir sinyal olup olmadigi.

Kullanim:
    python research/confluence_hunt.py --provider binance --timeframe 1h
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
from core.strategies.confluence_vote import ConfluenceVote

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"

PARAM_GRID: list[dict] = [
    {"components": "tepe_dip_stratejisi,hacim_uyumsuzlugu_stratejisi,altcoin_stratejisi", "min_votes": 2},
    {"components": "tepe_dip_stratejisi,hacim_uyumsuzlugu_stratejisi,altcoin_stratejisi", "min_votes": 3},
]


def split_is_oos(df: pd.DataFrame, is_ratio: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * is_ratio)
    return df.iloc[:cut], df.iloc[cut:]


def evaluate(df: pd.DataFrame, params: dict, timeframe: str, market: str, costs: Costs) -> dict | None:
    if len(df) < 250:
        return None
    result = run_backtest(df, ConfluenceVote(**params), costs=costs)
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
    out_path = Path(__file__).resolve().parent.parent / "reports" / "confluence_hunt_sonuclari.csv"
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

    # min_votes=2 vs min_votes=3 karsilastirmasi (ozet)
    result_df["min_votes"] = result_df["params"].apply(lambda p: p["min_votes"])
    print("\n=== min_votes karsilastirmasi (tum kombinasyonlar) ===")
    print(result_df.groupby("min_votes").agg(
        n=("symbol", "count"), gecen=("dual_pf_gecti", "sum"),
        ort_OOS_PF=("OOS_profit_factor", "mean"), ort_OOS_islem=("OOS_islem", "mean")))

    print(f"\nTam sonuclar: {out_path}")


if __name__ == "__main__":
    main()
