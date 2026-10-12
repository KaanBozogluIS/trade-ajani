"""bot_gecmis_testi.simule -- AG YOK: tek coinlik sentetik veriyle mekanik kontrolu."""
import numpy as np

import bot_gecmis_testi as bgt


def _coin(kapanis, sinyal=1.0, kaldirac=5.0, stop_orani=0.02):
    kapanis = np.asarray(kapanis, dtype=float)
    n = len(kapanis)
    acilis = np.concatenate([[kapanis[0]], kapanis[:-1]])
    return {"acilis": acilis, "yuksek": np.maximum(acilis, kapanis), "dusuk": np.minimum(acilis, kapanis),
            "kapanis": kapanis, "kaldirac": np.full(n, kaldirac), "stop_orani": np.full(n, stop_orani),
            "poz": np.full((1, n), sinyal), "puan": np.zeros((1, n))}


def test_yukselen_fiyatta_long_kazandirir():
    egri, sayac = bgt.simule({"X": _coin(np.linspace(100, 110, 100))}, 100, "en_iyi")
    assert egri[-1] > 1000 and sayac["stop"] == 0 and sayac["likidasyon"] == 0


def test_cokuste_stop_marjinin_tamamini_kaybettirmez():
    # %15 dusus: 5x'te stop'suz likidasyon (-%100 marjin) olurdu; stop %2'de keser.
    kapanis = np.concatenate([np.full(5, 100.0), np.linspace(100, 85, 30), np.full(10, 85.0)])
    egri, sayac = bgt.simule({"X": _coin(kapanis)}, len(kapanis), "en_iyi")
    assert sayac["stop"] >= 1 and sayac["likidasyon"] == 0
    assert egri[-1] > 800


def test_devre_kesici_tetiklenir_ve_yeni_pozisyonu_durdurur():
    # 8 coin birlikte dusuyor, stop'lar likidasyondan sonra (fiilen yok):
    # her biri likide olur, portfoy zirveden %25+ duser -> kesici.
    kapanis = np.concatenate([np.full(5, 100.0), np.linspace(100, 60, 200)])
    coinler = {f"C{i}": _coin(kapanis, stop_orani=0.5) for i in range(8)}
    egri, sayac = bgt.simule(coinler, len(kapanis), "en_iyi")
    assert sayac["kesici"] >= 1
    assert egri[-1] > 0


def test_al_tut_kaldiracli_likidasyon():
    kapanis = np.array([100.0, 90.0, 79.0, 85.0])
    egri = bgt.al_tut(kapanis, kapanis, 5.0)
    assert egri[-1] == 0.0  # %20 dusus 5x'te likidasyon; sonra toparlanma kurtarmaz
