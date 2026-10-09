"""tek_coin_kontrolu / bir_dongu -- AG YOK: mum verisi ve strateji taklit edilir,
tum cikti dosyalari gecici klasorde (izole_cikti)."""
import json

import pandas as pd
import pytest

import sanal_trader as st
from conftest import sentetik_mumlar


class _Depo:
    durum = {}

    def coin(self, sembol):
        return None


def _hazirla(monkeypatch, kapanislar, sinyal, isinma=5):
    df = sentetik_mumlar(kapanislar)
    monkeypatch.setattr(st.vk, "mum_verisi", lambda s, z, adet: df.tail(adet).reset_index(drop=True))
    sabit = lambda d, **k: pd.Series([sinyal] * len(d), index=d.index, dtype=float)  # noqa: E731
    monkeypatch.setattr(st, "_STRATEJI_SOZLUGU", {"sabit": (sabit, {}, isinma)})
    return df


def _pozisyon(p, sembol, giris_fiyat, saat_once, kaldirac, yon="LONG"):
    p.pozisyonlar[sembol] = {
        "miktar": 1.0, "strateji": "sabit", "giris_fiyat": giris_fiyat, "maliyet": 100.0,
        "giris_zamani": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=saat_once)).isoformat(),
        "yon": yon, "kaldirac": kaldirac}
    p.nakit -= 100.0


def test_gecmiste_likidasyona_degip_donen_pozisyon_yakalanir(izole_cikti, monkeypatch):
    # 10x LONG @100 -> likidasyon 90. Fiyat 20 saat once 88'e indi, simdi 101.
    kapanislar = [100.0] * 60 + [95.0, 88.0, 95.0] + [101.0] * 20
    _hazirla(monkeypatch, kapanislar, 1.0)
    p = st.Portfoy(1000.0)
    _pozisyon(p, "X/USDT", 100.0, saat_once=30, kaldirac=10.0)
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) == "LIKIDASYON"
    assert "X/USDT" not in p.pozisyonlar and p.nakit == pytest.approx(900.0)
    assert any("LIKIDASYON" in o for o in st._olaylar)


def test_giristen_ONCEKI_dusus_likidasyon_sayilmaz(izole_cikti, monkeypatch):
    kapanislar = [100.0] * 40 + [80.0] + [100.0] * 40
    _hazirla(monkeypatch, kapanislar, 1.0)
    p = st.Portfoy(1000.0)
    _pozisyon(p, "X/USDT", 100.0, saat_once=10, kaldirac=10.0)
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) is None
    assert "X/USDT" in p.pozisyonlar


def test_maksimum_tutma_suresi_dolan_pozisyon_kapanir(izole_cikti, monkeypatch):
    _hazirla(monkeypatch, [100.0] * 500, 1.0)
    p = st.Portfoy(1000.0)
    _pozisyon(p, "X/USDT", 100.0, saat_once=24 * st.AYARLAR["maks_tutma_gun"] + 1, kaldirac=1.0)
    assert st.tek_coin_kontrolu(p, "X/USDT", "sabit", _Depo(), st.AYARLAR) == "SAT"
    satir = pd.read_csv(st.ISLEM_DOSYASI).iloc[-1]
    assert satir["sebep"] == "sure_doldu"


def test_yeni_pozisyon_kaldiracla_acilir_ve_olay_kaydedilir(izole_cikti, monkeypatch):
    _hazirla(monkeypatch, [100.0] * 100, -1.0)
    p = st.Portfoy(1000.0)
    assert st.tek_coin_kontrolu(p, "Y/USDT", "sabit", _Depo(), st.AYARLAR) == "KISA_AC"
    poz = p.pozisyonlar["Y/USDT"]
    assert poz["yon"] == "SHORT" and 5.0 <= poz["kaldirac"] <= 10.0
    assert st._olaylar and "SHORT AC" in st._olaylar[0]


def test_veri_yoksa_saglik_bozulur_ve_telegram_uyarisi_bir_kez_gider(izole_cikti, monkeypatch):
    monkeypatch.setattr(st.vk, "mum_verisi", lambda *a, **k: None)
    monkeypatch.setattr(st, "_STRATEJI_SOZLUGU", {"sabit": (lambda d: d, {}, 5)})
    gonderilen = []
    monkeypatch.setattr(st, "_telegram_gonder", lambda m: gonderilen.append(m) or True)
    durum = {"pozisyon_stratejileri": {"A/USDT": "sabit", "B/USDT": "sabit"},
             "son_rotasyon": pd.Timestamp.now(tz="UTC").isoformat()}
    p = st.Portfoy(1000.0)
    st.bir_dongu(p, durum, _Depo(), st.AYARLAR)
    st.bir_dongu(p, durum, _Depo(), st.AYARLAR)
    saglik = json.loads(st.SAGLIK_DOSYASI.read_text(encoding="utf-8"))
    assert saglik["mum_verisi_ok"] is False and saglik["verisiz_coin"] == ["A/USDT", "B/USDT"]
    assert len([m for m in gonderilen if "VERİ ALAMIYOR" in m]) == 1  # spam yok
