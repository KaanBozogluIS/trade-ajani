"""Tek bir sembol/strateji icin detayli backtest raporu + equity grafigi.

Kullanim:
    python scripts/single_backtest.py --symbol BTCUSDT --tf 4h --strategy donchian_breakout
    python scripts/single_backtest.py --symbol THYAO.IS --provider yahoo --tf 1d --strategy ema_cross
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt

from core import datastore
from core.backtest import Costs, run as run_backtest
from core.metrics import summarize
from core.strategies import REGISTRY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--provider", default="binance")
    parser.add_argument("--tf", default="4h")
    parser.add_argument("--strategy", required=True, choices=list(REGISTRY))
    parser.add_argument("--params", default="{}", help='JSON, orn. \'{"fast":10,"slow":30}\'')
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--market", default="crypto", choices=["crypto", "stock"])
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    df = datastore.get(args.provider, args.symbol, args.tf, start=args.start)
    if df.empty:
        print(f"Veri yok. Once: python scripts/fetch_data.py  ya da datastore.update() cagirin.")
        return

    params = json.loads(args.params)
    strategy = REGISTRY[args.strategy](**params)
    costs = Costs(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    result = run_backtest(df, strategy, costs=costs)
    m = summarize(result, args.tf, args.market)

    print(f"\n{args.provider} {args.symbol} {args.tf}  |  {strategy}\n")
    for k, v in m.items():
        print(f"  {k:24s}: {v}")

    if not result.trades.empty:
        print(f"\nSon 5 islem:\n{result.trades.tail(5).to_string(index=False)}")

    if not args.no_plot:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                                        gridspec_kw={"height_ratios": [3, 1]})
        ax1.plot(result.equity.index, result.equity.values, color="#2563eb", linewidth=1.2)
        ax1.set_title(f"{args.symbol} {args.tf} - {strategy}")
        ax1.set_ylabel("Sermaye")
        ax1.grid(alpha=0.3)

        dd = result.equity / result.equity.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values * 100, 0, color="#dc2626", alpha=0.4)
        ax2.set_ylabel("Drawdown %")
        ax2.grid(alpha=0.3)

        out_dir = Path(__file__).resolve().parent.parent / "reports"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{args.symbol}_{args.tf}_{args.strategy}.png"
        fig.tight_layout()
        fig.savefig(out_path, dpi=130)
        print(f"\nGrafik kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
