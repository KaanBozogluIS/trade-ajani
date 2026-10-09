"""mum_verisi testleri -- AG YOK, HTTP yanitlari taklit edilir."""
import pandas as pd
import pytest
import requests

import veri_kaynaklari as vk

SAAT_MS = 3_600_000


class _Yanit:
    def __init__(self, veri, durum=200):
        self._veri, self.status_code = veri, durum

    def json(self):
        return self._veri

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"{self.status_code} Client Error")


def _mumlar(baslangic_ms, adet):
    return [[baslangic_ms + i * SAAT_MS, "1", "2", "0.5", "1.5", "10", 0, "0", 0, "0", "0", "0"]
            for i in range(adet)]


@pytest.fixture
def sahte_borsa(monkeypatch):
    """Binance /klines davranisi: endTime'a kadar en fazla <limit> mum, eskiden yeniye."""
    son_kapali = (pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(hours=1)).value // 1_000_000
    tum = _mumlar(son_kapali - 2999 * SAAT_MS, 3000) + _mumlar(son_kapali + SAAT_MS, 1)  # +1 kapanmamis
    cagrilar = []

    def get(url, params=None, timeout=None):
        cagrilar.append((url, dict(params)))
        if "api.binance.com" in url and sahte_borsa_ayar.get("ikinci_adres_hata"):
            return _Yanit({}, 451)
        if "data-api" in url and sahte_borsa_ayar.get("ilk_adres_hata"):
            return _Yanit({"code": 0}, 451)
        bitis = params.get("endTime", 10**15)
        uygun = [m for m in tum if m[0] <= bitis]
        return _Yanit(uygun[-params["limit"]:])

    sahte_borsa_ayar = {}
    monkeypatch.setattr(vk._oturum, "get", get)
    return cagrilar, sahte_borsa_ayar


def test_sayfalama_bosluksuz_ve_kapanmamis_mum_atilir(sahte_borsa):
    cagrilar, _ = sahte_borsa
    df = vk.mum_verisi("BTC/USDT", "1h", 2500)
    assert len(df) == 2500 and len(cagrilar) == 3
    farklar = df["zaman"].diff().dropna().unique()
    assert len(farklar) == 1 and farklar[0] == pd.Timedelta(hours=1)
    assert df["zaman"].iloc[-1] < pd.Timestamp.now(tz="UTC").floor("h")
    assert list(df.columns) == ["zaman", "acilis", "yuksek", "dusuk", "kapanis", "hacim"]
    assert df["kapanis"].dtype == float
    assert cagrilar[0][1]["symbol"] == "BTCUSDT"


def test_ilk_adres_engelliyse_yedege_gecer(sahte_borsa):
    cagrilar, ayar = sahte_borsa
    ayar["ilk_adres_hata"] = True
    df = vk.mum_verisi("ETH/USDT", "1h", 50)
    assert df is not None and len(df) == 50
    assert any("api.binance.com" in u for u, _ in cagrilar)


def test_iki_adres_de_engelliyse_none_ve_sebep_kaydedilir(sahte_borsa):
    _, ayar = sahte_borsa
    ayar["ilk_adres_hata"] = ayar["ikinci_adres_hata"] = True
    assert vk.mum_verisi("ETH/USDT", "1h", 50) is None
    assert "451" in vk.son_mum_hatasi


def test_desteklenmeyen_zaman_dilimi():
    assert vk.mum_verisi("BTC/USDT", "7h", 10) is None
    assert "zaman dilimi" in vk.son_mum_hatasi
