"""Stop-loss: canli bot (sanal_trader) ve rotasyon puanlamasi (dogrulama) AYNI kurali uygulamali."""
import pandas as pd
import pytest

import sanal_trader as st
from conftest import sentetik_mumlar
from dogrulama import simule_et


class _Depo:
    def coin(self, s):
        return None


def _hazirla(monkeypatch, kapanislar, sinyal=1.0):
    df = sentetik_mumlar(kapanislar, oynaklik=0.0)
    monkeypatch.setattr(st.vk, "mum_verisi", lambda s, z, adet: df.tail(adet).reset_index(drop=True))
    sabit = lambda d, **k: pd.Series([sinyal] * len(d), index=d.index, dtype=float)  # noqa: E731
    monkeypatch.setattr(st, "_STRATEJI_SOZLUGU", {"sabit": (sabit, {}, 5)})
    return df


def _poz(p, saat_once, stop=None, kaldirac=10.0, yon="LONG", giris=100.0, stop_saat_once=None):
    zaman = lambda s: (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=s)).isoformat()  # noqa: E731
    p.pozisyonlar["X/USDT"] = {"miktar": 10.0, "strateji": "sabit", "giris_fiyat": giris, "maliyet": 100.0,
                               "giris_zamani": zaman(saat_once), "yon": yon, "kaldirac": kaldirac}
    if stop is not None:
        p.pozisyonlar["X/USDT"]["stop_fiyat"] = stop
        p.pozisyonlar["X/USDT"]["stop_baslangic"] = zaman(stop_saat_once or saat_once)
    p.nakit -= 100.0


def test_yeni_pozisyon_stop_ile_acilir_ve_stop_likidasyondan_once(izole_cikti, monkeypatch):
    _hazirla(monkeypatch, [100.0] * 300)
    p = st.Portfoy(1000.0)
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) == "AL"
    poz = p.pozisyonlar["X/USDT"]
    assert poz["stop_fiyat"] > st._likidasyon_fiyati(poz)
    assert poz["stop_fiyat"] < poz["giris_fiyat"]


def test_stop_vurulunca_zarar_marjinin_tamami_degil(izole_cikti, monkeypatch):
    # 10x LONG @100, stop 98.8 (%1.2), likidasyon 90. Fiyat 85'e kadar dustu:
    # stop'suz -%100 olurdu; stop'la ~-%12 + komisyon.
    _hazirla(monkeypatch, [100.0] * 60 + [99.5, 98.0, 92.0, 85.0] + [86.0] * 10)
    p = st.Portfoy(1000.0)
    _poz(p, saat_once=20, stop=98.8)
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) == "SAT"
    satir = pd.read_csv(st.ISLEM_DOSYASI).iloc[-1]
    assert satir["sebep"] == "stop"
    assert -16 < satir["kar_zarar_yuzde"] < -10
    assert any("stop-loss" in o for o in st._olaylar)


def test_bosluklu_acilista_stoptan_degil_acilistan_dolar(izole_cikti, monkeypatch):
    # Mum stop'un altinda ACILIYOR (99 -> 97.5): dolum 97.5, stop 98.8 degil.
    df = _hazirla(monkeypatch, [100.0] * 60 + [99.0, 97.0] + [97.0] * 5)
    i = df.index[df["kapanis"] == 97.0][0]
    df.loc[i, "acilis"] = 97.5
    df.loc[i, "yuksek"] = 97.6
    p = st.Portfoy(1000.0)
    _poz(p, saat_once=20, stop=98.8)
    olay = st._risk_olayi(p.pozisyonlar["X/USDT"], df)
    assert olay == ("STOP", 97.5)


def test_eski_pozisyona_stop_eklenir_ama_gecmise_donuk_islem_uydurulmaz(izole_cikti, monkeypatch):
    # Stop'suz eski pozisyon: 10 saat once 98'e indi (stop'un altina), simdi 100.
    _hazirla(monkeypatch, [100.0] * 60 + [98.0] + [100.0] * 10)
    p = st.Portfoy(1000.0)
    _poz(p, saat_once=30)
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) is None
    poz = p.pozisyonlar["X/USDT"]
    assert poz["stop_fiyat"] < 100.0 and pd.Timestamp(poz["stop_baslangic"]) > pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=1)
    assert st.Portfoy.yukle(1000.0).pozisyonlar["X/USDT"]["stop_fiyat"] == poz["stop_fiyat"]  # kaydedildi


def test_zaten_stopun_altindaki_eski_pozisyona_guncel_fiyattan_stop(izole_cikti, monkeypatch):
    df = _hazirla(monkeypatch, [100.0] * 60 + [95.0] * 10)
    poz = {"giris_fiyat": 100.0, "yon": "LONG", "kaldirac": 10.0,
           "giris_zamani": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=30)).isoformat()}
    assert st._eksik_stopu_tamamla(poz, df, st.AYARLAR)
    assert st._likidasyon_fiyati(poz) < poz["stop_fiyat"] < 95.0


def test_short_stop_yukari_yonde(izole_cikti, monkeypatch):
    _hazirla(monkeypatch, [100.0] * 60 + [100.5, 101.5, 103.0] + [103.0] * 5, sinyal=-1.0)
    p = st.Portfoy(1000.0)
    _poz(p, saat_once=20, stop=101.2, yon="SHORT")
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) == "KISA_KAPAT"


def test_simulasyon_stopu_canli_botla_ayni_kural():
    A = {"baslangic_bakiye": 1000.0, "islem_ucreti_yuzde": 0.1, "islem_orani": 0.95}
    df = sentetik_mumlar([100.0] * 5 + [100 - i for i in range(1, 16)] + [85.0] * 10, oynaklik=0.0)
    poz = [0.0] * 3 + [1.0] * 27
    stopsuz = simule_et(df, poz, A, kaldirac=10.0, detay_don=True)
    stoplu = simule_et(df, poz, A, kaldirac=10.0, stop_orani=0.02, detay_don=True)
    assert stopsuz["islemler"][0]["getiri_yuzde"] == pytest.approx(-100.0)
    assert stoplu["stop"] >= 1 and stoplu["islemler"][0]["sebep"] == "stop"
    assert stoplu["islemler"][0]["getiri_yuzde"] > -30
    assert stoplu["getiri"] > stopsuz["getiri"]
