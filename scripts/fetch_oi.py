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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core import oi_store
from core.providers.base import DataProviderError

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"
# Tek sembol icin makul olmayan bir sure (ornegin paylasimli/kisitli bir
# IP'de sikisma) - asilirsa UYARI basilir ama script DURDURULMAZ, sadece
# hangi sembolun yavaslattigi GORULEBILIR olsun diye.
YAVAS_ESIK_SN = 15.0


def main() -> None:
    t_basla = time.time()
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    symbols = cfg["binance"]["symbols"]
    print(f"[i] {len(symbols)} sembol icin OI/long-short guncellenecek...", flush=True)

    ok = skipped = 0
    for i, symbol in enumerate(symbols):
        t0 = time.time()
        try:
            oi = oi_store.update_open_interest(symbol, period="1h")
            ls = oi_store.update_long_short_ratio(symbol, period="1h")
            gecen = time.time() - t0
            if gecen > YAVAS_ESIK_SN:
                print(f"  [yavas] {symbol}: {gecen:.1f}sn", flush=True)
            if oi.empty and ls.empty:
                skipped += 1
                continue
            ok += 1
        except DataProviderError as exc:
            print(f"[atlandi] {symbol}: {exc}", flush=True)
            skipped += 1
        except Exception as exc:  # futures'ta olmayan sembol vb. - durdurmadan devam
            print(f"[atlandi] {symbol}: beklenmeyen hata: {exc}", flush=True)
            skipped += 1
        if (i + 1) % 15 == 0:
            print(f"  ...{i + 1}/{len(symbols)} ({time.time() - t_basla:.0f}sn gecti)", flush=True)

    print(f"\nTamamlandi: {ok} sembol guncellendi, {skipped} atlandi. "
          f"Toplam sure: {time.time() - t_basla:.0f}sn", flush=True)
    inv = oi_store.describe_cache()
    if not inv.empty:
        total_bars = inv["bars"].sum()
        print(f"Toplam biriken kayit: {total_bars}, en eski: {inv['start'].min()}, en yeni: {inv['end'].max()}")


if __name__ == "__main__":
    main()
