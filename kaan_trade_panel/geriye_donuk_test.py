r"""
GERIYE DONUK TEST (BACKTEST)
============================

"Bu strateji son iki yilda ne yapardi?" sorusunun cevabini verir.

Nasil calisir: Gecmis fiyat verisini basindan sonuna dogru mum mum okur,
tipki botun canli calistigi gibi sinyal uretir ve sanal alim-satim yapar.
Sonunda ne kadar para kaldigini, kac islem yapildigini ve en kotu aninda
ne kadar dustugunu soyler.

ONEMLI - GERCEKCILIK NOTU:
    Gercek hayatta bir mumun kapanis fiyatini ancak mum kapandiktan SONRA
    bilirsiniz. O yuzden bu test, sinyali gordugu mumdan bir SONRAKI mumun
    acilis fiyatindan islem yapar. Bircok amator test bu detayi atlar ve
    gercekte imkansiz olan karlar gosterir.

Calistirmak icin:
    .\.venv\Scripts\python.exe geriye_donuk_test.py
"""

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # ekran yerine dosyaya cizsin
import matplotlib.pyplot as plt

import bot                      # strateji tek yerde dursun diye botun kendisinden aliyoruz
from veri_indir import veri_al

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


KLASOR = Path(__file__).parent
CIKTI_KLASORU = KLASOR / "cikti"
ISLEM_DOSYASI = CIKTI_KLASORU / "test_islemleri.csv"
GRAFIK_DOSYASI = CIKTI_KLASORU / "test_grafik.png"


# ============================================================
#  AYARLAR
# ============================================================

AYARLAR = {
    "borsa": "binance",
    "sembol": "BTC/USDT",
    "zaman_dilimi": "1h",
    "kac_gun": 730,                 # 730 gun = yaklasik 2 yil

    "baslangic_bakiye": 1000.0,
    "islem_ucreti_yuzde": 0.1,
    "islem_orani": 0.95,

    # Test edilecek strateji ayarlari (bot.py'dekiyle ayni olmali)
    "hizli_ortalama": 10,
    "yavas_ortalama": 30,

    # Farkli ayar kombinasyonlarini da denesin mi?
    "parametre_taramasi": True,
}


# ============================================================
#  SIMULASYON
# ============================================================

def simule_et(df, hizli, yavas, a):
    """
    Verilen fiyat verisinde stratejiyi bastan sona calistirir.
    Sonuclari bir sozluk olarak dondurur.
    """
    df = bot.ortalamalari_hesapla(df, hizli, yavas)

    # Hizli olmasi icin sutunlari duz listeye ceviriyoruz
    zamanlar = df["zaman"].tolist()
    acilislar = df["acilis"].tolist()
    kapanislar = df["kapanis"].tolist()
    hizli_ma = df["hizli_ma"].tolist()
    yavas_ma = df["yavas_ma"].tolist()
    n = len(df)

    nakit = a["baslangic_bakiye"]
    coin = 0.0
    ucret_o = a["islem_ucreti_yuzde"] / 100

    bekleyen = None          # sonraki mumda gerceklestirilecek emir
    islemler = []            # her alim ve her satim
    turlar = []              # alim-satim ciftleri (kar/zarar olcmek icin)
    acik_alim = None
    portfoy_serisi = []
    piyasada_mum = 0

    for i in range(n):
        # --- 1) Onceki mumda verilen emri bu mumun acilisinda gerceklestir
        if bekleyen == "AL":
            harcanan = nakit * a["islem_orani"]
            if harcanan >= 1:
                fiyat = acilislar[i]
                ucret = harcanan * ucret_o
                alinan = (harcanan - ucret) / fiyat
                nakit -= harcanan
                coin += alinan
                islemler.append({"tarih": zamanlar[i], "tur": "AL", "fiyat": fiyat,
                                 "miktar": alinan, "tutar": harcanan, "ucret": ucret})
                acik_alim = {"tarih": zamanlar[i], "fiyat": fiyat, "harcanan": harcanan}
            bekleyen = None

        elif bekleyen == "SAT":
            if coin > 0:
                fiyat = acilislar[i]
                brut = coin * fiyat
                ucret = brut * ucret_o
                net = brut - ucret
                islemler.append({"tarih": zamanlar[i], "tur": "SAT", "fiyat": fiyat,
                                 "miktar": coin, "tutar": net, "ucret": ucret})
                if acik_alim:
                    kazanc = net - acik_alim["harcanan"]
                    turlar.append({
                        "giris_tarih": acik_alim["tarih"],
                        "cikis_tarih": zamanlar[i],
                        "giris_fiyat": acik_alim["fiyat"],
                        "cikis_fiyat": fiyat,
                        "kazanc": kazanc,
                        "yuzde": kazanc / acik_alim["harcanan"] * 100,
                    })
                    acik_alim = None
                coin = 0.0
                nakit += net
            bekleyen = None

        # --- 2) Bu mumun kapanisina bakip yeni sinyal uret
        if i >= 1 and i < n - 1:
            gecerli = not any(
                x != x for x in (hizli_ma[i - 1], yavas_ma[i - 1], hizli_ma[i], yavas_ma[i])
            )  # "x != x" ifadesi sadece bos (NaN) degerler icin dogrudur
            if gecerli:
                onceki_ustte = hizli_ma[i - 1] > yavas_ma[i - 1]
                simdi_ustte = hizli_ma[i] > yavas_ma[i]
                if not onceki_ustte and simdi_ustte and coin == 0:
                    bekleyen = "AL"
                elif onceki_ustte and not simdi_ustte and coin > 0:
                    bekleyen = "SAT"

        # --- 3) Mumun sonundaki portfoy degerini kaydet
        if coin > 0:
            piyasada_mum += 1
        portfoy_serisi.append(nakit + coin * kapanislar[i])

    son_deger = portfoy_serisi[-1]
    kazananlar = [t for t in turlar if t["kazanc"] > 0]
    kaybedenler = [t for t in turlar if t["kazanc"] <= 0]

    # Al-ve-tut karsilastirmasi: basta al, sonuna kadar elde tut
    al_tut_deger = a["baslangic_bakiye"] * (1 - ucret_o) * (kapanislar[-1] / acilislar[0])

    return {
        "hizli": hizli,
        "yavas": yavas,
        "baslangic": a["baslangic_bakiye"],
        "son_deger": son_deger,
        "getiri_yuzde": (son_deger / a["baslangic_bakiye"] - 1) * 100,
        "al_tut_deger": al_tut_deger,
        "al_tut_yuzde": (al_tut_deger / a["baslangic_bakiye"] - 1) * 100,
        "tur_sayisi": len(turlar),
        "islem_sayisi": len(islemler),
        "kazanan": len(kazananlar),
        "kaybeden": len(kaybedenler),
        "kazanma_orani": len(kazananlar) / len(turlar) * 100 if turlar else 0.0,
        "ortalama_kazanc": sum(t["yuzde"] for t in kazananlar) / len(kazananlar) if kazananlar else 0.0,
        "ortalama_kayip": sum(t["yuzde"] for t in kaybedenler) / len(kaybedenler) if kaybedenler else 0.0,
        "en_iyi_tur": max((t["yuzde"] for t in turlar), default=0.0),
        "en_kotu_tur": min((t["yuzde"] for t in turlar), default=0.0),
        "en_buyuk_dusus": en_buyuk_dusus(portfoy_serisi),
        "al_tut_en_buyuk_dusus": en_buyuk_dusus(kapanislar),
        "piyasada_sure": piyasada_mum / n * 100,
        "odenen_ucret": sum(x["ucret"] for x in islemler),
        "portfoy_serisi": portfoy_serisi,
        "zamanlar": zamanlar,
        "kapanislar": kapanislar,
        "islemler": islemler,
        "turlar": turlar,
    }


def en_buyuk_dusus(seri):
    """
    "Max drawdown" -- en tepe noktadan en dibe kadar yuzde kac kaybettiniz.
    Bu sayi getiriden bile onemlidir: %200 kazandiran ama yolda %70 dusen
    bir strateji, cogu insanin dayanamayip birakacagi bir stratejidir.
    """
    zirve = seri[0]
    en_kotu = 0.0
    for deger in seri:
        if deger > zirve:
            zirve = deger
        dusus = (deger / zirve - 1) * 100
        if dusus < en_kotu:
            en_kotu = dusus
    return en_kotu


# ============================================================
#  RAPOR
# ============================================================

def satir(etiket, deger, aciklama=""):
    print(f"  {etiket:<28} {deger:>16}   {aciklama}")


def rapor_yaz(s, a, df):
    bas = df["zaman"].iloc[0]
    son = df["zaman"].iloc[-1]

    print()
    print("=" * 74)
    print("  GERIYE DONUK TEST SONUCU")
    print("=" * 74)
    satir("Coin", a["sembol"])
    satir("Zaman dilimi", a["zaman_dilimi"])
    satir("Test araligi", f"{bas:%Y-%m-%d} / {son:%Y-%m-%d}")
    satir("Mum sayisi", f"{len(df):,}")
    satir("Strateji", f"{s['hizli']} / {s['yavas']} ortalama")

    print("-" * 74)
    print("  PARA")
    satir("Baslangic", f"{s['baslangic']:,.2f} USDT")
    satir("Bitis", f"{s['son_deger']:,.2f} USDT")
    satir("Getiri", f"{s['getiri_yuzde']:+.2f} %", "<-- stratejinin sonucu")
    satir("Al-ve-tut getirisi", f"{s['al_tut_yuzde']:+.2f} %", "hic islem yapmasaydiniz")
    fark = s["getiri_yuzde"] - s["al_tut_yuzde"]
    satir("Fark", f"{fark:+.2f} %",
          "strateji daha iyi" if fark > 0 else "strateji daha kotu")
    satir("Odenen komisyon", f"{s['odenen_ucret']:,.2f} USDT")

    print("-" * 74)
    print("  ISLEMLER")
    satir("Alim-satim turu", f"{s['tur_sayisi']:,}")
    satir("Kazanan / kaybeden", f"{s['kazanan']} / {s['kaybeden']}")
    satir("Kazanma orani", f"{s['kazanma_orani']:.1f} %")
    satir("Ortalama kazanc", f"{s['ortalama_kazanc']:+.2f} %")
    satir("Ortalama kayip", f"{s['ortalama_kayip']:+.2f} %")
    satir("En iyi islem", f"{s['en_iyi_tur']:+.2f} %")
    satir("En kotu islem", f"{s['en_kotu_tur']:+.2f} %")
    satir("Piyasada gecen sure", f"{s['piyasada_sure']:.1f} %", "geri kalani nakitte beklendi")

    print("-" * 74)
    print("  RISK")
    satir("En buyuk dusus", f"{s['en_buyuk_dusus']:.2f} %", "zirveden dibe (strateji)")
    satir("Al-ve-tut en buyuk dusus", f"{s['al_tut_en_buyuk_dusus']:.2f} %", "zirveden dibe (coin)")
    print("=" * 74)


def islemleri_kaydet(s):
    CIKTI_KLASORU.mkdir(exist_ok=True)
    with ISLEM_DOSYASI.open("w", newline="", encoding="utf-8-sig") as f:
        y = csv.DictWriter(f, fieldnames=["tarih", "tur", "fiyat", "miktar", "tutar", "ucret"])
        y.writeheader()
        for x in s["islemler"]:
            y.writerow({
                "tarih": f"{x['tarih']:%Y-%m-%d %H:%M}",
                "tur": x["tur"],
                "fiyat": round(x["fiyat"], 2),
                "miktar": round(x["miktar"], 8),
                "tutar": round(x["tutar"], 2),
                "ucret": round(x["ucret"], 4),
            })
    print(f"\n[i] Butun islemler kaydedildi: {ISLEM_DOSYASI.name}")


def grafik_ciz(s, a):
    """Ustte fiyat ve islem noktalari, altta portfoy degeri."""
    zaman = s["zamanlar"]
    fig, (ust, alt) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1]})

    ust.plot(zaman, s["kapanislar"], linewidth=0.8, color="#555555", label=a["sembol"] + " fiyati")
    if len(s["islemler"]) <= 400:
        alis_z = [x["tarih"] for x in s["islemler"] if x["tur"] == "AL"]
        alis_f = [x["fiyat"] for x in s["islemler"] if x["tur"] == "AL"]
        satis_z = [x["tarih"] for x in s["islemler"] if x["tur"] == "SAT"]
        satis_f = [x["fiyat"] for x in s["islemler"] if x["tur"] == "SAT"]
        ust.scatter(alis_z, alis_f, marker="^", s=28, color="#1D9E75", label="alim", zorder=3)
        ust.scatter(satis_z, satis_f, marker="v", s=28, color="#E24B4A", label="satim", zorder=3)
    ust.set_ylabel("Fiyat (USDT)")
    ust.set_title(f"{a['sembol']}  {a['zaman_dilimi']}  -  {s['hizli']}/{s['yavas']} ortalama kesismesi")
    ust.legend(loc="upper left", fontsize=9)
    ust.grid(alpha=0.25)

    al_tut = [a["baslangic_bakiye"] * (1 - a["islem_ucreti_yuzde"] / 100)
              * (k / s["kapanislar"][0]) for k in s["kapanislar"]]
    alt.plot(zaman, s["portfoy_serisi"], linewidth=1.2, color="#534AB7", label="Strateji")
    alt.plot(zaman, al_tut, linewidth=1.2, color="#BA7517", linestyle="--", label="Al ve tut")
    alt.axhline(a["baslangic_bakiye"], color="#888780", linewidth=0.8, linestyle=":")
    alt.set_ylabel("Portfoy degeri (USDT)")
    alt.set_xlabel("Tarih")
    alt.legend(loc="upper left", fontsize=9)
    alt.grid(alpha=0.25)

    fig.tight_layout()
    CIKTI_KLASORU.mkdir(exist_ok=True)
    fig.savefig(GRAFIK_DOSYASI, dpi=110)
    plt.close(fig)
    print(f"[i] Grafik kaydedildi: {GRAFIK_DOSYASI.name}")


# ============================================================
#  PARAMETRE TARAMASI  (ve asiri uydurma tuzagi)
# ============================================================

HIZLI_SECENEKLER = [5, 8, 10, 15, 20, 30]
YAVAS_SECENEKLER = [20, 30, 50, 100, 150, 200]


def parametre_taramasi(df, a):
    """
    Bircok farkli ortalama kombinasyonunu dener.

    AMA dogru bicimde: veriyi ikiye boluyoruz.
      * EGITIM  (ilk %70)  -> en iyi ayari burada ariyoruz
      * TEST    (son %30)  -> bulunan ayari hic bakmadigimiz veride deniyoruz

    Neden? Cunku yeterince cok kombinasyon denerseniz, gecmiste harika
    gorunen bir ayari MUTLAKA bulursunuz -- tesadufen. Buna "asiri uydurma"
    denir. Gercek soru sudur: o ayar, hic gormedigi veride de calisiyor mu?
    """
    ayirma = int(len(df) * 0.70)
    egitim = df.iloc[:ayirma].reset_index(drop=True)
    test = df.iloc[ayirma:].reset_index(drop=True)

    print()
    print("=" * 74)
    print("  PARAMETRE TARAMASI")
    print("=" * 74)
    print(f"  Egitim verisi : {egitim['zaman'].iloc[0]:%Y-%m-%d} / {egitim['zaman'].iloc[-1]:%Y-%m-%d}  ({len(egitim):,} mum)")
    print(f"  Test verisi   : {test['zaman'].iloc[0]:%Y-%m-%d} / {test['zaman'].iloc[-1]:%Y-%m-%d}  ({len(test):,} mum)")

    kombinasyonlar = [(h, y) for h in HIZLI_SECENEKLER for y in YAVAS_SECENEKLER if h < y]
    print(f"  Denenen kombinasyon sayisi: {len(kombinasyonlar)}")

    sonuclar = []
    for h, y in kombinasyonlar:
        e = simule_et(egitim, h, y, a)
        sonuclar.append({"hizli": h, "yavas": y, "egitim": e["getiri_yuzde"],
                         "egitim_dusus": e["en_buyuk_dusus"], "tur": e["tur_sayisi"]})

    sonuclar.sort(key=lambda r: r["egitim"], reverse=True)

    print("-" * 74)
    print("  Egitim verisinde EN IYI 5 ayar, ve ayni ayarlarin test sonucu:")
    print()
    print(f"  {'ayar':<12}{'egitim getiri':>15}{'test getiri':>14}{'test dususu':>14}{'islem':>8}")
    print("  " + "-" * 61)

    for r in sonuclar[:5]:
        t = simule_et(test, r["hizli"], r["yavas"], a)
        print(f"  {str(r['hizli']) + '/' + str(r['yavas']):<12}"
              f"{r['egitim']:>14.2f}%{t['getiri_yuzde']:>13.2f}%"
              f"{t['en_buyuk_dusus']:>13.2f}%{t['tur_sayisi']:>8}")

    # Karsilastirma icin: test doneminde al-ve-tut ne yapardi
    ornek = simule_et(test, 10, 30, a)
    print()
    print(f"  Kiyas: test doneminde al-ve-tut getirisi {ornek['al_tut_yuzde']:+.2f}%")
    print(f"         test doneminde 10/30 ayari        {ornek['getiri_yuzde']:+.2f}%")

    en_iyi = sonuclar[0]
    en_iyi_test = simule_et(test, en_iyi["hizli"], en_iyi["yavas"], a)
    print()
    print("-" * 74)
    if en_iyi_test["getiri_yuzde"] < en_iyi["egitim"] / 2:
        print("  YORUM: Egitimde en iyi gorunen ayar, test verisinde cok daha kotu.")
        print("         Iste 'asiri uydurma' tam olarak bu. Egitimdeki yuksek sonuc")
        print("         bir yetenek degil, tesadufun uzerine oturmus bir sayiydi.")
    else:
        print("  YORUM: Egitimde iyi olan ayar test verisinde de fena degil. Bu iyi")
        print("         bir isaret, ama tek bir coin ve tek bir donem uzerinde kanit")
        print("         sayilmaz. Baska coinlerde ve donemlerde de denemek gerekir.")
    print("=" * 74)


# ============================================================
#  ANA AKIS
# ============================================================

def main():
    a = AYARLAR

    df = veri_al(a["borsa"], a["sembol"], a["zaman_dilimi"], a["kac_gun"])

    s = simule_et(df, a["hizli_ortalama"], a["yavas_ortalama"], a)
    rapor_yaz(s, a, df)
    islemleri_kaydet(s)
    grafik_ciz(s, a)

    if a["parametre_taramasi"]:
        parametre_taramasi(df, a)


if __name__ == "__main__":
    main()
