"""Universe'deki tum sembol/zaman dilimi kombinasyonlarini onbellege ceker.

Kullanim:
    python scripts/fetch_data.py
    python scripts/fetch_data.py --only binance
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core import datastore

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["binance", "us_stocks", "bist"], default=None)
    args = parser.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    start = cfg["backtest_defaults"]["start"]

    groups = {k: v for k, v in cfg.items() if k in ("binance", "us_stocks", "bist")}
    if args.only:
        groups = {args.only: groups[args.only]}

    for group_name, group in groups.items():
        provider = "binance" if group_name == "binance" else group["provider"]
        for symbol in group["symbols"]:
            for tf in group["timeframes"]:
                t0 = time.time()
                try:
                    df = datastore.update(provider, symbol, tf, start=start)
                    print(f"[OK]   {provider:8s} {symbol:12s} {tf:4s} "
                          f"{len(df):6d} mum  ({time.time()-t0:4.1f}s)")
                except Exception as exc:
                    print(f"[HATA] {provider:8s} {symbol:12s} {tf:4s}  {exc}")


if __name__ == "__main__":
    main()
