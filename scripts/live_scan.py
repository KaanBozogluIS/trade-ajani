"""Canli sinyal taramasi: universe.yaml + config/watchlist.yaml'daki her
sembol/zaman dilimi icin secilen stratejinin GUNCEL kapali mumdaki sinyalini
hesaplar; onceki calistirmadaki durumdan FARKLIYSA Telegram'a bildirim atar.

Tekrar tekrar ayni sinyali gondermemek icin son durum data/state/last_signal.json
dosyasinda tutulur.

Kullanim (once en az bir kez fetch_data.py calistirilmali):
    python scripts/live_scan.py
    python scripts/live_scan.py --dry-run      # telegram'a gondermeden konsola yaz

Zamanlanmis calistirma icin Windows Gorev Zamanlayicisi / cron kullan:
    ornek: her 15 dakikada bir  ->  Windows Task Scheduler, trigger: Daily,
    repeat every 15 minutes, action: python.exe scripts\\live_scan.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows konsolu varsayilan olarak cp1254/cp1252 gibi kodlamalar kullanir,
# bunlar Telegram mesajlarindaki emojileri (LONG/SHORT/FLAT ikonlari)
# yazdiramaz ve UnicodeEncodeError ile cokuyordu. UTF-8'e zorla.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from dotenv import load_dotenv

from core import datastore
from core.notify.telegram import TelegramNotifier, format_signal_message
from core.strategies import REGISTRY
from core.strategy import Signal

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "universe.yaml"
WATCHLIST_PATH = ROOT / "config" / "watchlist.yaml"
STATE_PATH = ROOT / "data" / "state" / "last_signal.json"

_SIGNAL_NAME = {Signal.LONG: "LONG", Signal.SHORT: "SHORT", Signal.FLAT: "FLAT"}


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Telegram'a gonderme, sadece yazdir")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    if not WATCHLIST_PATH.exists():
        print(f"HATA: {WATCHLIST_PATH} yok. Once research/scan.py sonuclarindan "
              f"secim yapip config/watchlist.yaml.example dosyasini kopyalayin.")
        return

    watchlist = yaml.safe_load(WATCHLIST_PATH.read_text(encoding="utf-8")) or []
    state = load_state()
    notifier = TelegramNotifier()

    for entry in watchlist:
        provider, symbol, tf = entry["provider"], entry["symbol"], entry["timeframe"]
        strat_name, params = entry["strategy"], entry.get("params", {})
        key = f"{provider}:{symbol}:{tf}:{strat_name}"

        df = datastore.update(provider, symbol, tf, start=entry.get("start", "2023-01-01"))
        from core.providers.base import drop_unclosed_bar
        df = drop_unclosed_bar(df, tf)
        if len(df) < 250:
            print(f"[atlandi] {key} - yetersiz veri ({len(df)} mum)")
            continue

        strat_cls = REGISTRY[strat_name]
        result = strat_cls(**params).generate(df)
        last_signal = int(result.signal.iloc[-1])
        last_time = df.index[-1]
        last_price = float(df["close"].iloc[-1])

        prev_signal = state.get(key, {}).get("signal")
        changed = prev_signal != last_signal

        label = _SIGNAL_NAME[last_signal]
        print(f"{key:55s} -> {label:6s} @ {last_price:g}  ({last_time})"
              f"{'  [YENI]' if changed else ''}")

        if changed:
            msg = format_signal_message(
                provider=provider, symbol=symbol, timeframe=tf, strategy=strat_name,
                side=label, price=last_price, bar_time=last_time,
            )
            if args.dry_run:
                print("  (dry-run, gonderilmedi)\n" + msg)
            else:
                notifier.send(msg)

        state[key] = {"signal": last_signal, "time": str(last_time), "price": last_price}

    save_state(state)


if __name__ == "__main__":
    main()
