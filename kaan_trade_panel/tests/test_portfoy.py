import pytest

import sanal_trader as st


def test_spot_long_formulu_degismedi():
    p = st.Portfoy(1000.0)
    p.ac("A/USDT", "s", 100.0, 200.0, 0.1, yon="LONG")
    s = p.kapat("A/USDT", 110.0, 0.1)
    assert s["kar_zarar"] == pytest.approx(19.56022)
    assert p.nakit == pytest.approx(1019.56022)


def test_spot_short_fiyat_duserse_kar():
    p = st.Portfoy(1000.0)
    p.ac("A/USDT", "s", 100.0, 200.0, 0.1, yon="SHORT")
    assert p.kapat("A/USDT", 90.0, 0.1)["kar_zarar"] == pytest.approx(19.82018)


def test_yon_alani_olmayan_eski_pozisyon_long_sayilir():
    p = st.Portfoy(1000.0)
    p.pozisyonlar["E/USDT"] = {"miktar": 2.0, "strateji": "s", "giris_fiyat": 100.0,
                               "giris_zamani": "2026-01-01T00:00:00+00:00", "maliyet": 200.0}
    assert p.kapat("E/USDT", 110.0, 0.1)["kar_zarar"] > 0


@pytest.mark.parametrize("yon,cikis", [("LONG", 105.0), ("SHORT", 95.0)])
def test_kaldiracli_kar_marjin_x_kaldirac(yon, cikis):
    p = st.Portfoy(1000.0)
    p.ac("B/USDT", "s", 100.0, 100.0, 0.0, yon=yon, kaldirac=8.0)
    assert p.kapat("B/USDT", cikis, 0.0)["kar_zarar"] == pytest.approx(40.0)


def test_kaldiracli_giris_komisyonu_dusulur():
    # 10x, %0.1 komisyon, fiyat degismedi -> giris + cikis komisyonu ~ marjinin %2'si
    p = st.Portfoy(1000.0)
    p.ac("C/USDT", "s", 100.0, 100.0, 0.1, yon="LONG", kaldirac=10.0)
    kz = p.kapat("C/USDT", 100.0, 0.1)["kar_zarar"]
    assert kz == pytest.approx(-2.0, abs=0.01)


def test_likidasyon_marjinle_sinirli_ve_nakit_negatife_dusmez():
    p = st.Portfoy(1000.0)
    p.ac("D/USDT", "s", 100.0, 100.0, 0.0, yon="LONG", kaldirac=8.0)
    assert st._likidasyon_fiyati(p.pozisyonlar["D/USDT"]) == pytest.approx(87.5)
    s = p.kapat("D/USDT", 50.0, 0.0)
    assert s["tutar"] == 0.0 and s["kar_zarar"] == pytest.approx(-100.0)
    assert p.nakit == pytest.approx(900.0)


def test_spot_pozisyon_likide_olmaz():
    assert st._likidasyon_fiyati({"giris_fiyat": 100.0, "yon": "LONG"}) is None
    assert st._likidasyon_fiyati({"giris_fiyat": 100.0, "kaldirac": 1.0}) is None


def test_toplam_deger_kaldiracli_sifirin_altina_inmez():
    p = st.Portfoy(1000.0)
    p.ac("E/USDT", "s", 100.0, 100.0, 0.0, yon="LONG", kaldirac=8.0)
    assert p.toplam_deger({"E/USDT": 50.0}) == pytest.approx(900.0)


def test_toplam_deger_ile_kapat_tutarli():
    # Acik pozisyonun degeri ~ o an kapatilsa donecek nakit (cikis komisyonu haric)
    p = st.Portfoy(1000.0)
    p.ac("F/USDT", "s", 100.0, 100.0, 0.1, yon="SHORT", kaldirac=5.0)
    deger = p.toplam_deger({"F/USDT": 96.0})
    p.kapat("F/USDT", 96.0, 0.1)
    assert deger == pytest.approx(p.nakit, abs=0.6)


@pytest.mark.parametrize("oynaklik,beklenen", [(0.0005, 10.0), (0.05, 5.0)])
def test_kaldirac_her_zaman_5_10_araliginda(oynaklik, beklenen):
    from conftest import sentetik_mumlar
    df = sentetik_mumlar([100.0] * 60, oynaklik=oynaklik)
    assert st._kaldirac_hesapla(df, st.AYARLAR) == pytest.approx(beklenen)
