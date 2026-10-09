import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PANEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PANEL))

import sanal_trader as st  # noqa: E402


@pytest.fixture
def izole_cikti(tmp_path, monkeypatch):
    """sanal_trader'in yazdigi TUM dosyalari gecici klasore yonlendirir --
    testler canli portfoye/islem gecmisine ASLA dokunmaz (bu hataya bir kez
    dusuldu: test betigi gercek islemler.csv'ye sahte satir yazmisti)."""
    for ad, dosya in (("CIKTI_KLASORU", ""), ("PORTFOY_DOSYASI", "portfoy.json"),
                      ("POZISYON_DOSYASI", "pozisyonlar.json"), ("ISLEM_DOSYASI", "islemler.csv"),
                      ("ROTASYON_DOSYASI", "rotasyon_gunlugu.csv"), ("DURUM_DOSYASI", "durum.json"),
                      ("CALISMA_DOSYASI", "calisma_durumu.json"), ("SAGLIK_DOSYASI", "saglik.json")):
        monkeypatch.setattr(st, ad, tmp_path / dosya if dosya else tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    st._olaylar.clear()
    st._saglik.update({"mum_verisi_ok": True, "hata": None, "verisiz_coin": []})
    yield tmp_path
    st._olaylar.clear()


def sentetik_mumlar(kapanislar, bitis=None, aralik_saat=1, oynaklik=0.002):
    """Verilen kapanis dizisinden yuksek/dusuk/acilis/hacim'i olan saatlik mumlar."""
    kapanislar = np.asarray(kapanislar, dtype=float)
    n = len(kapanislar)
    bitis = bitis or pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(hours=1)
    zaman = pd.date_range(end=bitis, periods=n, freq=f"{aralik_saat}h", tz="UTC")
    acilis = np.concatenate([[kapanislar[0]], kapanislar[:-1]])
    return pd.DataFrame({
        "zaman": zaman, "acilis": acilis,
        "yuksek": np.maximum(acilis, kapanislar) * (1 + oynaklik),
        "dusuk": np.minimum(acilis, kapanislar) * (1 - oynaklik),
        "kapanis": kapanislar, "hacim": np.full(n, 1000.0),
    })
