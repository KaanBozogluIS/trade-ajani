r"""
DESEN TABANLI STRATEJILER
=========================

desenler.py'deki HAM geometriyi (swing noktalari, order block, fair value
gap) ve analiz_botu.py'deki likidite avi (SFP) fikrini, stratejiler.py'nin
POZISYON kalibina (her mum icin 1.0 = pozisyondayim, 0.0 = nakitteyim,
NaN = henuz karar veremem) cevirir. Boylece bu desenler de dogrulama.py /
tarama.py'nin AYNI olcum motoruna, mevcut 16 stratejiyle YAN YANA girebilir.

ONEMLI -- ILERI BAKIS (lookahead) OLMASIN DIYE:
    Bir "swing" noktasi ancak kendisinden <pencere> mum SONRASI da
    goruldukten sonra "onaylanir" (desenler.swing_noktalari'nin kendi
    tanimi geregi). Asagidaki fonksiyonlar i. mumda karar verirken SADECE
    o ana kadar (gelecegi bilmeden) GERCEKTEN onaylanmis olabilecek
    bilgiyi kullanir. Bu, gecmis testinin (backtest) gecerli sayilmasi
    icin sart -- aksi halde "gelecegi bilerek" yapay bir basari
    gorunumu olusur.

BU DOSYA DA STRATEJILER.PY'YE BAGIMLI DEGIL, TERSI DE DEGIL -- ikisi de
sadece desenler.py'yi (ya da hic bir seyi) kullanir; boylece dongusel
import (circular import) riski yok.

LONG-ONLY: bot.py / sanal_trader.py gibi, bu stratejiler de sadece
"coinde miyim, nakitte miyim" kararı verir -- kisa (short) pozisyon
yoktur. O yuzden sadece BOGA (yukari yonlu) desenler islem sinyaline
cevrilir; ayi desenler (varsa) sadece "pozisyondan cik" anlaminda
kullanilir, "kisa ac" anlaminda degil.

DURUSTLUK NOTU: Bu stratejilerin gercekten ise yarayip yaramadigi
BURADA VARSAYILMAZ -- tarama.py ile, mevcut 16 stratejiyle AYNI
rastgele-kontrol-grubu yontemiyle olculur (bkz. README.md, "Sanal
Trader" bolumu). Sonuc olumsuz cikarsa bu da oldugu gibi raporlanir.
"""

import bisect

import numpy as np
import pandas as pd

from desenler import swing_noktalari


def _basit_atr(yuksek, dusuk, kapanis, periyot=14):
    """
    desenler.order_block_bolgeleri ile AYNI basit ATR hesabi -- bu
    dosya stratejiler.py'ye bagimli olmasin diye kucuk bir kopyasi
    burada da duruyor (mantik ayni: gercek aralik + kayan ortalama).
    """
    n = len(kapanis)
    if n == 0:
        return []
    gercek_araliklar = [yuksek[0] - dusuk[0]]
    for i in range(1, n):
        gercek_araliklar.append(max(
            yuksek[i] - dusuk[i],
            abs(yuksek[i] - kapanis[i - 1]),
            abs(dusuk[i] - kapanis[i - 1]),
        ))
    atr = []
    for i in range(n):
        pencere = gercek_araliklar[max(0, i - periyot + 1):i + 1]
        atr.append(sum(pencere) / len(pencere))
    return atr


# ============================================================
#  1) LIKIDITE AVI (SFP) STRATEJISI
# ============================================================

def sfp_stratejisi(df, pencere=3, hacim_esigi=1.5, esik_ust=15.0, tutma_suresi=10):
    """
    Boga likidite avi (SFP) sinyali geldiginde uzun pozisyona girer;
    <tutma_suresi> mum sonra ya da fiyat supurulen dip seviyesinin
    ALTINA kapanarak sinyali gecersiz kilarsa (hangisi once gelirse)
    cikar.
    """
    n = len(df)
    if n < 2 * pencere + 15:
        return pd.Series(np.nan, index=df.index)

    yuksek = df["yuksek"].tolist()
    dusuk = df["dusuk"].tolist()
    kapanis = df["kapanis"].tolist()
    hacim = df["hacim"].tolist()

    _, dip_idx_all = swing_noktalari(dusuk, pencere)

    esik = 0.0002
    pozisyonlar = [float("nan")] * n
    icinde = False
    giris_index = None
    giris_dip_seviyesi = None
    isinma = 2 * pencere + 15

    for i in range(isinma, n):
        if icinde:
            gecen = i - giris_index
            if gecen >= tutma_suresi or kapanis[i] < giris_dip_seviyesi:
                icinde = False
            pozisyonlar[i] = 1.0 if icinde else 0.0
            continue

        # Sadece i - pencere'den ONCE onaylanmis swing dipler bilinir
        # (gelecege bakmadan bu ana kadar gercekten bilinebilecek olan).
        sinir = i - pencere
        konum = bisect.bisect_left(dip_idx_all, sinir)
        if konum == 0:
            pozisyonlar[i] = 0.0
            continue
        dip_idx = dip_idx_all[konum - 1]
        dip_seviye = dusuk[dip_idx]
        if dip_seviye <= 0:
            pozisyonlar[i] = 0.0
            continue

        sarkma = (dip_seviye - dusuk[i]) / dip_seviye * 100
        supuruldu = dusuk[i] < dip_seviye * (1 - esik) and kapanis[i] > dip_seviye and sarkma <= esik_ust

        if supuruldu:
            ort_hacim = sum(hacim[max(0, i - 20):i]) / max(1, len(hacim[max(0, i - 20):i]))
            hacim_teyitli = ort_hacim > 0 and hacim[i] >= ort_hacim * hacim_esigi
            if hacim_teyitli:
                icinde = True
                giris_index = i
                giris_dip_seviyesi = dip_seviye

        pozisyonlar[i] = 1.0 if icinde else 0.0

    return pd.Series(pozisyonlar, index=df.index)


# ============================================================
#  2) ORDER BLOCK STRATEJISI
# ============================================================

def order_block_stratejisi(df, esik_katsayi=1.5, tutma_suresi=10):
    """
    Fiyat, en son olusan (henuz gecersiz kilinmamis) boga Order Block
    bolgesine donup USTUNE geri kapaninca ("reddedip") uzun pozisyona
    girer; bolgenin ALTINA kapanirsa (gecersiz) ya da <tutma_suresi>
    mum gecerse cikar.
    """
    n = len(df)
    if n < 20:
        return pd.Series(np.nan, index=df.index)

    acilis = df["acilis"].tolist()
    yuksek = df["yuksek"].tolist()
    dusuk = df["dusuk"].tolist()
    kapanis = df["kapanis"].tolist()
    atr = _basit_atr(yuksek, dusuk, kapanis)

    pozisyonlar = [float("nan")] * n
    icinde = False
    giris_index = None
    giris_bolgesi = None
    aktif_bolge = None  # (alt, ust) -- en son olusan, henuz test/gecersiz olmamis

    for i in range(15, n):
        if icinde:
            gecen = i - giris_index
            if gecen >= tutma_suresi or kapanis[i] < giris_bolgesi[0]:
                icinde = False
            pozisyonlar[i] = 1.0 if icinde else 0.0
            continue

        # 1) ONCE mevcut (onceki bardan kalma) aktif bolgeyi test et --
        #    boylece bir bolge, olustugu barin KENDISINDE degil, ancak
        #    SONRAKI bir barda test edilebilir (ayni bar sizintisi yok).
        if aktif_bolge is not None:
            alt, ust = aktif_bolge
            if dusuk[i] < alt:
                aktif_bolge = None
            elif dusuk[i] <= ust and kapanis[i] > ust:
                icinde = True
                giris_index = i
                giris_bolgesi = aktif_bolge
                aktif_bolge = None

        # 2) SONRA bu barin yeni bir OB olusturup olusturmadigina bak
        #    (gelecek barlar icin -- bu barin kendisi icin degil).
        govde_onceki = kapanis[i - 1] - acilis[i - 1]
        govde_simdi = kapanis[i] - acilis[i]
        if atr[i] > 0 and govde_onceki < 0 and govde_simdi > 0 \
                and abs(govde_simdi) >= esik_katsayi * atr[i] and kapanis[i] > yuksek[i - 1]:
            aktif_bolge = (min(acilis[i - 1], kapanis[i - 1]), max(acilis[i - 1], kapanis[i - 1]))

        pozisyonlar[i] = 1.0 if icinde else 0.0

    return pd.Series(pozisyonlar, index=df.index)


# ============================================================
#  3) FAIR VALUE GAP STRATEJISI
# ============================================================

def fair_value_gap_stratejisi(df, tutma_suresi=10):
    """
    Fiyat, en son olusan (henuz doldurulmamis) boga FVG bolgesine
    donup KISMEN doldurup ustunde kapaninca ("reddedip") uzun
    pozisyona girer; bolgenin ALT sinirinin altina kapanirsa (tam
    gecersiz) ya da <tutma_suresi> mum gecerse cikar.
    """
    n = len(df)
    if n < 5:
        return pd.Series(np.nan, index=df.index)

    yuksek = df["yuksek"].tolist()
    dusuk = df["dusuk"].tolist()
    kapanis = df["kapanis"].tolist()

    pozisyonlar = [float("nan")] * n
    icinde = False
    giris_index = None
    giris_bolgesi = None
    aktif_bolge = None

    for i in range(3, n):
        if icinde:
            gecen = i - giris_index
            if gecen >= tutma_suresi or kapanis[i] < giris_bolgesi[0]:
                icinde = False
            pozisyonlar[i] = 1.0 if icinde else 0.0
            continue

        # 1) ONCE mevcut (onceki bardan kalma) aktif bolgeyi test et.
        if aktif_bolge is not None:
            alt, ust = aktif_bolge
            if dusuk[i] < alt:
                aktif_bolge = None
            elif dusuk[i] <= ust and kapanis[i] > alt:
                icinde = True
                giris_index = i
                giris_bolgesi = aktif_bolge
                aktif_bolge = None

        # 2) SONRA bu bar (i-2, i-1, i uclusu) yeni bir FVG olusturuyor mu?
        onceki_yuksek, onceki_dusuk = yuksek[i - 2], dusuk[i - 2]
        if onceki_yuksek < dusuk[i]:
            aktif_bolge = (onceki_yuksek, dusuk[i])

        pozisyonlar[i] = 1.0 if icinde else 0.0

    return pd.Series(pozisyonlar, index=df.index)


# ============================================================
#  4) DESTEK/DIRENC KIRILMASI (swing tabanli)
# ============================================================

def destek_direnc_kirilma(df, pencere=3):
    """
    Fiyat en son onaylanmis swing DIRENC (tepe) seviyesini kapanista
    kirinca gir; en son onaylanmis swing DESTEK (dip) seviyesinin
    altina kapaninca cik.

    Mevcut "Donchian kirilma" stratejisinden (stratejiler.py) farki:
    rolling max/min yerine _swing_noktalari ile bulunan "anlamli"
    fraktal seviyeleri kullanir -- daha az ama (iddiaya gore) daha
    "onemli" seviyeler.
    """
    n = len(df)
    if n < 2 * pencere + 15:
        return pd.Series(np.nan, index=df.index)

    yuksek = df["yuksek"].tolist()
    dusuk = df["dusuk"].tolist()
    kapanis = df["kapanis"].tolist()

    tepe_idx_all, _ = swing_noktalari(yuksek, pencere)
    _, dip_idx_all = swing_noktalari(dusuk, pencere)

    pozisyonlar = [float("nan")] * n
    icinde = False
    isinma = 2 * pencere + 15

    for i in range(isinma, n):
        sinir = i - pencere
        konum_t = bisect.bisect_left(tepe_idx_all, sinir)
        konum_d = bisect.bisect_left(dip_idx_all, sinir)
        if konum_t == 0 or konum_d == 0:
            pozisyonlar[i] = 0.0
            continue
        direnc = yuksek[tepe_idx_all[konum_t - 1]]
        destek = dusuk[dip_idx_all[konum_d - 1]]

        if not icinde and kapanis[i] > direnc:
            icinde = True
        elif icinde and kapanis[i] < destek:
            icinde = False

        pozisyonlar[i] = 1.0 if icinde else 0.0

    return pd.Series(pozisyonlar, index=df.index)


# ============================================================
#  TEST EDILECEK LISTE  (tarama.py / sanal_trader.py buradan okur)
# ============================================================

DESEN_STRATEJILERI = [
    ("SFP (likidite avi)",       sfp_stratejisi,          {}),
    ("Order Block",              order_block_stratejisi,  {}),
    ("Fair Value Gap",           fair_value_gap_stratejisi, {}),
    ("Destek/Direnc kirilmasi",  destek_direnc_kirilma,   {}),
]


def isinma_suresi(isim, parametreler):
    """stratejiler.isinma_suresi ile ayni fikir; bu dosya bagimsiz kalsin
    diye kucuk bir kopyasi -- desen stratejilerinin hepsi ~20-30 mumda
    isinir, sabit bir deger yeterli."""
    return 30
