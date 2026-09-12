r"""
DOGRULAMA ARACI
===============

Bir stratejinin gercekten ise yarayip yaramadigini olcen arac.

Neden ayri bir arac?
    geriye_donuk_test.py bir stratejinin TEK bir coinde ne yaptigini
    ayrintili anlatir. Ama "iyi bir sonuc" ile "sans" arasindaki farki
    gostermez. Bu dosya onu gosterir; uc soruyu birden sorar:

      1. Ayni kural BIRDEN COK coinde de calisiyor mu?
      2. Ayni kural HIC BAKILMAMIS bir zaman diliminde de calisiyor mu?
      3. Sonuc, ayar degistikce cok mu oynuyor?

    Ucu birden tutuyorsa elinizde bir sey olabilir. Sadece biri tutuyorsa
    muhtemelen tesaduf gormussunuzdur.

Calistirmak icin:
    .\.venv\Scripts\python.exe dogrulama.py
"""

import sys

import pandas as pd

from geriye_donuk_test import en_buyuk_dusus
from veri_indir import veri_al

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


AYARLAR = {
    "borsa": "binance",
    "coinler": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "kac_gun": 730,
    "baslangic_bakiye": 1000.0,
    "islem_ucreti_yuzde": 0.1,
    "islem_orani": 0.95,
    "periyotlar": [20, 50, 100, 150],
    "test_orani": 0.30,          # verinin son %30'u hic bakilmayan bolum
}


# ============================================================
#  STRATEJI
# ============================================================
#
# Bu arac "pozisyon" mantigi kullanir: her mum icin tek bir cevap
#   1 = coin elimde olsun,  0 = nakitte bekleyeyim
#
# Kesisme mantigindan farki: "al" ve "sat" anlarini degil, "nerede
# olmam gerektigini" tarif eder. Ayni sey ama yazmasi cok daha kolay.

def sma_trend(df, periyot):
    """
    Fiyat, son <periyot> mumun ortalamasinin uzerindeyse pozisyonda ol.
    Altindaysa nakitte bekle.

    Bu bir "trend filtresi". Buyuk cokusleri disarida bekletmeyi amaclar.
    """
    ortalama = df["kapanis"].rolling(periyot).mean()
    return (df["kapanis"] > ortalama).astype("float").where(ortalama.notna())


# ============================================================
#  YARDIMCILAR
# ============================================================

def gunluge_cevir(df):
    """Saatlik mumlari gunluk mumlara birlestirir."""
    return (df.set_index("zaman")
              .resample("1D")
              .agg({"acilis": "first", "yuksek": "max", "dusuk": "min",
                    "kapanis": "last", "hacim": "sum"})
              .dropna()
              .reset_index())


def simule_et(df, pozisyon, a, baslangic=0, detay_don=False):
    """
    Pozisyon listesini gercek alim-satima cevirip sonucu olcer.

    baslangic : bu indeksten ONCEKI mumlar sadece ortalamayi hesaplamak
                icin kullanilir, islem yapilmaz. Boylece test bolumunun
                ilk mumlari "ortalama henuz hazir degil" diye bosa gitmez.

    Islemler, sinyalin gorulduğu mumun SONRASINDAKI mumun acilisinda
    yapilir -- cunku gercek hayatta kapanis fiyatini ancak mum kapaninca
    ogrenirsiniz.

    SHORT DESTEGI (2026-09-12): bu aracın kendi stratejileri (sma_trend,
    tarama.py/strateji_desenleri.py'deki tumu) HEP 0/1 uretir -- bu yuzden
    asagidaki -1 dallari onlar icin hicbir zaman calismaz, davranis AYNEN
    korunur. -1, SADECE Trade-ajani'ndan aktarilan (ve sanal_trader.py'nin
    rotasyonuna eklenen) stratejilerden gelir -- SHORT ekonomisi
    sanal_trader.py'nin Portfoy.kapat()'iyle AYNI matematik (fiyat
    dustukce kazanc): kar_zarar = tutar * (giris_fiyat - kapanis_fiyat) / giris_fiyat.

    <detay_don>: True ise sonuc sozlugune "seri" (portfoy degeri, HER
    mum icin), "zamanlar" (df'de "zaman" sutunu varsa o, yoksa indeks)
    ve "islemler" (her kapanan islemin giris/cikis zamani-fiyati-yonu-
    getirisi) eklenir -- Trade Ajanı sayfasındaki geçmişe dönük analiz
    aracı (grafik + işlem tablosu) için. Varsayilan False'ta davranis
    (dondurulen sozluk) ESKISIYLE BIREBIR AYNI -- rotasyon/tarama.py gibi
    mevcut cagiranlar etkilenmez.
    """
    acilis = df["acilis"].tolist()
    kapanis = df["kapanis"].tolist()
    zaman_sutunu = df["zaman"].tolist() if "zaman" in df.columns else None
    poz = list(pozisyon)
    n = len(df)

    nakit, coin = a["baslangic_bakiye"], 0.0
    yon = None  # None / "LONG" / "SHORT" -- SADECE SHORT icin kullanilir, LONG hala "coin" ile takip edilir
    kisa_miktar = kisa_giris_fiyat = kisa_tutar = None
    ucret_o = a["islem_ucreti_yuzde"] / 100
    bekleyen, acik_tutar = None, None
    turlar, seri = [], []
    odenen_ucret, piyasada = 0.0, 0
    islem_kayitlari = []
    acik_giris = None  # {"zaman","fiyat","yon"} -- detay_don icin

    for i in range(baslangic, n):
        if bekleyen == "AL" and coin == 0 and yon is None:
            harcanan = nakit * a["islem_orani"]
            if harcanan >= 1:
                ucret = harcanan * ucret_o
                coin = (harcanan - ucret) / acilis[i]
                nakit -= harcanan
                odenen_ucret += ucret
                acik_tutar = harcanan
                if detay_don:
                    acik_giris = {"zaman": zaman_sutunu[i] if zaman_sutunu else i,
                                 "fiyat": acilis[i], "yon": "LONG"}
        elif bekleyen == "KISA_AC" and coin == 0 and yon is None:
            harcanan = nakit * a["islem_orani"]
            if harcanan >= 1:
                ucret = harcanan * ucret_o
                kisa_miktar = (harcanan - ucret) / acilis[i]
                nakit -= harcanan
                odenen_ucret += ucret
                kisa_giris_fiyat, kisa_tutar = acilis[i], harcanan
                acik_tutar = harcanan
                yon = "SHORT"
                if detay_don:
                    acik_giris = {"zaman": zaman_sutunu[i] if zaman_sutunu else i,
                                 "fiyat": acilis[i], "yon": "SHORT"}
        elif bekleyen == "SAT" and coin > 0:
            brut = coin * acilis[i]
            ucret = brut * ucret_o
            nakit += brut - ucret
            odenen_ucret += ucret
            if acik_tutar:
                getiri_yuzde = (brut - ucret - acik_tutar) / acik_tutar * 100
                turlar.append(getiri_yuzde)
                if detay_don and acik_giris:
                    islem_kayitlari.append({**acik_giris, "cikis_zaman": zaman_sutunu[i] if zaman_sutunu else i,
                                            "cikis_fiyat": acilis[i], "getiri_yuzde": getiri_yuzde})
                acik_tutar = None
            coin = 0.0
        elif bekleyen == "SAT" and yon == "SHORT":
            brut_islem = kisa_miktar * acilis[i]
            ucret = brut_islem * ucret_o
            kar_zarar = kisa_tutar * (kisa_giris_fiyat - acilis[i]) / kisa_giris_fiyat - ucret
            net = kisa_tutar + kar_zarar
            nakit += net
            odenen_ucret += ucret
            if acik_tutar:
                getiri_yuzde = (net - acik_tutar) / acik_tutar * 100
                turlar.append(getiri_yuzde)
                if detay_don and acik_giris:
                    islem_kayitlari.append({**acik_giris, "cikis_zaman": zaman_sutunu[i] if zaman_sutunu else i,
                                            "cikis_fiyat": acilis[i], "getiri_yuzde": getiri_yuzde})
                acik_tutar = None
            kisa_miktar = kisa_giris_fiyat = kisa_tutar = None
            yon = None
        bekleyen = None

        # Sinyal uret (son mumda uretmiyoruz, cunku islenecek mum kalmaz)
        if i >= 1 and i < n - 1 and not pd.isna(poz[i]):
            if poz[i] == 1 and coin == 0 and yon is None:
                bekleyen = "AL"
            elif poz[i] == -1 and coin == 0 and yon is None:
                bekleyen = "KISA_AC"
            elif poz[i] == 0 and (coin > 0 or yon == "SHORT"):
                bekleyen = "SAT"

        if coin > 0:
            piyasada += 1
            seri.append(nakit + coin * kapanis[i])
        elif yon == "SHORT":
            piyasada += 1
            deger = kisa_tutar * (kisa_giris_fiyat - kapanis[i]) / kisa_giris_fiyat if kisa_giris_fiyat else 0.0
            seri.append(nakit + kisa_tutar + deger)
        else:
            seri.append(nakit)

    if not seri:
        return None

    kazanan = [t for t in turlar if t > 0]
    ilk_acilis = acilis[baslangic]
    al_tut = a["baslangic_bakiye"] * (1 - ucret_o) * (kapanis[-1] / ilk_acilis)

    sonuc = {
        "getiri": (seri[-1] / a["baslangic_bakiye"] - 1) * 100,
        "al_tut_getiri": (al_tut / a["baslangic_bakiye"] - 1) * 100,
        "dusus": en_buyuk_dusus(seri),
        "al_tut_dusus": en_buyuk_dusus(kapanis[baslangic:]),
        "tur": len(turlar),
        "kazanma": len(kazanan) / len(turlar) * 100 if turlar else 0.0,
        "ucret": odenen_ucret,
        "piyasada": piyasada / (n - baslangic) * 100,
        "mum": n - baslangic,
    }
    if detay_don:
        sonuc["seri"] = seri
        sonuc["zamanlar"] = zaman_sutunu[baslangic:] if zaman_sutunu else list(range(baslangic, n))
        sonuc["islemler"] = islem_kayitlari
    return sonuc


# ============================================================
#  RAPOR
# ============================================================

def coin_dogrula(sembol, a):
    saatlik = veri_al(a["borsa"], sembol, "1h", a["kac_gun"])
    gunluk = gunluge_cevir(saatlik)

    ayirma = int(len(gunluk) * (1 - a["test_orani"]))
    egitim = gunluk.iloc[:ayirma].reset_index(drop=True)

    print()
    print("=" * 90)
    print(f"  {sembol}   -   {len(gunluk):,} gunluk mum   "
          f"({gunluk['zaman'].iloc[0]:%Y-%m-%d} / {gunluk['zaman'].iloc[-1]:%Y-%m-%d})")
    print("=" * 90)
    print(f"  {'kural':<16}{'egitim':>10}{'TEST':>10}{'al-tut(test)':>15}"
          f"{'TEST dusus':>13}{'al-tut dusus':>14}{'islem':>8}")
    print("  " + "-" * 86)

    satirlar = []
    for p in a["periyotlar"]:
        e = simule_et(egitim, sma_trend(egitim, p), a)

        # Test bolumu: oncesinden <p> mum "isinma" olarak ekliyoruz ki
        # ortalama test doneminin ilk gununde hazir olsun.
        isinma = p + 2
        bas = max(0, ayirma - isinma)
        dilim = gunluk.iloc[bas:].reset_index(drop=True)
        t = simule_et(dilim, sma_trend(dilim, p), a, baslangic=ayirma - bas)

        if e is None or t is None:
            continue
        print(f"  {'SMA' + str(p):<16}{e['getiri']:>9.2f}%{t['getiri']:>9.2f}%"
              f"{t['al_tut_getiri']:>14.2f}%{t['dusus']:>12.2f}%"
              f"{t['al_tut_dusus']:>13.2f}%{t['tur']:>8}")
        satirlar.append((p, e, t))

    return satirlar


def main():
    a = AYARLAR
    print()
    print("#" * 90)
    print("  DOGRULAMA:  trend filtresi (fiyat > hareketli ortalama), gunluk mumlar")
    print(f"  Egitim = verinin ilk %{int((1 - a['test_orani']) * 100)}   |   "
          f"TEST = son %{int(a['test_orani'] * 100)} (bu bolume gore hicbir secim yapilmadi)")
    print("#" * 90)

    hepsi = {}
    for sembol in a["coinler"]:
        hepsi[sembol] = coin_dogrula(sembol, a)

    # --- Ozet: kac durumda dusus azaldi, kac durumda getiri yendi? ---
    dusus_iyi = dusus_top = getiri_iyi = getiri_top = 0
    for satirlar in hepsi.values():
        for _, _, t in satirlar:
            dusus_top += 1
            getiri_top += 1
            if t["dusus"] > t["al_tut_dusus"]:      # daha az dusus = daha iyi
                dusus_iyi += 1
            if t["getiri"] > t["al_tut_getiri"]:
                getiri_iyi += 1

    print()
    print("=" * 90)
    print("  OZET  (sadece TEST bolumune bakarak)")
    print("=" * 90)
    print(f"  En buyuk dususu azaltti : {dusus_iyi} / {dusus_top} durumda")
    print(f"  Getiride al-ve-tut'u yendi: {getiri_iyi} / {getiri_top} durumda")
    print()
    print("  NASIL OKUNUR:")
    print("  * Bir sonucun guvenilir olmasi icin coinlerin ve ayarlarin")
    print("    COGUNDA ayni yonde cikmasi gerekir. Tek bir parlak sayi degersizdir.")
    print("  * Getiri sayilari ayar degistikce cok oynuyorsa, o getiri")
    print("    stratejinin degil sansin eseridir.")
    print("  * Bu test 2024-2026 arasini kapsar ve bu donem cogunlukla")
    print("    dususle gecti. Dususte 'nakite kac' kurallari dogal olarak iyi")
    print("    gorunur. Yukselen bir piyasada ayni kural para KAYBETTIRIR.")
    print("=" * 90)


if __name__ == "__main__":
    main()
