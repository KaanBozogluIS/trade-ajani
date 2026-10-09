import pandas as pd
import pytest

from conftest import sentetik_mumlar
from dogrulama import simule_et

A = {"baslangic_bakiye": 1000.0, "islem_ucreti_yuzde": 0.1, "islem_orani": 0.95}


def _df(kapanislar):
    return sentetik_mumlar(kapanislar, oynaklik=0.0)


def test_spot_long_regresyon():
    df = _df([100 + i for i in range(30)])
    s = simule_et(df, [0.0] * 5 + [1.0] * 15 + [0.0] * 10, A)
    assert s["tur"] == 1 and s["getiri"] > 0
    assert "seri" not in s  # detay_don=False eski anahtarlari degistirmez


@pytest.mark.parametrize("yonlu_fiyat,beklenen_isaret", [(-1, 1), (1, -1)])
def test_spot_short(yonlu_fiyat, beklenen_isaret):
    df = _df([200 + yonlu_fiyat * i for i in range(30)])
    s = simule_et(df, [0.0] * 5 + [-1.0] * 15 + [0.0] * 10, A)
    assert s["tur"] == 1 and s["getiri"] * beklenen_isaret > 0


def test_detay_don_islem_kaydi_ve_seri():
    df = _df([100 + i for i in range(30)])
    s = simule_et(df, [0.0] * 5 + [1.0] * 15 + [0.0] * 10, A, detay_don=True)
    assert len(s["seri"]) == len(s["zamanlar"]) == 30
    assert len(s["islemler"]) == 1 and s["islemler"][0]["yon"] == "LONG"


def test_kaldiracli_getiri_spottan_buyuk():
    df = _df([100 * 1.002 ** i for i in range(60)])
    poz = [0.0] * 5 + [1.0] * 50 + [0.0] * 5
    spot, kald = simule_et(df, poz, A), simule_et(df, poz, A, kaldirac=5.0)
    assert kald["getiri"] > 3 * spot["getiri"] > 0
    assert kald["likidasyon"] == 0


def test_kaldiracli_likidasyon_marjini_sifirlar():
    # 10x LONG, fiyat %15 dusuyor -> likidasyon (%10'da)
    df = _df([100.0] * 5 + [100 - i for i in range(1, 16)] + [85.0] * 10)
    s = simule_et(df, [0.0] * 3 + [1.0] * 27, A, kaldirac=10.0, detay_don=True)
    assert s["likidasyon"] >= 1
    assert s["islemler"][0]["likidasyon"] is True
    assert s["islemler"][0]["getiri_yuzde"] == pytest.approx(-100.0)


def test_kaldiracli_spot_ile_ayni_islem_zamanlamasi():
    df = _df([100 + (i % 7) for i in range(80)])
    poz = ([0.0] * 4 + [1.0] * 6) * 8
    assert simule_et(df, poz, A)["tur"] == simule_et(df, poz, A, kaldirac=3.0)["tur"]
