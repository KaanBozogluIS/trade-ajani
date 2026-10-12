from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

import sanal_trader as st
from conftest import sentetik_mumlar

A = st.AYARLAR


def test_ilk_calismada_zirve_bugunden_baslar_kesici_tetiklenmez():
    p = st.Portfoy(1000.0)
    assert p.devre_kesiciyi_guncelle(500.0, A) is None  # gecmisteki dusus kesiciyi tetiklemez
    assert p.zirve == 500.0 and not p.devre_kesici_aktif_mi()


def test_zirveden_esik_kadar_dusus_tetikler_ve_yeni_pozisyonu_engeller():
    p = st.Portfoy(1000.0)
    p.devre_kesiciyi_guncelle(1000.0, A)
    assert p.devre_kesiciyi_guncelle(800.0, A) is None          # %20 -- esigin alti
    assert p.devre_kesiciyi_guncelle(750.0, A) == "TETIKLENDI"  # %25
    assert p.devre_kesici_aktif_mi() and p.bos_pozisyon_yeri(8) == 0
    assert p.devre_kesiciyi_guncelle(700.0, A) is None          # aktifken tekrar tetiklenmez


def test_sure_dolunca_biter_ve_zirve_sifirlanir():
    p = st.Portfoy(1000.0)
    p.zirve = 1000.0
    p.devre_kesici_bitis = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert p.devre_kesiciyi_guncelle(600.0, A) == "BITTI"
    assert p.zirve == 600.0 and p.devre_kesici_bitis is None and p.bos_pozisyon_yeri(8) == 8


def test_durum_kaydedilip_yukleniyor(izole_cikti):
    p = st.Portfoy(1000.0)
    p.devre_kesiciyi_guncelle(1000.0, A)
    p.devre_kesiciyi_guncelle(700.0, A)
    p.kaydet()
    q = st.Portfoy.yukle(1000.0)
    assert q.zirve == 1000.0 and q.devre_kesici_aktif_mi()


class _Depo:
    def __init__(self, fiyatlar):
        self.fiyatlar = fiyatlar

    def coin(self, s):
        return {"fiyat": self.fiyatlar[s]} if s in self.fiyatlar else None


def _pozisyonlu_portfoy():
    p = st.Portfoy(1000.0)
    p.ac("A/USDT", "s", 100.0, 500.0, 0.0, yon="LONG", kaldirac=1.0)
    p.zirve = 1000.0
    return p


def test_eksik_fiyatta_kesici_yanlislikla_tetiklenmez(izole_cikti):
    p = _pozisyonlu_portfoy()
    st._dongu_sonu(p, _Depo({}), A, 1)  # A/USDT fiyati yok -> toplam 500 GORUNUR
    assert not p.devre_kesici_aktif_mi()


def test_dongu_sonu_kesiciyi_tetikler_ve_bildirir(izole_cikti, monkeypatch):
    giden = []
    monkeypatch.setattr(st, "_telegram_gonder", lambda m: giden.append(m) or True)
    p = _pozisyonlu_portfoy()
    st._dongu_sonu(p, _Depo({"A/USDT": 40.0}), A, 1)  # 500 + 200 = 700 -> %30 dusus
    assert p.devre_kesici_aktif_mi()
    assert giden and "DEVRE KESİCİ" in giden[0]
    assert st.Portfoy.yukle(1000.0).devre_kesici_aktif_mi()  # kalici


def test_sakin_donem_tuzagi_uzun_oynaklik_kaldiraci_dusurur():
    # 7 gun cok oynak, son 20 saat cok sakin
    r = np.random.default_rng(1)
    oynak = 100 * np.exp(np.cumsum(r.normal(0, 0.03, 300)))
    sakin = np.full(20, oynak[-1])
    df = sentetik_mumlar(np.concatenate([oynak, sakin]), oynaklik=0.0005)
    sadece_kisa = dict(A, kaldirac_uzun_atr_mum=1)  # eski davranisin vekili
    assert st._kaldirac_hesapla(df, sadece_kisa) > st._kaldirac_hesapla(df, A)
    assert st._kaldirac_hesapla(df, A) >= A["min_kaldirac"]


def test_canli_akista_olmayan_fiyat_RESTten_alinir_ve_kesici_calisir(izole_cikti, monkeypatch):
    monkeypatch.setattr(st.vk, "son_fiyat", lambda sembol: 40.0)
    p = _pozisyonlu_portfoy()
    st._dongu_sonu(p, _Depo({}), A, 1)  # canli akis bos -> REST 40 -> 500 + 200 = 700, %30 dusus
    assert p.devre_kesici_aktif_mi()


def test_stablecoin_otomatik_taninir():
    stabil = sentetik_mumlar(1.0 + 0.0005 * np.sin(np.arange(800)), oynaklik=0.0002)
    oynak = sentetik_mumlar(100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.01, 800))))
    dolar_civari_oynak = sentetik_mumlar(1.0 + 0.1 * np.sin(np.arange(800) / 20))
    assert st._stabil_mi(stabil)
    assert not st._stabil_mi(oynak) and not st._stabil_mi(dolar_civari_oynak)
