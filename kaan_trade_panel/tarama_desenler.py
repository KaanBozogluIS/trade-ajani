r"""
DESEN STRATEJILERI DOGRULAMA
=============================

tarama.py'nin AYNI rastgele-kontrol-grubu yontemiyle, YENI desen tabanli
stratejileri (SFP, Order Block, Fair Value Gap, Destek/Direnc kirilmasi --
bkz. strateji_desenleri.py) olcer.

Bu ayri bir dosya, cunku tarama.py mevcut 16 stratejiyi test eden, zaten
calisan/belgelenen bir arac -- onu bozmadan, AYNI olcum motorunu
(veriyi_topla, rastgele_dagilim, olc, yuzdelik fonksiyonlari) buradan
tekrar kullanarak yeni adaylari test ediyoruz.

NEDEN GEREKLI: sanal_trader.py bu desenleri canli rotasyon motoruna aday
olarak eklemeden ONCE, ayni sikilikta olculmeleri sart -- projenin en
temel ilkesi budur (bkz. README.md, tarama.py). Sonuc olumsuz cikarsa
(rastgeleyi gecemezlerse) bu da oldugu gibi rapor edilir, gizlenmez.

Calistirmak icin:
    .\.venv\Scripts\python.exe tarama_desenler.py
"""

import statistics
import sys

from strateji_desenleri import DESEN_STRATEJILERI
from strateji_desenleri import isinma_suresi as desen_isinma_suresi
from tarama import AYARLAR, dusus_yuzdelik, olc, rastgele_dagilim, veriyi_topla, yuzdelik

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    a = dict(AYARLAR)

    print()
    print("#" * 100)
    print("  DESEN STRATEJILERI DOGRULAMASI")
    print(f"  {len(a['coinler'])} coin  |  {len(DESEN_STRATEJILERI)} desen stratejisi  |  "
          f"{a['zaman_dilimi']} mumlar  |  ~{a['kac_gun'] // 365} yil")
    print(f"  Egitim = ilk %{int((1 - a['test_orani']) * 100)}   "
          f"TEST = son %{int(a['test_orani'] * 100)} (hicbir secim bu bolume bakilarak yapilmadi)")
    print("#" * 100)

    veriler = veriyi_topla(a)
    if not veriler:
        print("Hic veri alinamadi.")
        return

    rast_getiri, rast_dusus, rast_yenen = rastgele_dagilim(veriler, a)
    rast_medyan = statistics.median(rast_getiri)
    rast_dusus_medyan = statistics.median(rast_dusus)

    print("[i] Desen stratejileri olculuyor...\n")
    satirlar = []
    for isim, fonksiyon, parametreler in DESEN_STRATEJILERI:
        isinma = desen_isinma_suresi(isim, parametreler)
        testler, dususler, turlar, piyasada = [], [], [], []
        altut_yenen, gecerli = 0, 0
        for df in veriler.values():
            e, t = olc(df, fonksiyon, parametreler, isinma, a)
            if not e or not t:
                continue
            gecerli += 1
            testler.append(t["getiri"])
            dususler.append(t["dusus"])
            turlar.append(t["tur"])
            piyasada.append(t["piyasada"])
            if t["getiri"] > t["al_tut_getiri"]:
                altut_yenen += 1
        if gecerli < 3:
            print(f"  [!] {isim}: yeterli coinde gecerli sonuc yok ({gecerli}), atlandi")
            continue
        satirlar.append({
            "isim": isim,
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

    print("=" * 100)
    print("  SONUCLAR  (butun coinlerin ORTA degeri, sadece TEST bolumu)")
    print("  Parantez icindeki sayilar: rastgelenin yuzde kacini gecti")
    print("=" * 100)
    print(f"  {'strateji':<28}{'TEST getiri':>17}{'TEST dusus':>17}"
          f"{'al-tut yenen':>17}{'islem':>7}{'piyasada':>10}")
    print("  " + "-" * 96)
    for r in satirlar:
        print(f"  {r['isim']:<28}"
              f"{r['test']:>10.1f}% ({r['y_getiri']:>3.0f}%)"
              f"{r['dusus']:>10.1f}% ({r['y_dusus']:>3.0f}%)"
              f"{str(r['altut']) + '/' + str(r['gecerli']):>10} ({r['y_altut']:>3.0f}%)"
              f"{r['tur']:>7.0f}{r['piyasada']:>9.0f}%")
    print("  " + "-" * 96)
    print(f"  {'RASTGELE (kontrol)':<28}{rast_medyan:>10.1f}%{'':>7}{rast_dusus_medyan:>10.1f}%")
    print("=" * 100)

    gecen = [r for r in satirlar if r["y_getiri"] >= 95]
    dusus_gecen = [r for r in satirlar if r["y_dusus"] >= 95 and r["piyasada"] >= 25.0]
    print()
    print("  KARAR")
    print("  " + "-" * 96)
    print(f"  Getiride rastgele esigini (%95) gecen: {', '.join(r['isim'] for r in gecen) or 'YOK'}")
    print(f"  Dususu azaltmada rastgele esigini gecen: {', '.join(r['isim'] for r in dusus_gecen) or 'YOK'}")
    print()


if __name__ == "__main__":
    main()
