"""hisse_mum_verisi -- AG YOK: yfinance modulu taklit edilir."""
import sys
import types

import numpy as np
import pandas as pd
import pytest

import veri_kaynaklari as vk

NY = "America/New_York"


def _yahoo_tablosu(index):
    n = len(index)
    kapanis = np.linspace(10, 20, n)
    return pd.DataFrame({"Open": kapanis, "High": kapanis * 1.01, "Low": kapanis * 0.99,
                         "Close": kapanis, "Volume": 1e6}, index=index)


@pytest.fixture
def sahte_yf(monkeypatch):
    ayar = {}

    def download(sembol, interval, period, **_):
        ayar["cagri"] = (sembol, interval, period)
        return ayar["tablo"]

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(download=download))
    return ayar


def _simdi(monkeypatch, ny_zaman):
    gercek = pd.Timestamp.now
    sabit = pd.Timestamp(ny_zaman, tz=NY)
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(
        lambda cls, tz=None: sabit.tz_convert(tz) if tz else sabit.tz_convert("UTC").tz_localize(None)))
    return gercek


def test_gunluk_seans_surerken_bugunun_mumu_atilir(sahte_yf, monkeypatch):
    _simdi(monkeypatch, "2026-10-09 13:00")
    sahte_yf["tablo"] = _yahoo_tablosu(pd.date_range("2026-01-01", "2026-10-09", freq="B"))
    df = vk.hisse_mum_verisi("mstr", "1d", 10_000)
    assert sahte_yf["cagri"] == ("MSTR", "1d", "max")
    assert df["zaman"].iloc[-1].date() == pd.Timestamp("2026-10-08").date()
    assert list(df.columns) == ["zaman", "acilis", "yuksek", "dusuk", "kapanis", "hacim"]
    assert str(df["zaman"].dt.tz) == "UTC"


def test_gunluk_seans_kapandiktan_sonra_bugun_dahil(sahte_yf, monkeypatch):
    _simdi(monkeypatch, "2026-10-09 17:00")
    sahte_yf["tablo"] = _yahoo_tablosu(pd.date_range("2026-01-01", "2026-10-09", freq="B"))
    assert vk.hisse_mum_verisi("MSTR", "1d", 10_000)["zaman"].iloc[-1].date() == pd.Timestamp("2026-10-09").date()


def test_saatlik_suren_mum_atilir_ve_15_30_mumu_16da_kapanir(sahte_yf, monkeypatch):
    saatler = [f"2026-10-08 {h}" for h in ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30")] + \
              ["2026-10-09 09:30", "2026-10-09 10:30"]
    sahte_yf["tablo"] = _yahoo_tablosu(pd.DatetimeIndex(saatler).tz_localize(NY))
    _simdi(monkeypatch, "2026-10-09 11:00")  # 10:30 mumu henuz kapanmadi
    df = vk.hisse_mum_verisi("AMPX", "1h", 100)
    assert sahte_yf["cagri"][1:] == ("60m", "730d")
    son = df["zaman"].iloc[-1].tz_convert(NY)
    assert son == pd.Timestamp("2026-10-09 09:30", tz=NY) and len(df) == 8


def test_bos_yanit_none_ve_sebep(sahte_yf):
    sahte_yf["tablo"] = pd.DataFrame()
    assert vk.hisse_mum_verisi("YOKBOYLE", "1d") is None
    assert "YOKBOYLE" in vk.son_mum_hatasi


def test_desteklenmeyen_zaman_dilimi():
    assert vk.hisse_mum_verisi("MSTR", "4h") is None and "4h" in vk.son_mum_hatasi


def test_haftalik_gunlukten_turetilir_ve_biten_hafta_atilir(sahte_yf, monkeypatch):
    # Persembe 13:00 NY: bu hafta (Pzt-Cum) henuz bitmedi -> son tam hafta onceki hafta
    _simdi(monkeypatch, "2026-10-08 13:00")
    sahte_yf["tablo"] = _yahoo_tablosu(pd.date_range("2026-09-01", "2026-10-08", freq="B"))
    df = vk.hisse_mum_verisi("MSTR", "1w", 100)
    assert df["zaman"].iloc[-1].date() == pd.Timestamp("2026-09-28").date()  # Pazartesi etiketi
    assert (df["zaman"].dt.weekday == 0).all()
    gun = vk.hisse_mum_verisi("MSTR", "1d", 1000)
    hafta = gun[(gun["zaman"] >= "2026-09-28") & (gun["zaman"] <= "2026-10-03")]
    son = df.iloc[-1]
    assert son["acilis"] == hafta["acilis"].iloc[0] and son["kapanis"] == hafta["kapanis"].iloc[-1]
    assert son["yuksek"] == hafta["yuksek"].max() and son["hacim"] == hafta["hacim"].sum()


def test_goreli_guc_kiyas_adi():
    import analiz_botu as ab
    yukselen = pd.DataFrame({"kapanis": np.linspace(10, 20, 40)})
    duz = pd.DataFrame({"kapanis": np.full(40, 10.0)})
    g = ab.gozlem_goreli_guc(yukselen, duz, "AMPX", kiyas_adi="S&P 500")
    assert g and "S&P 500 karşısında daha güçlü" in g[0]["baslik"] and "BTC" not in g[0]["aciklama"]
    assert "BTC karşısında" in ab.gozlem_goreli_guc(yukselen, duz, "ETH")[0]["baslik"]  # coin varsayilani
