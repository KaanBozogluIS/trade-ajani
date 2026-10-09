"""live_scan.main -- AG YOK: veri, strateji, Telegram ve durum dosyasi taklit edilir."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.strategy import Signal, StrategyResult  # noqa: E402
import scripts.live_scan as ls  # noqa: E402


class _SabitLong:
    def __init__(self, **_):
        pass

    def generate(self, df):
        sinyal = pd.Series(Signal.FLAT, index=df.index, dtype="int64")
        sinyal.iloc[-3:] = Signal.LONG  # 3 mum once basladi
        return StrategyResult(signal=sinyal)


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    n = 300
    idx = pd.date_range(end="2026-01-01", periods=n, freq="1h", tz="UTC")
    kapanis = np.linspace(100, 110, n)
    df = pd.DataFrame({"open": kapanis, "high": kapanis * 1.01, "low": kapanis * 0.99,
                       "close": kapanis, "volume": 1.0}, index=idx)
    izleme = tmp_path / "watchlist.yaml"
    izleme.write_text("- {provider: binance, symbol: TESTUSDT, timeframe: 1h, strategy: sabit_test}\n")
    monkeypatch.setattr(ls, "WATCHLIST_PATH", izleme)
    monkeypatch.setattr(ls, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ls.datastore, "update", lambda *a, **k: df)
    monkeypatch.setitem(ls.REGISTRY, "sabit_test", _SabitLong)
    monkeypatch.setattr(ls, "load_dotenv", lambda *a, **k: None)
    gonderilen = []
    return tmp_path, gonderilen, monkeypatch


def _calistir(monkeypatch, gonderilen, basarili, *arg):
    def send(self, metin, parse_mode="Markdown"):
        gonderilen.append(metin)
        return basarili
    monkeypatch.setattr(ls.TelegramNotifier, "send", send)
    monkeypatch.setattr(sys, "argv", ["live_scan.py", *arg])
    ls.main()


def test_gonderilemeyen_sinyal_kaybolmaz_sonraki_turda_tekrar_denenir(ortam):
    tmp, gonderilen, mp = ortam
    _calistir(mp, gonderilen, False)
    assert not (tmp / "state.json").exists() or "TESTUSDT" not in (tmp / "state.json").read_text()
    _calistir(mp, gonderilen, True)
    assert len(gonderilen) == 2 and "TESTUSDT" in (tmp / "state.json").read_text()
    _calistir(mp, gonderilen, True)
    assert len(gonderilen) == 2  # artik degisiklik yok, tekrar gonderilmez


def test_mesajda_gec_tespit_bilgisi(ortam):
    _, gonderilen, mp = ortam
    _calistir(mp, gonderilen, True)
    assert "`2` mum once basladi" in gonderilen[0]


def test_dry_run_durum_dosyasini_yazmaz(ortam):
    tmp, gonderilen, mp = ortam
    _calistir(mp, gonderilen, True, "--dry-run")
    assert not gonderilen and not (tmp / "state.json").exists()
