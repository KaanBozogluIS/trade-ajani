r"""
DESENLER  (grafik-okuma desenleri: swing noktalari, order block, fair value gap)
==================================================================================

Bu dosya SADECE GEOMETRI icerir -- bir insanin grafige bakip elle
isaretleyecegi turden "burda bir bolge/seviye var" bilgisini kod olarak
uretir. Metin/yorum uretmez (bunu analiz_botu.py yapar), "al/sat" hic
demez.

NEDEN AYRI BIR DOSYA? Hem analiz_botu.py (tek coin icin okunur "gozlem"
kartlari uretmek icin) hem strateji_desenleri.py (coklu-coin backtest ve
sanal-trader icin surekli pozisyon serisi uretmek icin) AYNI ham
geometriye ihtiyac duyuyor. Ikisi arasinda dongusel import (circular
import) olmasin diye bu ortak, dusuk seviyeli katman burada duruyor --
analiz_botu.py da, strateji_desenleri.py da BURADAN import eder, birbirinden
degil.

DURUSTLUK NOTU: "Order Block" ve "Fair Value Gap" (Smart Money Concepts /
ICT camiasindan gelen terimler) icin TEK, evrensel kabul gormus bir tanim
YOK -- kaynaktan kaynaga onemli farklar var. Burada kullanilan tanimlar
yaygin anlatilan, makul birer versiyondur -- "ise yaradiklarinin kaniti"
DEGILDIR. tarama.py'de kanitladigimiz gibi (16 standart strateji rastgeleyi
gecemedi), "populer olmak" ile "kar getirmek" FARKLI seylerdir. Bu
desenlerin gercekten ise yarayip yaramadigi strateji_desenleri.py + tarama.py
ile AYRICA, olcerek belirlenir -- burada tanimlanmis olmalari bir onay
degildir.
"""


# ============================================================
#  SWING (FRAKTAL) NOKTALARI
# ============================================================
# analiz_botu.py'de _swing_noktalari adiyla tanimliydi; artik ortak
# oldugu icin buraya tasindi. Davranis AYNI -- sadece paylasilan hale
# geldi (destek/direnc, likidite avi, order block, fair value gap ve yeni
# destek/direnc kirilma stratejisi hepsi bunu kullaniyor).

def swing_noktalari(degerler, pencere=3):
    """
    Yerel tepe ve dip noktalarini bulur (basit "fraktal" yontemi):
    bir nokta, kendisinden once ve sonraki <pencere> nokta icinde
    en yuksek/en dusukse "swing" sayilir.
    """
    n = len(degerler)
    tepe_idx, dip_idx = [], []
    for i in range(pencere, n - pencere):
        dilim = degerler[i - pencere:i + pencere + 1]
        if degerler[i] == max(dilim):
            tepe_idx.append(i)
        if degerler[i] == min(dilim):
            dip_idx.append(i)
    return tepe_idx, dip_idx


# ============================================================
#  FAIR VALUE GAP (FVG)  --  3 mumluk fiyat dengesizligi
# ============================================================
#
# FIKIR: guclu, tek yonlu bir hareket sirasinda orta mum o kadar buyuk
# olur ki, ondan onceki ve sonraki mumlarin fitilleri bile CAKISMAZ --
# aralarinda kimsenin islem yapmadigi bos bir fiyat araligi kalir.
# Bazi analistler bu "bosluk"un, ozellikle kurumsal emirlerin fiyati
# "verimsiz" biraktigi bir bolge oldugunu ve fiyatin er ya da gec buraya
# donup "doldurdugunu" iddia eder.
#
# TANIM (burada kullanilan, yaygin versiyon):
#   BOGA FVG : mum[i-1].yuksek < mum[i+1].dusuk
#              -> bosluk = [mum[i-1].yuksek, mum[i+1].dusuk]
#   AYI  FVG : mum[i-1].dusuk  > mum[i+1].yuksek
#              -> bosluk = [mum[i+1].yuksek, mum[i-1].dusuk]
# "DOLDURULDU" (aktif degil): sonraki bir mumun fiyati bosluğun
# TAMAMINDAN gecip diger uca ulasti -- yani bosluk tamamen "kapandi".

def fair_value_gap_bolgeleri(df, bakilan=150):
    """
    Ekrandaki son <bakilan> mum icinde FVG bolgelerini bulur.

    Donen: [{"tur": "boga"|"ayi", "alt": float, "ust": float,
             "olusum_index": int, "aktif": bool}, ...]
    "aktif" = bolge henuz (kismen bile olsa) doldurulmadi.
    """
    n = len(df)
    if n < 3:
        return []
    baslangic = max(1, n - bakilan)
    yuksek = df["yuksek"].tolist()
    dusuk = df["dusuk"].tolist()

    bolgeler = []
    for i in range(baslangic, n - 1):
        onceki_yuksek, onceki_dusuk = yuksek[i - 1], dusuk[i - 1]
        sonraki_yuksek, sonraki_dusuk = yuksek[i + 1], dusuk[i + 1]

        if onceki_yuksek < sonraki_dusuk:
            alt, ust, tur = onceki_yuksek, sonraki_dusuk, "boga"
        elif onceki_dusuk > sonraki_yuksek:
            alt, ust, tur = sonraki_yuksek, onceki_dusuk, "ayi"
        else:
            continue

        # Doldu mu? Bolgeden SONRAKI mumlara bak (i+2'den itibaren).
        dolduruldu = False
        for j in range(i + 2, n):
            if tur == "boga" and dusuk[j] <= alt:
                dolduruldu = True
                break
            if tur == "ayi" and yuksek[j] >= ust:
                dolduruldu = True
                break

        bolgeler.append({
            "tur": tur, "alt": float(alt), "ust": float(ust),
            "olusum_index": i, "aktif": not dolduruldu,
        })
    return bolgeler


# ============================================================
#  ORDER BLOCK (OB)  --  guclu harekettin baslangic noktasi
# ============================================================
#
# FIKIR: buyuk (kurumsal) emirlerin, fiyati agirlikli olarak TERS
# yondeki son mumda biriktirdigi, sonra fiyati kendi yonune "firlattigi"
# varsayilir. O yuzden guclu bir yukselisten hemen ONCEKI son dusus
# mumu (ya da tam tersi), "buyuk oyuncularin durdugu yer" sayilir.
#
# TANIM (burada kullanilan, yaygin versiyon):
#   BOGA OB: mum[i] DUSUS mumu (kapanis < acilis) VE mum[i+1] GUCLU
#            YUKSELIS mumu -- govdesi ATR'nin esik_katsayi kati kadar
#            buyuk VE kapanisi mum[i]'nin YUKSEGINI kiriyor (yapisal
#            kirilim). Bolge = mum[i]'nin govdesi (kapanis..acilis).
#   AYI  OB: simetrik (yukselis mumu + guclu dusus impulsu).
# "GECERSIZ" (aktif degil): sonraki bir mumun KAPANISI, boga OB icin
# bolgenin ALTINA, ayi OB icin bolgenin USTUNE gecti -- yani "buyuk
# oyuncunun durdugu yer" fiyatla asildi, artik guvenilir sayilmaz.

def order_block_bolgeleri(df, bakilan=150, esik_katsayi=1.5):
    """
    Ekrandaki son <bakilan> mum icinde Order Block bolgelerini bulur.
    ATR icin basit bir "gercek aralik" hesabi kullanir (stratejiler.py'deki
    atr() ile ayni fikir, ama bu modul stratejiler.py'ye bagimli olmasin
    diye burada ayrica, kisaca hesaplaniyor).

    Donen: [{"tur": "boga"|"ayi", "alt": float, "ust": float,
             "olusum_index": int, "aktif": bool}, ...]
    """
    n = len(df)
    if n < 20:
        return []
    baslangic = max(15, n - bakilan)
    acilis = df["acilis"].tolist()
    yuksek = df["yuksek"].tolist()
    dusuk = df["dusuk"].tolist()
    kapanis = df["kapanis"].tolist()

    # Basit ATR (14 periyot, kayan ortalama -- ewm degil, bu modulun
    # pandas disi kalmasi onemli degil ama hesap sade kalsin diye).
    gercek_araliklar = [yuksek[0] - dusuk[0]]
    for i in range(1, n):
        gercek_araliklar.append(max(
            yuksek[i] - dusuk[i],
            abs(yuksek[i] - kapanis[i - 1]),
            abs(dusuk[i] - kapanis[i - 1]),
        ))
    atr = []
    for i in range(n):
        pencere = gercek_araliklar[max(0, i - 13):i + 1]
        atr.append(sum(pencere) / len(pencere))

    bolgeler = []
    for i in range(baslangic, n - 1):
        govde_i = kapanis[i] - acilis[i]
        govde_sonraki = kapanis[i + 1] - acilis[i + 1]
        if atr[i + 1] <= 0:
            continue
        guclu = abs(govde_sonraki) >= esik_katsayi * atr[i + 1]

        if govde_i < 0 and govde_sonraki > 0 and guclu and kapanis[i + 1] > yuksek[i]:
            alt, ust, tur = min(acilis[i], kapanis[i]), max(acilis[i], kapanis[i]), "boga"
        elif govde_i > 0 and govde_sonraki < 0 and guclu and kapanis[i + 1] < dusuk[i]:
            alt, ust, tur = min(acilis[i], kapanis[i]), max(acilis[i], kapanis[i]), "ayi"
        else:
            continue

        gecersiz = False
        for j in range(i + 2, n):
            if tur == "boga" and kapanis[j] < alt:
                gecersiz = True
                break
            if tur == "ayi" and kapanis[j] > ust:
                gecersiz = True
                break

        bolgeler.append({
            "tur": tur, "alt": float(alt), "ust": float(ust),
            "olusum_index": i, "aktif": not gecersiz,
        })
    return bolgeler
