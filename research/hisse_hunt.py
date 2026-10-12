"""ABD hisseleri icin strateji dogrulama taramasi (Telegram'a eklemeden ONCE).

Kripto icin tasarlanmis 6 stratejinin (REGISTRY) hisselerde ise yarayip
yaramadigini olcer. Ayni disiplin (bkz. reversal_hunt.py): her seri IS (%70)
/ OOS (%30) bolunur, ikisinde de profit_factor >= 1.0 ve yeterli islem
sarti aranir.

EZBERE KARSI EK KOSUL: sadece kullanicinin ilgilendigi 3 hissede (AMPX,
ANNX, MSTR) "gecen" parametreyi secmek tesadufe cok acik (54 kombinasyonda
birkaci sansla gecer). Bu yuzden genis bir evren taranir ve bir
(strateji, parametre, zaman dilimi) ancak EVRENIN EN AZ YARISINDA da
dual-PF'yi geciyorsa "genellenebilir" sayilir. Telegram'a SADECE
genellenebilir bir kombinasyonun, ilgilenilen hissede de gectigi
durumlar eklenmeye adaydir.

Kullanim:  python research/hisse_hunt.py
Sonuc:     reports/hisse_hunt_sonuclari.csv + konsol ozeti
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yaml

from core import datastore
from core.backtest import Costs, run as run_backtest
from core.metrics import summarize
from core.strategies import REGISTRY

KOK = Path(__file__).resolve().parent.parent
ILGILENILEN = ["AMPX", "ANNX", "MSTR"]
# Farkli sektor/oynaklik profillerinden likit ABD hisseleri -- genelleme olcusu.
EVREN = ILGILENILEN + [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "NFLX",
    "PLTR", "COIN", "MARA", "RIOT", "HOOD", "SOFI", "SMCI", "RKLB", "IONQ", "JPM",
    "XOM", "UNH", "LLY", "WMT", "SPY", "QQQ",
]
ZAMAN_DILIMLERI = ["1h", "1d"]
BASLANGIC = {"1h": "2024-01-01", "1d": "2015-01-01"}

# Her strateji icin varsayilan + birkac makul varyant (bilerek kucuk tutuldu:
# cok fazla deneme, sansla gecen sayisini artirir).
PARAMETRELER: dict[str, list[dict]] = {
    "ema_cross": [{}, {"fast": 20, "slow": 50}, {"fast": 50, "slow": 200}],
    "ict_swing": [{}],
    "altcoin_stratejisi": [{}, {"tolerance_pct": 1.0, "break_atr_mult": 0.5}],
    "major_stratejisi": [{}, {"breakout_len": 55, "adx_min": 20.0}],
    "tepe_dip_stratejisi": [{}, {"tolerance_pct": 0.5}],
    "hacim_uyumsuzlugu_stratejisi": [{}, {"tolerance_pct": 0.5}],
}
MIN_ISLEM = 5


def _degerlendir(df, sinif, params, tf, maliyet):
    if len(df) < 250:
        return None
    try:
        m = summarize(run_backtest(df, sinif(**params), costs=maliyet), tf, "stock")
    except Exception:
        return None
    return None if "error" in m else m


def main() -> None:
    cfg = yaml.safe_load((KOK / "config" / "universe.yaml").read_text(encoding="utf-8"))
    bt = cfg["backtest_defaults"]
    maliyet = Costs(fee_bps=bt["fee_bps"], slippage_bps=bt["slippage_bps"])

    satirlar = []
    for tf in ZAMAN_DILIMLERI:
        for sembol in EVREN:
            try:
                df = datastore.update("yahoo", sembol, tf, start=BASLANGIC[tf])
            except Exception as exc:
                print(f"[atlandi] {sembol} {tf}: {exc}", file=sys.stderr)
                continue
            if len(df) < 500:
                print(f"[atlandi] {sembol} {tf}: {len(df)} mum", file=sys.stderr)
                continue
            kes = int(len(df) * 0.7)
            df_is, df_oos = df.iloc[:kes], df.iloc[kes:]
            al_tut_oos = (df_oos["close"].iloc[-1] / df_oos["close"].iloc[0] - 1) * 100
            for strateji, varyantlar in PARAMETRELER.items():
                for i, params in enumerate(varyantlar):
                    m_is = _degerlendir(df_is, REGISTRY[strateji], params, tf, maliyet)
                    m_oos = _degerlendir(df_oos, REGISTRY[strateji], params, tf, maliyet)
                    if m_is is None or m_oos is None:
                        continue
                    yeterli = m_is["islem_sayisi"] >= MIN_ISLEM and m_oos["islem_sayisi"] >= MIN_ISLEM
                    satirlar.append({
                        "sembol": sembol, "tf": tf, "strateji": strateji, "varyant": i, "params": params,
                        "IS_PF": m_is["profit_factor"], "OOS_PF": m_oos["profit_factor"],
                        "IS_islem": m_is["islem_sayisi"], "OOS_islem": m_oos["islem_sayisi"],
                        "OOS_getiri_%": m_oos["toplam_getiri_%"], "OOS_al_tut_%": al_tut_oos,
                        "OOS_maxdd_%": m_oos["max_drawdown_%"],
                        "gecti": yeterli and m_is["profit_factor"] >= 1.0 and m_oos["profit_factor"] >= 1.0,
                    })
            print(f"  ... {sembol} {tf} tamam", file=sys.stderr)

    tablo = pd.DataFrame(satirlar)
    cikti = KOK / "reports" / "hisse_hunt_sonuclari.csv"
    cikti.parent.mkdir(exist_ok=True)
    tablo.to_csv(cikti, index=False, encoding="utf-8-sig")

    anahtar = ["tf", "strateji", "varyant"]
    genel = (tablo.groupby(anahtar)
             .agg(sembol_sayisi=("sembol", "nunique"), gecen=("gecti", "sum"),
                  medyan_OOS_PF=("OOS_PF", "median"))
             .reset_index())
    genel["gecme_orani_%"] = genel["gecen"] / genel["sembol_sayisi"] * 100
    genel = genel.sort_values("gecme_orani_%", ascending=False)
    print("\n=== Kombinasyon bazinda: evrenin yuzde kacinda dual-PF gecti ===")
    print(genel.to_string(index=False))

    genellenebilir = genel[genel["gecme_orani_%"] >= 50]
    print(f"\nGenellenebilir (evrenin >= %50'sinde gecen) kombinasyon: {len(genellenebilir)}")
    adaylar = tablo.merge(genellenebilir[anahtar], on=anahtar)
    adaylar = adaylar[adaylar["sembol"].isin(ILGILENILEN) & adaylar["gecti"]]
    print("\n=== Telegram'a ADAY (genellenebilir + ilgilenilen hissede gecti) ===")
    print(adaylar.to_string(index=False) if not adaylar.empty else "(yok)")
    print(f"\nIlgilenilen hisselerde gecen TUM kombinasyonlar (genellenebilir olmasa bile):")
    print(tablo[tablo["sembol"].isin(ILGILENILEN) & tablo["gecti"]]
          [["sembol", "tf", "strateji", "varyant", "IS_PF", "OOS_PF", "OOS_islem", "OOS_getiri_%", "OOS_al_tut_%"]]
          .to_string(index=False))
    print(f"\nTam sonuclar: {cikti}")


if __name__ == "__main__":
    main()
