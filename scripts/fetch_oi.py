"""Acik Pozisyon (OI) + long/short orani verisini evrendeki tum semboller
icin gunceller ve KALICI olarak biriktirir (core/oi_store.py).

Binance bu veriyi sadece ~30 gun saklıyor - bu script'in duzenli
calistirilmasi (bkz. .github/workflows/fetch_oi.yml, saatlik) sayesinde
Binance'in penceresi kaysa bile bizim yerel arsivimiz kalici buyur.

NOT: sadece futures'ta islem goren semboller icin veri doner - spot'ta
olup futures'ta olmayan semboller icin bos/hata donerse ATLANIR (durdurmaz).

Kullanim:
    python scripts/fetch_oi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core import oi_store
from core.providers.base import DataProviderError

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"


def main() -> None:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    symbols = cfg["binance"]["symbols"]

    ok = skipped = 0
    for symbol in symbols:
        try:
            oi = oi_store.update_open_interest(symbol, period="1h")
            ls = oi_store.update_long_short_ratio(symbol, period="1h")
            if oi.empty and ls.empty:
                skipped += 1
                continue
            ok += 1
        except DataProviderError as exc:
            print(f"[atlandi] {symbol}: {exc}")
            skipped += 1
        except Exception as exc:  # futures'ta olmayan sembol vb. - durdurmadan devam
            print(f"[atlandi] {symbol}: beklenmeyen hata: {exc}")
            skipped += 1

    print(f"\nTamamlandi: {ok} sembol guncellendi, {skipped} atlandi.")
    inv = oi_store.describe_cache()
    if not inv.empty:
        total_bars = inv["bars"].sum()
        print(f"Toplam biriken kayit: {total_bars}, en eski: {inv['start'].min()}, en yeni: {inv['end'].max()}")


if __name__ == "__main__":
    main()
