r"""
SANAL TRADER'IN BUTUN OLARAK GECMIS TESTI
=========================================

Soru: Sanal Trader'in YONTEMI ("her coin icin son 30 gunde en iyi giden
stratejiyi sec, kaldiracla isle") gecmiste ise yarar miydi -- yoksa
kazanci/kaybi piyasanin genel yonu mu belirliyor?

Canli botun kurallarinin AYNISI son ~1 yilin saatlik verisinde,
bar bar oynatilir: 40 coinlik evren, 23 strateji, en fazla 8 pozisyon,
nakdin bos slotlara esit bolunmesi, ATR'a gore 5x-10x kaldirac, 2xATR
stop-loss, likidasyon, 14 gun tutma siniri, %25'lik devre kesici, %0.1
komisyon (giris + cikis, notional uzerinden).

KIYASLAR (asil cevap bunlarda):
  - RASTGELE: ayni bot, ama her gun her coine RASTGELE bir strateji
    atanir (5 farkli tohum). "En iyiyi secmek" rastgele secmeyi
    gecemiyorsa, secim mekanizmasi bir sey katmiyor demektir -- bu
    projenin tarama.py'deki rastgele-kontrol-grubu yaklasimiyla ayni fikir.
  - BTC al-tut (1x ve 5x, likidasyon dahil) ve 40 coinin esit agirlikli al-tut'u.

BILINCLI BASITLESTIRMELER (sonuclari yorumlarken akilda tutun):
  1. Rotasyon saatlik degil GUNLUK (24 mumda bir). Acik pozisyonlar zaten
     acildiklari stratejiye bagli kaldigi icin etkisi sadece YENI
     girislerin strateji secimindedir.
  2. Strateji siralamasi, son 30 gundeki KALDIRACSIZ getiriyle yapilir
     (canli bot kaldirac + stop + likidasyonla puanlar). Ayni coinde tum
     stratejiler ayni kaldiraci kullandigi icin siralama cogunlukla ayni
     kalir; farki, islem ortasinda derin dusus yapan stratejilerde olur.
  3. Stratejilerin pozisyon serisi tum gecmis uzerinde BIR KEZ hesaplanir
     (canli bot her saat son ~400 mum uzerinde hesaplar). Kosullara bagli
     "bekleyen kurulum" tutan stratejilerde kucuk farklar olabilir.
  4. EVREN BUGUNUN en likit 40 coinidir -- bir yil once hangi coinlerin
     likit oldugunu bilemeyiz. Bu "hayatta kalan yanlisi" (survivorship
     bias) sonuclari bir miktar IYIMSER gosterir.

Calistirmak icin (ilk sefer veriyi indirir, ~5-10 dk):
    .\.venv\Scripts\python.exe bot_gecmis_testi.py
Sonuclar: cikti/bot_gecmis_testi/ozet.json ve egri.csv (panelde Sanal
Trader sayfasinda gosterilir).
"""

import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import sanal_trader as st
import veri_kaynaklari as vk
from stratejiler import atr

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KLASOR = Path(__file__).parent
CIKTI = KLASOR / "cikti" / "bot_gecmis_testi"
ONBELLEK = KLASOR / "veri" / "bot_gecmis_testi"   # veri/ gitignore'da

A = st.AYARLAR
TEST_GUN = 365
PENCERE_MUM = 30 * 24          # rotasyon puanlama penceresi (canli bot: 30 gun)
ROTASYON_MUM = 24              # gunluk rotasyon
RASTGELE_TOHUMLAR = (1, 2, 3, 4, 5)
UCRET = A["islem_ucreti_yuzde"] / 100


# ------------------------------------------------------------
#  1) Evren ve veri
# ------------------------------------------------------------

def evren_sec(adet=40):
    import requests
    for taban in vk._MUM_ADRESLERI:
        try:
            y = requests.get(f"{taban}/api/v3/ticker/24hr", timeout=30)
            y.raise_for_status()
            break
        except Exception:
            continue
    else:
        raise SystemExit("24 saatlik hacim listesi alinamadi")
    satirlar = [r for r in y.json() if r["symbol"].endswith("USDT")]
    satirlar.sort(key=lambda r: float(r["quoteVolume"]), reverse=True)
    evren = []
    for r in satirlar:
        kod = r["symbol"][:-4]
        if kod in st._STABILCOIN_KODLARI or kod.endswith(("UP", "DOWN", "BULL", "BEAR")):
            continue
        evren.append(f"{kod}/USDT")
        if len(evren) >= adet + 15:   # stabil/verisiz elenenler icin pay
            break
    return evren


def veri_yukle(semboller, mum_sayisi):
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    dosya = ONBELLEK / f"mumlar_{datetime.now(timezone.utc):%Y%m%d}.pkl"
    if dosya.exists():
        print(f"[i] Bugunun onbellegi kullaniliyor: {dosya.name}")
        return pickle.loads(dosya.read_bytes())
    veriler = {}
    for i, s in enumerate(semboller, 1):
        df = vk.mum_verisi(s, "1h", mum_sayisi)
        print(f"   ... {i}/{len(semboller)} {s}: {0 if df is None else len(df)} mum")
        if df is not None and len(df) > PENCERE_MUM + st._MAKS_ISINMA + 24 * 30:
            veriler[s] = df
    dosya.write_bytes(pickle.dumps(veriler))
    return veriler


# ------------------------------------------------------------
#  2) Her coin icin onceden hesaplananlar
# ------------------------------------------------------------

def coin_hazirla(df, zaman_ekseni):
    """Ortak saatlik eksene hizalanmis diziler + her strateji icin pozisyon ve puan."""
    d = df.set_index("zaman")
    kapanis = d["kapanis"]
    kisa, uzun = atr(df, 14).to_numpy(), atr(df, A["kaldirac_uzun_atr_mum"]).to_numpy()
    a_deger = np.fmax(kisa, uzun)
    stop_yuzde = A["stop_atr_kati"] * a_deger / kapanis.to_numpy() * 100
    with np.errstate(divide="ignore", invalid="ignore"):
        kaldirac = np.clip(A["risk_per_islem_yuzde"] / stop_yuzde, A["min_kaldirac"], A["maks_kaldirac"])
    stop_orani = np.minimum(stop_yuzde / 100, 0.8 / kaldirac)

    getiri = kapanis.pct_change().to_numpy()
    pozlar, puanlar = [], []
    for isim, fn, params, isinma in st._STRATEJILER_TUMU:
        try:
            poz = np.array(fn(df, **params), dtype=float)
        except Exception:
            poz = np.full(len(df), np.nan)
        poz[:isinma] = np.nan
        strat_getiri = np.nan_to_num(np.concatenate([[np.nan], poz[:-1]]) * getiri)
        puan = np.array(pd.Series(strat_getiri).rolling(PENCERE_MUM, min_periods=PENCERE_MUM).sum(), dtype=float)
        puan[:isinma + PENCERE_MUM] = np.nan
        pozlar.append(poz)
        puanlar.append(puan)

    tablo = pd.DataFrame({
        "acilis": d["acilis"], "yuksek": d["yuksek"], "dusuk": d["dusuk"], "kapanis": kapanis,
        "kaldirac": kaldirac, "stop_orani": stop_orani,
    }, index=d.index)
    hizali = tablo.reindex(zaman_ekseni)
    idx = d.index.get_indexer(zaman_ekseni)          # -1: o saatte veri yok
    gecerli = idx >= 0
    def hizala(dizi):
        out = np.full(len(zaman_ekseni), np.nan)
        out[gecerli] = dizi[idx[gecerli]]
        return out
    return {
        "acilis": hizali["acilis"].to_numpy(), "yuksek": hizali["yuksek"].to_numpy(),
        "dusuk": hizali["dusuk"].to_numpy(), "kapanis": hizali["kapanis"].to_numpy(),
        "kaldirac": hizali["kaldirac"].to_numpy(), "stop_orani": hizali["stop_orani"].to_numpy(),
        "poz": np.vstack([hizala(p) for p in pozlar]),
        "puan": np.vstack([hizala(p) for p in puanlar]),
    }


# ------------------------------------------------------------
#  3) Portfoy simulasyonu (canli Portfoy sinifiyla AYNI muhasebe)
# ------------------------------------------------------------

def _deger(p, fiyat):
    oran = (fiyat / p["giris"] - 1) if p["yon"] == 1 else (p["giris"] - fiyat) / p["giris"]
    return max(0.0, p["marjin"] - p["giris_ucreti"] + p["marjin"] * p["k"] * oran)


def simule(coinler, n_mum, secim, tohum=None):
    rng = np.random.default_rng(tohum)
    nakit = A["baslangic_bakiye"]
    acik = {}
    atama = {}
    zirve, kesici_bitis = None, None
    egri = np.empty(n_mum)
    sayac = {"islem": 0, "kazanan": 0, "stop": 0, "likidasyon": 0, "sure": 0, "kesici": 0, "short": 0}
    adlar = list(coinler)

    def kapat(c, fiyat, likide=False):
        nonlocal nakit
        p = acik.pop(c)
        if likide:
            net = 0.0
        else:
            cikis_ucreti = p["miktar"] * fiyat * UCRET
            oran = (fiyat / p["giris"] - 1) if p["yon"] == 1 else (p["giris"] - fiyat) / p["giris"]
            net = max(0.0, p["marjin"] + p["marjin"] * p["k"] * oran - cikis_ucreti - p["giris_ucreti"])
        nakit += net
        sayac["islem"] += 1
        sayac["kazanan"] += int(net > p["marjin"])

    for t in range(n_mum):
        if t % ROTASYON_MUM == 0:
            for c in adlar:
                puan = coinler[c]["puan"][:, t]
                gecerli = np.flatnonzero(~np.isnan(puan))
                if len(gecerli) == 0:
                    atama.pop(c, None)
                elif secim == "en_iyi":
                    atama[c] = int(gecerli[np.argmax(puan[gecerli])])
                else:
                    atama[c] = int(rng.choice(gecerli))

        kesici_aktif = kesici_bitis is not None and t < kesici_bitis
        for c in list(dict.fromkeys(list(acik) + list(atama))):
            v = coinler[c]
            kap = v["kapanis"][t]
            if np.isnan(kap):
                continue
            if c in acik:
                p = acik[c]
                uc = v["dusuk"][t] if p["yon"] == 1 else v["yuksek"][t]
                stop_vur = (uc <= p["stop"]) if p["yon"] == 1 else (uc >= p["stop"])
                liq_vur = (uc <= p["liq"]) if p["yon"] == 1 else (uc >= p["liq"])
                if stop_vur:
                    dolum = min(p["stop"], v["acilis"][t]) if p["yon"] == 1 else max(p["stop"], v["acilis"][t])
                    if (dolum <= p["liq"]) if p["yon"] == 1 else (dolum >= p["liq"]):
                        sayac["likidasyon"] += 1
                        kapat(c, p["liq"], likide=True)
                    else:
                        sayac["stop"] += 1
                        kapat(c, dolum)
                    continue
                if liq_vur:
                    sayac["likidasyon"] += 1
                    kapat(c, p["liq"], likide=True)
                    continue
                if t - p["t0"] >= A["maks_tutma_gun"] * 24:
                    sayac["sure"] += 1
                    kapat(c, kap)
                    continue
                if v["poz"][p["strateji"], t] == 0:
                    kapat(c, kap)
                continue
            if c not in atama or kesici_aktif:
                continue
            sinyal = v["poz"][atama[c], t]
            if sinyal not in (1.0, -1.0):
                continue
            bos = A["maks_pozisyon"] - len(acik)
            if bos <= 0:
                continue
            marjin = nakit * A["islem_orani"] / bos
            k, so = v["kaldirac"][t], v["stop_orani"][t]
            if marjin < 1 or np.isnan(k) or np.isnan(so):
                continue
            yon = 1 if sinyal == 1.0 else -1
            giris_ucreti = marjin * k * UCRET
            nakit -= marjin
            acik[c] = {"yon": yon, "giris": kap, "marjin": marjin, "k": k, "giris_ucreti": giris_ucreti,
                       "miktar": (marjin * k - giris_ucreti) / kap, "t0": t, "strateji": atama[c],
                       "stop": kap * (1 - so) if yon == 1 else kap * (1 + so),
                       "liq": kap * (1 - 1 / k) if yon == 1 else kap * (1 + 1 / k)}
            sayac["short"] += int(yon == -1)

        deger = nakit + sum(_deger(p, coinler[c]["kapanis"][t]) for c, p in acik.items()
                            if not np.isnan(coinler[c]["kapanis"][t]))
        egri[t] = deger
        if kesici_bitis is not None and t >= kesici_bitis:
            kesici_bitis, zirve = None, deger
        elif kesici_bitis is None:
            if zirve is None or deger > zirve:
                zirve = deger
            elif deger <= zirve * (1 - A["devre_kesici_dusus_yuzde"] / 100):
                kesici_bitis = t + A["devre_kesici_bekleme_saat"]
                sayac["kesici"] += 1
    return egri, sayac


# ------------------------------------------------------------
#  4) Kiyas egrileri ve olcumler
# ------------------------------------------------------------

def al_tut(kapanis, dusuk, kaldirac=1.0):
    gecerli = ~np.isnan(kapanis)
    ilk = np.argmax(gecerli)
    giris = kapanis[ilk]
    oran = pd.Series(kapanis / giris - 1).ffill().fillna(0).to_numpy()
    egri = A["baslangic_bakiye"] * (1 + kaldirac * oran - kaldirac * UCRET)
    if kaldirac > 1:
        likit = giris * (1 - 1 / kaldirac)
        vurdu = np.flatnonzero((dusuk <= likit) & (np.arange(len(dusuk)) >= ilk))
        if len(vurdu):
            egri[vurdu[0]:] = 0.0
    return np.maximum(egri, 0.0)


def olc(egri, zaman_ekseni=None):
    tepe = np.maximum.accumulate(egri)
    with np.errstate(divide="ignore", invalid="ignore"):
        dusus = np.nanmin(np.where(tepe > 0, egri / tepe - 1, 0)) * 100
    sonuc = {"getiri": (egri[-1] / A["baslangic_bakiye"] - 1) * 100, "en_buyuk_dusus": dusus}
    if zaman_ekseni is not None:
        # "Fiilen sifirlandi": baslangicin %5'inin altina indigi ilk an. Sonrasinda
        # nakit, yeni pozisyon acmaya yetmedigi icin (marjin < 1$) egri donar --
        # o yuzden bu noktadan sonraki farklar anlamsizdir.
        iflas = np.flatnonzero(egri < A["baslangic_bakiye"] * 0.05)
        sonuc["iflas_tarihi"] = str(zaman_ekseni[iflas[0]].date()) if len(iflas) else None
    return sonuc


def main():
    CIKTI.mkdir(parents=True, exist_ok=True)
    print("[i] Evren seciliyor (bugunun en likit USDT ciftleri)...")
    adaylar = evren_sec()
    mum_sayisi = TEST_GUN * 24 + PENCERE_MUM + st._MAKS_ISINMA + 50
    print(f"[i] {len(adaylar)} aday icin {mum_sayisi} saatlik mum indiriliyor...")
    veriler = veri_yukle(adaylar, mum_sayisi)
    veriler = {s: d for s, d in veriler.items() if not st._stabil_mi(d)}
    veriler = dict(list(veriler.items())[:A["evren_boyutu"]])
    if "BTC/USDT" not in veriler:
        raise SystemExit("BTC verisi yok -- kiyas yapilamaz")

    son = max(d["zaman"].iloc[-1] for d in veriler.values())
    zaman_ekseni = pd.date_range(end=son, periods=TEST_GUN * 24, freq="h")
    print(f"[i] {len(veriler)} coin, test donemi {zaman_ekseni[0]:%Y-%m-%d} -> {zaman_ekseni[-1]:%Y-%m-%d}")
    print("[i] Stratejiler her coin icin hesaplaniyor...")
    coinler = {}
    for i, (s, df) in enumerate(veriler.items(), 1):
        coinler[s] = coin_hazirla(df, zaman_ekseni)
        if i % 10 == 0:
            print(f"   ... {i}/{len(veriler)}")

    n = len(zaman_ekseni)
    print("[i] Bot (en iyi secim) simulasyonu...")
    bot_egri, bot_sayac = simule(coinler, n, "en_iyi")
    rastgeleler = []
    for tohum in RASTGELE_TOHUMLAR:
        print(f"[i] Rastgele kontrol (tohum {tohum})...")
        rastgeleler.append(simule(coinler, n, "rastgele", tohum))

    btc = coinler["BTC/USDT"]
    btc1, btc5 = al_tut(btc["kapanis"], btc["dusuk"]), al_tut(btc["kapanis"], btc["dusuk"], 5.0)
    esit = np.nanmean(np.vstack([al_tut(v["kapanis"], v["dusuk"]) for v in coinler.values()]), axis=0)
    rastgele_getiriler = [olc(e)["getiri"] for e, _ in rastgeleler]
    medyan_i = int(np.argsort(rastgele_getiriler)[len(rastgele_getiriler) // 2])

    # TESHIS: ayni kurallar KALDIRACSIZ (1x). Kaldiracli surumde butun
    # senaryolar sifirlaniyorsa, secim yonteminin bir degeri olup olmadigi
    # ancak burada gorulebilir.
    print("[i] Kaldiracsiz (1x) teshis simulasyonlari...")
    birx = {s: {**v, "kaldirac": np.where(np.isnan(v["kaldirac"]), np.nan, 1.0)} for s, v in coinler.items()}
    bot1_egri, bot1_sayac = simule(birx, n, "en_iyi")
    rastgele1 = [simule(birx, n, "rastgele", t) for t in RASTGELE_TOHUMLAR]
    rastgele1_getiriler = [olc(e)["getiri"] for e, _ in rastgele1]
    medyan1_i = int(np.argsort(rastgele1_getiriler)[len(rastgele1_getiriler) // 2])

    ozet = {
        "olusturma": datetime.now(timezone.utc).isoformat(),
        "donem": [str(zaman_ekseni[0]), str(zaman_ekseni[-1])], "coin_sayisi": len(coinler),
        "strateji_sayisi": len(st._STRATEJILER_TUMU),
        "bot": {**olc(bot_egri, zaman_ekseni), **bot_sayac},
        "bot_1x": {**olc(bot1_egri, zaman_ekseni), **bot1_sayac},
        "rastgele_1x": [{"tohum": t, **olc(e), **s} for t, (e, s) in zip(RASTGELE_TOHUMLAR, rastgele1)],
        "bot_1x_rastgeleyi_gecti": int(sum(olc(bot1_egri)["getiri"] > g for g in rastgele1_getiriler)),
        "rastgele": [{"tohum": t, **olc(e, zaman_ekseni), **s} for t, (e, s) in zip(RASTGELE_TOHUMLAR, rastgeleler)],
        "btc_1x": olc(btc1), "btc_5x": olc(btc5), "esit_agirlik_1x": olc(esit),
        "bot_rastgeleyi_gecti": int(sum(olc(bot_egri)["getiri"] > g for g in rastgele_getiriler)),
    }
    (CIKTI / "ozet.json").write_text(json.dumps(ozet, indent=2, ensure_ascii=False, default=lambda o: o.item()), encoding="utf-8")
    egri = pd.DataFrame({"zaman": zaman_ekseni, "Bot (en iyi seçim)": bot_egri,
                         "Rastgele seçim (medyan)": rastgeleler[medyan_i][0],
                         "Bot kaldıraçsız (1x)": bot1_egri,
                         "Rastgele seçim 1x (medyan)": rastgele1[medyan1_i][0],
                         "BTC al-tut 1x": btc1, "BTC al-tut 5x": btc5,
                         "40 coin eşit ağırlık 1x": esit}).set_index("zaman").resample("D").last()
    egri.round(2).to_csv(CIKTI / "egri.csv")

    print("\n" + "=" * 72)
    for ad, o in (("BOT (en iyi secim)", ozet["bot"]), *[(f"Rastgele tohum {r['tohum']}", r) for r in ozet["rastgele"]],
                  ("BOT 1x (teshis)", ozet["bot_1x"]), *[(f"Rastgele 1x tohum {r['tohum']}", r) for r in ozet["rastgele_1x"]],
                  ("BTC al-tut 1x", ozet["btc_1x"]), ("BTC al-tut 5x", ozet["btc_5x"]),
                  ("40 coin esit agirlik 1x", ozet["esit_agirlik_1x"])):
        ek = f"  islem {o['islem']}, kazanan %{o['kazanan'] / max(o['islem'], 1) * 100:.0f}, stop {o['stop']}, " \
             f"likidasyon {o['likidasyon']}, kesici {o['kesici']}" if "islem" in o else ""
        print(f"{ad:<26} getiri {o['getiri']:+8.1f}%  en buyuk dusus {o['en_buyuk_dusus']:7.1f}%{ek}")
    print(f"\nBot, {len(rastgele_getiriler)} rastgele kontrolden {ozet['bot_rastgeleyi_gecti']} tanesini gecti.")
    print(f"[i] Sonuclar: {CIKTI}")


if __name__ == "__main__":
    main()
