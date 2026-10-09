import numpy as np
import pandas as pd
import pytest

import sanal_trader as st
import trade_ajani_stratejileri as taj
from conftest import sentetik_mumlar


def _rastgele_yuruyus(n=1500, tohum=7):
    r = np.random.default_rng(tohum)
    return sentetik_mumlar(100 * np.exp(np.cumsum(r.normal(0, 0.012, n))), oynaklik=0.006)


@pytest.mark.parametrize("isim,fn,params", taj.STRATEJILER, ids=[s[0] for s in taj.STRATEJILER])
def test_trade_ajani_stratejileri_gecerli_sinyal_uretir(isim, fn, params):
    df = _rastgele_yuruyus()
    poz = fn(df, **params)
    assert len(poz) == len(df)
    assert set(poz.dropna().unique()) <= {-1.0, 0.0, 1.0}


def test_rotasyona_tum_strateji_aileleri_dahil():
    isimler = {s[0] for s in st._STRATEJILER_TUMU}
    assert {s[0] for s in taj.STRATEJILER} <= isimler
    assert "al ve tut" not in isimler and "rastgele" not in isimler


def test_tum_rotasyon_stratejileri_sentetik_veride_cokmez():
    df = _rastgele_yuruyus(n=st._MAKS_ISINMA + 400)
    for isim, fn, params, isinma in st._STRATEJILER_TUMU:
        poz = fn(df, **params)
        assert len(poz) == len(df), isim
