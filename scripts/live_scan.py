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

import pandas as pd
import yaml
from dotenv import load_dotenv

from core import datastore, indicators as ta
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
        # notify:false -> "gozlem modu" - sinyal takip edilir/loglanir AMA
        # Telegram'a gonderilmez. Yeni/henuz canliya alinmamis stratejileri
        # once bir sure gozlemlemek icin (bkz. tepe_dip_stratejisi girisleri).
        entry_notify = entry.get("notify", True)
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
        # NOT: coğu strateji stop_loss/take_profit'i SADECE giris barinda
        # dolduruyor (backtest.py bunu yeterli buluyor - sadece o bari
        # okuyor). Canli gosterimde ise pozisyon acikken SONRAKI barlarda
        # da "hala gecerli olan" stop/hedefi gormek isteriz - ffill() bunu
        # cozer (yeni bir giris oldugunda zaten TAZE bir deger yazilir,
        # eskisinin uzerine gecer - bkz. core/strategy.py StrategyResult).
        sl_series = result.stop_loss.ffill() if result.stop_loss is not None else None
        tp_series = result.take_profit.ffill() if result.take_profit is not None else None
        strat_sl = float(sl_series.iloc[-1]) if sl_series is not None and not pd.isna(sl_series.iloc[-1]) else None
        last_tp = float(tp_series.iloc[-1]) if tp_series is not None and not pd.isna(tp_series.iloc[-1]) else None

        # BASKA BIR ONEMLI DUZELTME: trend-takip stratejileri (ema_cross,
        # major_stratejisi) pozisyonu AYLARCA acik tutabiliyor - bu durumda
        # stratejinin KENDI stop'u (giris barinda kilitlenen) fiyattan
        # COK uzak/anlamsiz kalabilir (ornek: ZECUSDT'de %59 mesafe -
        # matematiksel olarak dogru ama "simdi nereden girsem" sorusuna
        # yaramaz). Bu yuzden HER ZAMAN GUNCEL ATR'a gore taze bir stop da
        # hesaplaniyor; stratejinin kendi stop'u COK uzaksa (>%15) o
        # yerine bu guncel deger kullanilir.
        atr_now = float(ta.atr(df, 14).iloc[-1])
        fresh_sl = None
        if not pd.isna(atr_now) and atr_now > 0:
            fresh_sl = last_price - 2.5 * atr_now if last_signal > 0 else last_price + 2.5 * atr_now
        stale = strat_sl is not None and abs(last_price - strat_sl) / last_price > 0.15
        last_sl = fresh_sl if (strat_sl is None or stale) else strat_sl

        prev_signal = state.get(key, {}).get("signal")
        changed = prev_signal != last_signal

        label = _SIGNAL_NAME[last_signal]
        from core.tz import format_istanbul
        print(f"{key:55s} -> {label:6s} @ {last_price:g}  ({format_istanbul(last_time)})"
              f"{'  [YENI]' if changed else ''}")

        if changed:
            # watchlist.yaml'da satir-bazli risk_pct/max_leverage override
            # edilebilir (varsayilan %1.5 risk / 10x - kullanicinin
            # belirttigi 5-10x kaldirac araliginin ustu).
            msg = format_signal_message(
                provider=provider, symbol=symbol, timeframe=tf, strategy=strat_name,
                side=label, price=last_price, bar_time=last_time,
                stop_loss=last_sl, take_profit=last_tp,
                risk_per_trade_pct=entry.get("risk_per_trade_pct", 1.5),
                max_leverage=entry.get("max_leverage", 10.0),
            )
            if args.dry_run:
                print("  (dry-run, gonderilmedi)\n" + msg)
            elif not entry_notify:
                print("  (gozlem modu - notify:false, gonderilmedi)\n" + msg)
            else:
                notifier.send(msg)

        state[key] = {"signal": last_signal, "time": str(last_time), "price": last_price}

    save_state(state)


if __name__ == "__main__":
    main()
