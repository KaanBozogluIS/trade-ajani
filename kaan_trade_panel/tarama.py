r"""
STRATEJI TARAMA MOTORU
======================

Butun stratejileri, butun coinlerde, ayni anda test eder ve tek bir
tabloda karsilastirir.

BU DOSYANIN ASIL FIKRI:
    "Hangi strateji iyi?" sorusunun cevabi bir listede yazili degildir.
    Olculur. Ve olcerken en kritik sey bir KONTROL GRUBU kullanmaktir.

    Buraya para atarak karar veren "rastgele" bir strateji de katiliyor.
    30 farkli rastgele deneme yapiyoruz ve bir dagilim elde ediyoruz.
    Sonra her gercek stratejiye soruyoruz:
        "Sen bu dagilimin neresindesin?"

    Eger bir strateji rastgelenin ortasinda duruyorsa, o strateji
    hicbir sey bilmiyor -- sadece sansli ya da sanssiz cikmis.

Calistirmak icin:
    .\.venv\Scripts\python.exe tarama.py
"""

import statistics
import sys

from dogrulama import simule_et
from stratejiler import STRATEJILER, isinma_suresi, rastgele
from veri_indir import veri_al

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


AYARLAR = {
    "borsa": "binance",
    "coinler": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT",
                "SOL/USDT", "DOGE/USDT", "LTC/USDT", "LINK/USDT", "AVAX/USDT"],
    "zaman_dilimi": "1d",
    "kac_gun": 2200,              # ~6 yil: 2021 yukselisi de dahil olsun
    "baslangic_bakiye": 1000.0,
    "islem_ucreti_yuzde": 0.1,
    "islem_orani": 0.95,
    "test_orani": 0.30,
    "rastgele_deneme": 200,       # kontrol grubu kac kez denenecek
    "en_az_mum": 400,             # bundan kisa gecmisi olan coini atla
}


# ============================================================
#  TEK BIR STRATEJIYI TEK BIR COINDE OLC
# ============================================================

def olc(gunluk, fonksiyon, parametreler, isinma, a):
    """
    Stratejiyi hem egitim hem test bolumunde calistirir.
    Test bolumunde gostergenin isinmasi icin oncesinden mum ekler,
    ama islemleri sadece test doneminde sayar.
    """
    ayirma = int(len(gunluk) * (1 - a["test_orani"]))
    if ayirma < isinma + 30 or len(gunluk) - ayirma < 60:
        return None, None

    egitim = gunluk.iloc[:ayirma].reset_index(drop=True)
    e = simule_et(egitim, fonksiyon(egitim, **parametreler), a)

    bas = max(0, ayirma - isinma)
    dilim = gunluk.iloc[bas:].reset_index(drop=True)
    t = simule_et(dilim, fonksiyon(dilim, **parametreler), a,
                  baslangic=ayirma - bas)
    return e, t


# ============================================================
#  ANA TARAMA
# ============================================================

def veriyi_topla(a):
    """Butun coinlerin gunluk verisini indirir / diskten okur."""
    veriler = {}
    for sembol in a["coinler"]:
        try:
            df = veri_al(a["borsa"], sembol, a["zaman_dilimi"], a["kac_gun"])
        except Exception as e:
            print(f"  [!] {sembol} atlandi: {str(e)[:70]}")
            continue
        if len(df) < a["en_az_mum"]:
            print(f"  [!] {sembol} atlandi: gecmisi cok kisa ({len(df)} mum)")
            continue
        veriler[sembol] = df
    return veriler


def rastgele_dagilim(veriler, a):
    """
    Kontrol grubu: cok sayida kez para atarak karar veren strateji.

    Her deneme icin UC sayi hesapliyoruz:
      * butun coinlerin orta (medyan) getirisi
      * butun coinlerin orta dususu
      * kac coinde al-ve-tut'u gecti

    Boylece her olcut icin ayri bir "sans dagilimi" elde ediyoruz.

    NEDEN COK DENEME? 30 deneme ile en ince ayrim %3.3 olur, bu da %95
    esigini olcmeye yetmez. 200 deneme ile cozunurluk %0.5'e iner.
    """
    n = a["rastgele_deneme"]
    print(f"\n[i] Kontrol grubu calistiriliyor: {n} rastgele deneme...")
    medyanlar, dususler, yenenler = [], [], []
    for tohum in range(n):
        if tohum % 50 == 0 and tohum:
            print(f"    {tohum}/{n}...", end="\r")
        getiriler, coin_dususleri, yenen = [], [], 0
        for df in veriler.values():
            _, t = olc(df, rastgele, {"tohum": tohum}, 5, a)
            if t:
                getiriler.append(t["getiri"])
                coin_dususleri.append(t["dusus"])
                if t["getiri"] > t["al_tut_getiri"]:
                    yenen += 1
        if getiriler:
            medyanlar.append(statistics.median(getiriler))
            dususler.append(statistics.median(coin_dususleri))
            yenenler.append(yenen)
    print("    " + " " * 20, end="\r")
    return sorted(medyanlar), sorted(dususler), sorted(yenenler)


def yuzdelik(dagilim, deger):
    """Deger, dagilimin yuzde kacindan daha iyi?"""
    if not dagilim:
        return 0.0
    return sum(1 for d in dagilim if d < deger) / len(dagilim) * 100


def dusus_yuzdelik(dagilim, deger):
    """Dususte 'iyi' daha kucuk kayip demek, o yuzden yon ters."""
    if not dagilim:
        return 0.0
    return sum(1 for d in dagilim if d < deger) / len(dagilim) * 100


def main():
    a = AYARLAR

    print()
    print("#" * 100)
    print("  STRATEJI TARAMASI")
    print(f"  {len(a['coinler'])} coin  |  {len(STRATEJILER)} strateji  |  "
          f"{a['zaman_dilimi']} mumlar  |  ~{a['kac_gun'] // 365} yil")
    print(f"  Egitim = ilk %{int((1 - a['test_orani']) * 100)}   "
          f"TEST = son %{int(a['test_orani'] * 100)} (hicbir secim bu bolume bakilarak yapilmadi)")
    print("#" * 100)

    veriler = veriyi_topla(a)
    if not veriler:
        print("Hic veri alinamadi.")
        return

    ilk = next(iter(veriler.values()))
    print(f"\n[i] {len(veriler)} coin hazir. Ornek aralik "
          f"({next(iter(veriler))}): {ilk['zaman'].iloc[0]:%Y-%m-%d} / "
          f"{ilk['zaman'].iloc[-1]:%Y-%m-%d}  ({len(ilk):,} gun)")

    rast_getiri, rast_dusus, rast_yenen = rastgele_dagilim(veriler, a)
    rast_medyan = statistics.median(rast_getiri)
    rast_en_iyi = rast_getiri[-1]
    rast_dusus_medyan = statistics.median(rast_dusus)
    rast_yenen_medyan = statistics.median(rast_yenen)

    # --- Her stratejiyi olc --------------------------------
    print("[i] Stratejiler olculuyor...\n")
    satirlar = []
    for isim, fonksiyon, parametreler in STRATEJILER:
        isinma = isinma_suresi(isim, parametreler)
        egitimler, testler, dususler, turlar, piyasada = [], [], [], [], []
        altut_yenen, gecerli = 0, 0
        for df in veriler.values():
            e, t = olc(df, fonksiyon, parametreler, isinma, a)
            if not e or not t:
                continue
            gecerli += 1
            egitimler.append(e["getiri"])
            testler.append(t["getiri"])
            dususler.append(t["dusus"])
            turlar.append(t["tur"])
            piyasada.append(t["piyasada"])
            if t["getiri"] > t["al_tut_getiri"]:
                altut_yenen += 1
        if gecerli < 3:
            continue
        satirlar.append({
            "isim": isim,
            "egitim": statistics.median(egitimler),
            "test": statistics.median(testler),
            "dusus": statistics.median(dususler),
            "tur": statistics.median(turlar),
            "piyasada": statistics.median(piyasada),
            "altut": altut_yenen,
            "gecerli": gecerli,
            "y_getiri": yuzdelik(rast_getiri, statistics.median(testler)),
            "y_dusus": dusus_yuzdelik(rast_dusus, statistics.median(dususler)),
            "y_altut": yuzdelik(rast_yenen, altut_yenen),
        })

    satirlar.sort(key=lambda r: r["test"], reverse=True)

    # --- Tablo --------------------------------------------
    print("=" * 100)
    print("  SONUCLAR  (butun coinlerin ORTA degeri, sadece TEST bolumu)")
    print("  Parantez icindeki sayilar: rastgelenin yuzde kacini gecti")
    print("=" * 100)
    print(f"  {'strateji':<20}{'egitim':>8}{'TEST getiri':>17}"
          f"{'TEST dusus':>17}{'al-tut yenen':>17}{'islem':>7}{'piyasada':>10}")
    print("  " + "-" * 96)
    for r in satirlar:
        print(f"  {r['isim']:<20}{r['egitim']:>7.0f}%"
              f"{r['test']:>10.1f}% ({r['y_getiri']:>3.0f}%)"
              f"{r['dusus']:>10.1f}% ({r['y_dusus']:>3.0f}%)"
              f"{str(r['altut']) + '/' + str(r['gecerli']):>10} ({r['y_altut']:>3.0f}%)"
              f"{r['tur']:>7.0f}{r['piyasada']:>9.0f}%")

    # --- Kontrol grubu ------------------------------------
    print("  " + "-" * 96)
    print(f"  {'RASTGELE (kontrol)':<20}{'':>8}{rast_medyan:>10.1f}%"
          f"{'':>7}{rast_dusus_medyan:>10.1f}%{'':>7}{str(rast_yenen_medyan) + '/10':>10}"
          f"{'':>7}{'~50':>9}%")
    print(f"  {'  en iyi / en kotu':<20}{'':>8}"
          f"{rast_en_iyi:>10.1f}% / {rast_getiri[0]:.1f}%")
    print("=" * 100)

    # --- Yorum --------------------------------------------
    print()
    print("  NASIL OKUNUR")
    print("  " + "-" * 96)
    print(f"  * Parantez icindeki sayi: bu strateji {a['rastgele_deneme']} rastgele denemenin")
    print("    yuzde kacindan daha iyi? %50 demek 'tam ortada, hicbir sey bilmiyor'.")
    print("    Anlamli sayilmasi icin en az %95 olmasi gerekir -- bilimde kullanilan esik.")
    print()
    print("  * 'piyasada' sutununa MUTLAKA bakin. Neredeyse hic piyasaya girmeyen bir")
    print("    strateji dusus testini otomatik gecer -- nakitte oturmanin dususu yoktur.")
    print("    Bu bir yetenek degil, olcunun kandirilmasidir. Dusus bulgusunu ancak")
    print("    piyasada makul sure gecirmis stratejiler icin ciddiye alin.")
    print()
    print("  * 'egitim' ile 'TEST' arasindaki fark buyukse strateji gecmisi ezberlemis")
    print("    demektir. Iki sayinin birbirine YAKIN olmasi, yuksek olmasindan onemlidir.")
    print()
    print("  * Ayni ailenin farkli ayarlari (ornek SMA 50/100/200) benzer sonuc")
    print("    veriyorsa o bulgu saglamdir. Biri parlak digerleri kotuyse o parlak")
    print("    sayi tesaduftur.")
    print()
    print("  * Dusus sutunu getiriden daha guvenilirdir. Getiri donem sansina cok")
    print("    baglidir, dusus azalmasi ise stratejinin yapisindan gelir.")
    print("=" * 100)

    gercek = [r for r in satirlar if r["isim"] != "al ve tut"]
    getiri_gecen = [r for r in gercek if r["y_getiri"] >= 95]
    altut_gecen = [r for r in gercek if r["y_altut"] >= 95]

    # Dususte gecenleri iki gruba ayiriyoruz: piyasada makul sure gecirenler
    # ve neredeyse hic girmeyenler. Ikincisi olcuyu kandiriyor.
    EN_AZ_PIYASADA = 25.0
    dusus_gecen = [r for r in gercek
                   if r["y_dusus"] >= 95 and r["piyasada"] >= EN_AZ_PIYASADA]
    sahte_gecen = [r for r in gercek
                   if r["y_dusus"] >= 95 and r["piyasada"] < EN_AZ_PIYASADA]

    print()
    print("  KARAR")
    print("  " + "-" * 96)
    for etiket, liste in (("GETIRIDE", getiri_gecen),
                          ("DUSUS AZALTMADA", dusus_gecen),
                          ("AL-VE-TUT'U YENMEDE", altut_gecen)):
        if liste:
            print(f"  {etiket} rastgele esigini gecen: "
                  + ", ".join(r["isim"] for r in liste))
        else:
            print(f"  {etiket} rastgele esigini gecen: YOK")

    if sahte_gecen:
        print()
        for r in sahte_gecen:
            print(f"  [!] {r['isim']} dusus testini gecti ama piyasada sadece "
                  f"%{r['piyasada']:.0f} zaman")
            print(f"      gecirdi (medyan {r['tur']:.0f} islem). Yani neredeyse hep nakitte")
            print("      oturdu. Bu bir yetenek degil, olcunun kandirilmasi. SAYILMAZ.")
    print()
    if not getiri_gecen:
        print("  Getiri tarafinda hicbir strateji sansi yenemedi. Bu bir basarisizlik")
        print("  degil, olculen gercek: fiyat gecmisine bakarak gelecegi bilmek,")
        print("  herkesin ayni veriye baktigi bir piyasada zaten beklenmezdi.")
    if dusus_gecen:
        print("  Dusus tarafinda gecen stratejiler var. Bu daha inandirici bir bulgu,")
        print("  cunku dususu azaltmak icin gelecegi bilmek gerekmez -- sadece")
        print("  fiyat dusuyorken disarida beklemek gerekir. Bu bir KAR araci degil,")
        print("  bir RISK araci.")
    print()


if __name__ == "__main__":
    main()
