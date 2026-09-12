r"""
TRADE AJANI STRATEJI TARAMASI
==============================

tarama.py'deki AYNI olcum motorunu (rastgele-kontrol-grubu, %95 esik),
trade_ajani_stratejileri.py'deki 4 aktarilmis strateji icin calistirir.

NEDEN AYRI DOSYA: tarama.py'nin kendi AYARLAR'ini/STRATEJILER listesini
degistirmeden, aktarilan stratejileri AYNI olcumle sinamak icin. Ikisini
birlikte gormek isterseniz, tarama.py'nin STRATEJILER importuna bu
dosyadaki STRATEJILER'i EKLEYIN (birlestirin) - ya da bu dosyayi oldugu
gibi ayri calistirin.

ONEMLI KALIBRASYON NOTU: bu 4 strateji Trade-ajani'de 1 SAATLIK
mumlarda, cogunlukla ORTA/KUCUK cap ALTCOINLERDE (SEI, SHIB, FET, BICO,
WLD, ZKC, BMT, PENGU, ZEN - "Kirilim-GeriCekilme-Toparlanma" icin) ya da
belirli buyuk coinlerde (ETH, BNB - "Major Trend Surucusu" icin, 4 SAATLIK)
dogrulandi. Bu dosyanin varsayilan AYARLAR'i (1sa, birkac major coin)
sadece HIZLI bir tutarlilik kontrolu icindir - GERCEK dogrulama icin
`coinler` listesini Trade-ajani'nin kendi bulgularina gore ayarlayin
(bkz. TRADE_AJANI_BULGULARI.md).

Calistirmak icin:
    .\.venv\Scripts\python.exe trade_ajani_tarama.py
"""

import statistics
import sys

from tarama import olc, rastgele_dagilim, veriyi_topla, yuzdelik, dusus_yuzdelik
from trade_ajani_stratejileri import STRATEJILER, isinma_suresi

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


AYARLAR = {
    "borsa": "binance",
    # HIZLI kontrol icin birkac buyuk coin - GERCEK dogrulama icin
    # TRADE_AJANI_BULGULARI.md'deki altcoin listesini kullanin.
    "coinler": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "DOGE/USDT", "LINK/USDT"],
    "zaman_dilimi": "1h",
    "kac_gun": 400,
    "baslangic_bakiye": 1000.0,
    "islem_ucreti_yuzde": 0.1,
    "islem_orani": 0.95,
    "test_orani": 0.30,
    "rastgele_deneme": 100,
    "en_az_mum": 400,
}


def main():
    a = AYARLAR
    print(f"[i] Trade Ajani stratejileri taramasi: {len(a['coinler'])} coin, "
          f"{a['zaman_dilimi']}, {len(STRATEJILER)} strateji\n")

    veriler = veriyi_topla(a)
    if not veriler:
        print("Veri alinamadi.")
        return

    rast_getiri, rast_dusus, rast_yenen = rastgele_dagilim(veriler, a)

    print("\n" + "=" * 100)
    print(f"  {'strateji':<35}{'egitim':>8}{'TEST getiri':>17}{'TEST dusus':>17}"
          f"{'al-tut yenen':>15}{'islem':>7}{'piyasada':>10}")
    print("  " + "-" * 96)
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
        if gecerli < 2:
            print(f"  {isim:<35} yetersiz veri ({gecerli} coin)")
            continue
        test_medyan = statistics.median(testler)
        dusus_medyan = statistics.median(dususler)
        print(f"  {isim:<35}{statistics.median(egitimler):>7.0f}%"
              f"{test_medyan:>10.1f}% ({yuzdelik(rast_getiri, test_medyan):>3.0f}%)"
              f"{dusus_medyan:>10.1f}% ({dusus_yuzdelik(rast_dusus, dusus_medyan):>3.0f}%)"
              f"{str(altut_yenen)+'/'+str(gecerli):>9} ({yuzdelik(rast_yenen, altut_yenen):>3.0f}%)"
              f"{statistics.median(turlar):>7.0f}{statistics.median(piyasada):>9.0f}%")
    print("  " + "-" * 96)
    print(f"  {'RASTGELE (kontrol)':<35}{'':>8}{statistics.median(rast_getiri):>10.1f}%"
          f"{'':>7}{statistics.median(rast_dusus):>10.1f}%")
    print("=" * 100)
    print("\n  Parantez icindeki %95+ = kaan-trade'in kendi anlamlilik esigini geciyor.")
    print("  UYARI: yukaridaki varsayilan coin listesi (BTC/ETH/BNB/SOL/DOGE/LINK) bu")
    print("  stratejilerin Trade-ajani'de dogrulandigi evrenle (cogunlukla altcoin,")
    print("  bkz. TRADE_AJANI_BULGULARI.md) AYNI DEGIL - burasi hizli bir tutarlilik")
    print("  kontrolu, kesin dogrulama degil.")


if __name__ == "__main__":
    main()
