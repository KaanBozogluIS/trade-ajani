r"""
STRATEJI KUTUPHANESI
====================

Piyasada anlatilan strateji ailelerinin her biri burada, ayni kalipta.

KALIP: Her strateji bir fonksiyondur. Mum verisini alir ve her mum icin
tek bir cevap uretir:
      1.0  = coin elimde olsun
      0.0  = nakitte bekleyeyim
      NaN  = henuz karar veremem (gosterge isinmadi)

Neden hepsi ayni kalipta? Cunku ancak o zaman adil karsilastirilabilirler.
Farkli kaliplarda yazilmis stratejileri kiyaslamak, birini kilometreyle
digerini mille olcup "hangisi uzun?" diye sormak gibidir.

ONEMLI: Buradaki hicbir strateji "kar getirir" diye konulmadi. Hepsi
piyasada YAYGIN OLARAK ANLATILDIGI icin konuldu. Hangisinin ise
yaradigina tarama.py karar verir -- ya da hicbirinin yaramadigina.
"""

import numpy as np
import pandas as pd


# ============================================================
#  YARDIMCI GOSTERGELER
# ============================================================

def rsi(kapanis, periyot=14):
    """
    RSI (Relative Strength Index) -- "Goreli Guc Endeksi".
    0 ile 100 arasinda bir sayi. Kabaca: son <periyot> mumda yukselisler
    dususlere gore ne kadar baskin?
      70 uzeri -> "cok yukselmis" (asiri alim)
      30 alti  -> "cok dusmus"    (asiri satim)
    """
    fark = kapanis.diff()
    kazanc = fark.clip(lower=0)
    kayip = -fark.clip(upper=0)
    ort_kazanc = kazanc.ewm(alpha=1 / periyot, adjust=False).mean()
    ort_kayip = kayip.ewm(alpha=1 / periyot, adjust=False).mean()
    rs = ort_kazanc / ort_kayip.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df, periyot=14):
    """
    ATR (Average True Range) -- ortalama gercek aralik.
    Fiyatin gunluk ne kadar oynadigini gosterir. Oynaklik olcusu.
    """
    onceki_kapanis = df["kapanis"].shift(1)
    aralik = pd.concat([
        df["yuksek"] - df["dusuk"],
        (df["yuksek"] - onceki_kapanis).abs(),
        (df["dusuk"] - onceki_kapanis).abs(),
    ], axis=1).max(axis=1)
    return aralik.ewm(alpha=1 / periyot, adjust=False).mean()


def giris_cikis_pozisyon(giris, cikis):
    """
    Bazi stratejilerin girme ve cikma kurali ayridir (ornek: RSI 30'un
    altina inince gir, 70'in uzerine cikinca cik). Arada ne olacagi
    "en son ne yaptigina" baglidir. Bu fonksiyon onu takip eder.
    """
    pozisyonlar = []
    icinde = False
    for g, c in zip(giris, cikis):
        if pd.isna(g) or pd.isna(c):
            pozisyonlar.append(np.nan)
            continue
        if not icinde and g:
            icinde = True
        elif icinde and c:
            icinde = False
        pozisyonlar.append(1.0 if icinde else 0.0)
    return pd.Series(pozisyonlar, index=giris.index)


# ============================================================
#  1) KIYAS CIZGILERI  (baseline)
# ============================================================
# Bunlar strateji degil, ölçü aleti. Bir strateji bunlari
# gecemiyorsa hicbir ise yaramiyor demektir.

def al_ve_tut(df):
    """Basta al, sonuna kadar tut. Yenilmesi gereken cizgi."""
    return pd.Series(1.0, index=df.index)


def rastgele(df, tohum=0, degisim_olasiligi=0.02):
    """
    KONTROL GRUBU -- para atarak karar veren "strateji".

    Bu en onemli kiyas cizgisidir. Bir strateji rastgeleyi gecemiyorsa,
    o strateji hicbir sey bilmiyor demektir. Ilaç denemelerinde seker
    hapi (placebo) ne ise, bu da odur.

    degisim_olasiligi: her mumda pozisyon degistirme sansi. 0.02 secildi
    ki gercek stratejilerle benzer siklikta islem yapsin.
    """
    uretici = np.random.default_rng(tohum)
    pozisyonlar = []
    durum = uretici.random() < 0.5
    for _ in range(len(df)):
        if uretici.random() < degisim_olasiligi:
            durum = not durum
        pozisyonlar.append(1.0 if durum else 0.0)
    return pd.Series(pozisyonlar, index=df.index)


# ============================================================
#  2) TREND TAKIBI
# ============================================================
# Fikir: "Yukselen seyler yukselmeye devam eder." Buyuk cokusleri
# disarida beklemeyi amaclar. En eski ve en cok arastirilmis aile.

def sma_trend(df, periyot=100):
    """Fiyat, <periyot> mumluk ortalamasinin uzerindeyse pozisyonda ol."""
    ortalama = df["kapanis"].rolling(periyot).mean()
    return (df["kapanis"] > ortalama).astype(float).where(ortalama.notna())


def ma_kesisme(df, hizli=20, yavas=100):
    """
    Hizli ortalama yavasin uzerindeyse pozisyonda ol.
    (bot.py'de kullandigimiz kesisme stratejisinin pozisyon hali)
    """
    h = df["kapanis"].rolling(hizli).mean()
    y = df["kapanis"].rolling(yavas).mean()
    return (h > y).astype(float).where(y.notna())


def donchian_kirilma(df, giris_periyot=55, cikis_periyot=20):
    """
    "Turtle" kurali diye bilinen klasik kirilma stratejisi.
    Fiyat son <giris_periyot> mumun EN YUKSEGINI gecerse gir.
    Son <cikis_periyot> mumun EN DUSUGUNUN altina inerse cik.
    """
    en_yuksek = df["yuksek"].rolling(giris_periyot).max().shift(1)
    en_dusuk = df["dusuk"].rolling(cikis_periyot).min().shift(1)
    return giris_cikis_pozisyon(df["kapanis"] > en_yuksek,
                                df["kapanis"] < en_dusuk)


def macd_trend(df, hizli=12, yavas=26, sinyal=9):
    """
    MACD: iki ustel ortalamanin farki, ve o farkin ortalamasi.
    Fark, kendi ortalamasinin uzerindeyse pozisyonda ol.
    """
    h = df["kapanis"].ewm(span=hizli, adjust=False).mean()
    y = df["kapanis"].ewm(span=yavas, adjust=False).mean()
    cizgi = h - y
    sinyal_cizgi = cizgi.ewm(span=sinyal, adjust=False).mean()
    gecerli = df["kapanis"].rolling(yavas).mean().notna()
    return (cizgi > sinyal_cizgi).astype(float).where(gecerli)


def momentum(df, periyot=90):
    """
    Zaman serisi momentumu: son <periyot> mumda fiyat yukselmisse gir.
    Akademik literaturde en cok test edilmis kurallardan biridir.
    """
    getiri = df["kapanis"] / df["kapanis"].shift(periyot) - 1
    return (getiri > 0).astype(float).where(getiri.notna())


# ============================================================
#  3) ORTALAMAYA DONUS  (mean reversion)
# ============================================================
# Fikir: "Cok dusen toparlar, cok cikan geri gelir." Trend
# takibinin TAM TERSI. Ikisi ayni anda dogru olamaz -- hangisinin
# hangi kosulda dogru oldugu test isidir.

def rsi_geri_donus(df, periyot=14, alt=30, ust=60):
    """RSI <alt>'in altina inince gir (cok dusmus), <ust>'u gecince cik."""
    r = rsi(df["kapanis"], periyot)
    return giris_cikis_pozisyon(r < alt, r > ust)


def bollinger_geri_donus(df, periyot=20, katsayi=2.0):
    """
    Bollinger bantlari: ortalama, arti/eksi oynakligin katsayi kati.
    Fiyat alt bandin altina inince gir, ortalamaya donunce cik.
    """
    ortalama = df["kapanis"].rolling(periyot).mean()
    sapma = df["kapanis"].rolling(periyot).std()
    alt_bant = ortalama - katsayi * sapma
    return giris_cikis_pozisyon(df["kapanis"] < alt_bant,
                                df["kapanis"] > ortalama)


# ============================================================
#  4) OYNAKLIK TABANLI
# ============================================================

def dusuk_oynaklik(df, periyot=30, esik=0.6):
    """
    Fikir: "Sakin piyasada kal, firtinada disarida bekle."
    Oynaklik son bir yilin ortalamasinin <esik> katindan azsa pozisyonda ol.
    """
    gunluk_oynaklik = atr(df, periyot) / df["kapanis"]
    uzun_ortalama = gunluk_oynaklik.rolling(365, min_periods=100).mean()
    return (gunluk_oynaklik < uzun_ortalama * (1 + esik)).astype(float).where(
        uzun_ortalama.notna())


def atr_kirilma(df, periyot=20, katsayi=1.0):
    """
    Fiyat, son <periyot> mumun ortalamasini oynakligin <katsayi> kati
    kadar asarsa gir; ortalamanin altina inerse cik.
    """
    ortalama = df["kapanis"].rolling(periyot).mean()
    a = atr(df, periyot)
    return giris_cikis_pozisyon(df["kapanis"] > ortalama + katsayi * a,
                                df["kapanis"] < ortalama)


# ============================================================
#  TEST EDILECEK LISTE
# ============================================================
# (isim, fonksiyon, parametreler)
#
# Her aileden birkac ayar var. Ayni ailenin farkli ayarlari benzer
# sonuc veriyorsa o bulgu saglamdir; cok farkli sonuc veriyorsa
# o aile sadece sansa oynuyor demektir.

STRATEJILER = [
    ("al ve tut",            al_ve_tut,             {}),

    ("SMA trend 50",         sma_trend,             {"periyot": 50}),
    ("SMA trend 100",        sma_trend,             {"periyot": 100}),
    ("SMA trend 200",        sma_trend,             {"periyot": 200}),

    ("MA kesisme 20/100",    ma_kesisme,            {"hizli": 20, "yavas": 100}),
    ("MA kesisme 50/200",    ma_kesisme,            {"hizli": 50, "yavas": 200}),

    ("Donchian 55/20",       donchian_kirilma,      {"giris_periyot": 55, "cikis_periyot": 20}),
    ("Donchian 20/10",       donchian_kirilma,      {"giris_periyot": 20, "cikis_periyot": 10}),

    ("MACD",                 macd_trend,            {}),

    ("Momentum 90",          momentum,              {"periyot": 90}),
    ("Momentum 180",         momentum,              {"periyot": 180}),

    ("RSI 30/60",            rsi_geri_donus,        {"alt": 30, "ust": 60}),
    ("RSI 20/50",            rsi_geri_donus,        {"alt": 20, "ust": 50}),

    ("Bollinger 20/2",       bollinger_geri_donus,  {"periyot": 20, "katsayi": 2.0}),

    ("Dusuk oynaklik",       dusuk_oynaklik,        {}),
    ("ATR kirilma",          atr_kirilma,           {}),
]


def isinma_suresi(isim, parametreler):
    """
    Bir stratejinin karar verebilmesi icin kac mum gecmesi gerekir?
    Test bolumunu dogru kurmak icin bu sayiyi bilmemiz sart.
    """
    en_uzun = 1
    for deger in parametreler.values():
        if isinstance(deger, (int, float)) and deger > en_uzun:
            en_uzun = int(deger)
    if "oynaklik" in isim.lower():
        en_uzun = max(en_uzun, 365)
    return en_uzun + 5
