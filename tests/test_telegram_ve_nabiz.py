import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from core.notify.telegram import format_signal_message  # noqa: E402


def _mesaj(**ek):
    temel = dict(provider="binance", symbol="PEPEUSDT", timeframe="1h", strategy="tepe_dip_stratejisi",
                 side="LONG", price=4.52e-06, bar_time=pd.Timestamp("2026-09-29 18:00", tz="UTC"))
    return format_signal_message(**{**temel, **ek})


def test_gec_tespit_uyarisi():
    m = _mesaj(bars_ago=5, signal_start_time=pd.Timestamp("2026-09-29 13:00", tz="UTC"),
               signal_start_price=4.37e-06)
    assert "5` mum once basladi" in m and "%+3.43" in m
    assert "Gec tespit" not in _mesaj()


def test_birden_kucuk_kaldirac_kaldiracsiz_boyut_olarak_yazilir():
    assert "sermayenin `%31`'i ile, kaldiracsiz" in _mesaj(stop_loss=4.30e-06)
    assert "`2.3x` kaldirac" in _mesaj(stop_loss=4.49e-06)
    assert "0.3x" not in _mesaj(stop_loss=4.30e-06)


def _nabiz_calistir(tmp_path, dakika_once):
    betik = tmp_path / "scripts" / "sunucu_nabzi_taze_mi.py"
    betik.parent.mkdir()
    betik.write_text((KOK / "scripts" / "sunucu_nabzi_taze_mi.py").read_text(encoding="utf-8"), encoding="utf-8")
    if dakika_once is not None:
        (tmp_path / "data" / "state").mkdir(parents=True)
        zaman = datetime.now(timezone.utc) - timedelta(minutes=dakika_once)
        (tmp_path / "data" / "state" / "sunucu_nabiz.json").write_text(
            json.dumps({"zaman": zaman.isoformat(), "makine": "test"}), encoding="utf-8")
    cikti = tmp_path / "gh_output"
    subprocess.run([sys.executable, str(betik)], check=True, env={"GITHUB_OUTPUT": str(cikti)})
    return cikti.read_text().strip()


def test_nabiz_taze_ise_github_atlar(tmp_path):
    assert _nabiz_calistir(tmp_path, 3) == "atla=true"


def test_nabiz_eski_ya_da_yoksa_github_calisir(tmp_path):
    assert _nabiz_calistir(tmp_path, 45) == "atla=false"


def test_nabiz_dosyasi_yoksa_github_calisir(tmp_path):
    assert _nabiz_calistir(tmp_path, None) == "atla=false"
