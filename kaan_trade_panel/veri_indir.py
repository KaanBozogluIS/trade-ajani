r"""
GECMIS VERI INDIRICI
====================

Borsadan uzun gecmis fiyat verisi indirir ve klasordeki "veri" adli
alt klasore kaydeder.

Neden kaydediyoruz?
    Borsalar bize saniyede sinirli sayida soru sorma izni verir. Iki yillik
    saatlik veri yaklasik 17.500 mum demek ve borsa bunu tek seferde vermez,
    18 ayri istek gerekir. Bunu her test icin bastan yapmak dakikalar surer.
    Bir kez indirip diske kaydedersek, sonraki testler bir saniyede baslar.

Tek basina da calistirilabilir:
    .\.venv\Scripts\python.exe veri_indir.py
"""

import sys
import time
from pathlib import Path

import ccxt
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


KLASOR = Path(__file__).parent
VERI_KLASORU = KLASOR / "veri"

# Bir mumun kac milisaniye oldugu (borsadan veri isterken gerekiyor)
DILIM_MILISANIYE = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}

SUTUNLAR = ["zaman", "acilis", "yuksek", "dusuk", "kapanis", "hacim"]


def dosya_adi(borsa_adi, sembol, zaman_dilimi):
    """'BTC/USDT' gibi bir sembolu dosya adinda kullanilabilir hale getirir."""
    temiz = sembol.replace("/", "-").replace(":", "_")
    return VERI_KLASORU / f"{borsa_adi}_{temiz}_{zaman_dilimi}.csv"


def veri_al(borsa_adi="binance", sembol="BTC/USDT", zaman_dilimi="1h",
            kac_gun=730, yeniden_indir=False):
    """
    Istenen veriyi dondurur. Daha once indirilmisse diskten okur,
    indirilmemisse borsadan ceker ve kaydeder.

    kac_gun : kac gunluk gecmis istiyoruz (730 = yaklasik 2 yil)
    """
    if zaman_dilimi not in DILIM_MILISANIYE:
        raise ValueError(
            f"'{zaman_dilimi}' desteklenmiyor. "
            f"Kullanilabilir: {', '.join(DILIM_MILISANIYE)}"
        )

    VERI_KLASORU.mkdir(exist_ok=True)
    yol = dosya_adi(borsa_adi, sembol, zaman_dilimi)

    # --- Diskte var mi? -------------------------------------
    if yol.exists() and not yeniden_indir:
        df = pd.read_csv(yol, parse_dates=["zaman"])
        print(f"[i] Veri diskten okundu: {yol.name}  ({len(df):,} mum)")
        return df

    # --- Borsadan indir -------------------------------------
    print(f"[i] Borsadan indiriliyor: {sembol} / {zaman_dilimi} / {kac_gun} gun")
    print("    (ilk seferde biraz surer, sonra diskten okunacak)")

    borsa = getattr(ccxt, borsa_adi)({"enableRateLimit": True, "timeout": 30000})
    mum_ms = DILIM_MILISANIYE[zaman_dilimi]
    simdi = borsa.milliseconds()
    baslangic = simdi - kac_gun * 24 * 60 * 60 * 1000

    tum_mumlar = []
    imlec = baslangic
    while imlec < simdi:
        try:
            parca = borsa.fetch_ohlcv(sembol, timeframe=zaman_dilimi,
                                      since=imlec, limit=1000)
        except ccxt.NetworkError as e:
            print(f"    [!] Baglanti sorunu, 5 saniye sonra tekrar denenecek: {str(e)[:80]}")
            time.sleep(5)
            continue

        if not parca:
            break

        tum_mumlar.extend(parca)
        imlec = parca[-1][0] + mum_ms
        print(f"    {len(tum_mumlar):,} mum indirildi...", end="\r")

        # Borsa bize verebildigi kadarini verdi, devami yok
        if len(parca) < 2:
            break

    print()
    if not tum_mumlar:
        raise RuntimeError(
            f"Hic veri gelmedi. '{sembol}' bu borsada mevcut mu? "
            f"Sembolu kontrol edin."
        )

    df = pd.DataFrame(tum_mumlar, columns=SUTUNLAR)
    df["zaman"] = pd.to_datetime(df["zaman"], unit="ms", utc=True)

    # Ayni mum iki kez gelmis olabilir, tekrarlari temizle
    df = df.drop_duplicates(subset="zaman").sort_values("zaman").reset_index(drop=True)

    # Son mum henuz kapanmamis olabilir, onu atiyoruz
    df = df.iloc[:-1].reset_index(drop=True)

    df.to_csv(yol, index=False)
    print(f"[i] Kaydedildi: {yol.name}  ({len(df):,} mum)")
    print(f"    Tarih araligi: {df['zaman'].iloc[0]:%Y-%m-%d}  ->  {df['zaman'].iloc[-1]:%Y-%m-%d}")
    return df


if __name__ == "__main__":
    veri_al()
