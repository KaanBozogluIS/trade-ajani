"""Binance'teki tum USDT paritelerini 24s hacme gore siralayip genis bir
kripto evreni uretir (config/universe.yaml icindeki 'binance.symbols' listesini
gunceller). ABD hisse/BIST listelerine dokunmaz.

Neden hepsini degil top-N: Binance'te 500+ USDT paritesi var, cogu gunde
birkac bin dolar hacim goruyor - bunlarda spread/slipaj o kadar buyuk ki
backtest sonucu anlamsizlasir. Hacme gore filtrelemek "gercekte islem
yapilabilir" bir evren verir.

Kullanim:
    python scripts/build_universe.py                  # top 150
    python scripts/build_universe.py --top 300
    python scripts/build_universe.py --min-quote-volume 5000000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core.providers.binance import get_24h_stats, get_usdt_spot_symbols

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"

# Bunlar hacim siralamasindan bagimsiz her zaman evrende kalir.
_ALWAYS_INCLUDE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

# Stabilcoin / altina-sabit varlik ciftleri: fiyati kasten sabit tutulur,
# trend/kirilim/mean-reversion stratejileri icin anlamsizdir (sinyal uretmez
# ya da gurultuye tepki verir). Base asset'e gore filtreleniyor.
_EXCLUDE_BASE_ASSETS = {
    "USDC", "USD1", "FDUSD", "TUSD", "USDE", "USDP", "GUSD", "DAI", "PYUSD",
    "BFUSD", "XUSD", "USTC", "FRAX", "EUR", "EURI", "RLUSD", "XAUT", "PAXG",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=150, help="Hacme gore alinacak coin sayisi")
    parser.add_argument("--min-quote-volume", type=float, default=2_000_000,
                         help="24s minimum USDT hacmi (bunun altindaki coin'ler elenir)")
    args = parser.parse_args()

    print("Binance USDT spot parite listesi cekiliyor...")
    tradable = set(get_usdt_spot_symbols())
    print(f"  {len(tradable)} aktif USDT paritesi bulundu")

    print("24 saatlik hacim istatistikleri cekiliyor...")
    stats = get_24h_stats()
    stats = stats[stats["symbol"].isin(tradable) & (stats["quote_volume_24h"] >= args.min_quote_volume)]
    stats = stats[~stats["symbol"].str.replace("USDT", "", regex=False).isin(_EXCLUDE_BASE_ASSETS)]
    stats = stats.sort_values("quote_volume_24h", ascending=False)

    ranked = stats["symbol"].tolist()
    final = list(dict.fromkeys(_ALWAYS_INCLUDE + ranked[: args.top]))

    print(f"  Secilen: {len(final)} sembol (min 24s hacim: ${args.min_quote_volume:,.0f})")
    print(f"  Ilk 15: {', '.join(final[:15])}")

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["binance"]["symbols"] = final
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"\n{CONFIG_PATH} guncellendi.")
    print("Simdi yeni coinlerin verisini cekmek icin: python scripts/fetch_data.py --only binance")
    print("(Bu, secilen zaman dilimlerinde ~%d sembol icin veri indirecegi icin biraz surer.)" % len(final))


if __name__ == "__main__":
    main()
