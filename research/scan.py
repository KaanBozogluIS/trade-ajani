"""Sistematik strateji taramasi: sembol x zaman dilimi x parametre.

Overfitting'e karsi ana savunma: WALK-FORWARD ayrimi. Her seri once
in-sample (%70) / out-of-sample (%30) olarak bolunur. Parametre secimi
YALNIZCA in-sample'a bakarak yapilmaz burada - sabit "makul" parametre
setleri denenir ve her ikisi de raporlanir. Bir strateji ancak IS ve OOS'ta
TUTARLI davranirsa (ikisinde de pozitif Sharpe, benzer buyuklukte) guvenilir
sayilir; sadece IS'te iyi olan sonuclar ezber (overfit) suphelisidir.

Kullanim:
    python research/scan.py
    python research/scan.py --provider binance --timeframe 1h
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yaml

from core import datastore
from core.backtest import Costs, run as run_backtest
from core.metrics import summarize
from core.strategies import REGISTRY

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"

# Her strateji icin denenecek "makul" parametre setleri.
# Genis grid taramasi bilerek yapilmiyor - buyuk grid + kucuk veri = ezber garantisi.
PARAM_GRID: dict[str, list[dict]] = {
    "ema_cross": [
        {"fast": 10, "slow": 30, "trend_filter": 100},
        {"fast": 20, "slow": 50, "trend_filter": 200},
    ],
    # BTC/ETH/SOL/BNB odakli, kaldiracli/gunluk trader profili icin arandi
    # (major_coin_hunt.py, tam evren + IS/OOS). SOLUSDT 4h (tp=2.0/sl=0.3)
    # en saglam cikti: 563 islemlik tam-tarih ornegi, ort. tutma ~2.8 gun,
    # kaldiracli (risk %1-2, 5-10x) halde bile net karli kaliyor - digerleri
    # (BTC/ETH 1d) kaldiracli sıralamada zayifliyordu, bu yuzden disarida
    # birakildi.
    "ict_swing": [
        {"tp_r_mult": 2.0, "sl_atr_buffer": 0.3},
        {"tp_r_mult": 1.2, "sl_atr_buffer": 0.3},
        {"tp_r_mult": 1.5, "sl_atr_buffer": 0.3},
        {"tp_r_mult": 1.0, "sl_atr_buffer": 0.5},
    ],
    # Bize ozgu, sifirdan tasarlanmis strateji - literaturden degil, klasik
    # fiyat hareketi mantigindan (coklu-dokunuşlu S/D + kararli kirilim +
    # geri cekilme + toparlanma mumu) kurulan kurallar. Bkz.
    # core/strategies/breakout_retest_recovery.py docstring'i.
    # Asagidaki degerler brr_hunt.py ile tam evrende (108 sembol x 54
    # parametre, IS/OOS) dogrulanan EN SAGLAM bolgeyi temsil ediyor - 9
    # bagimsiz sembolde (SEI, SHIB, FET, BICO, WLD, ZKC, BMT, PENGU, ZEN)
    # tekrar eden bir oruntu, tek coin sansı degil. En guclu tek sonuc:
    # SEIUSDT 1h - tam tarih WR=%56, PF=1.71, Sharpe=1.0, maxDD=-%16.5,
    # ort. tutma ~5.4 saat (gercek gunluk-trader frekansi).
    "altcoin_stratejisi": [
        {"tolerance_pct": 0.4, "min_touches": 2, "break_atr_mult": 0.2, "tp_r_mult": 1.5,
         "sl_atr_buffer": 0.3, "max_retest_bars": 30, "recovery_body_ratio": 0.5},
        {"tolerance_pct": 0.4, "min_touches": 3, "break_atr_mult": 0.5, "tp_r_mult": 2.5,
         "sl_atr_buffer": 0.3, "max_retest_bars": 30, "recovery_body_ratio": 0.5},
        {"tolerance_pct": 0.4, "min_touches": 2, "break_atr_mult": 0.2, "tp_r_mult": 2.0,
         "sl_atr_buffer": 0.3, "max_retest_bars": 30, "recovery_body_ratio": 0.5},
        {"tolerance_pct": 0.6, "min_touches": 2, "break_atr_mult": 0.5, "tp_r_mult": 1.5,
         "sl_atr_buffer": 0.3, "max_retest_bars": 30, "recovery_body_ratio": 0.5},
    ],
    # MAJOR Stratejisi - buyuk/likit coinler icin sifirdan tasarlanmis
    # (kirilim+ADX+hacim girisi, "chandelier" iz suren stop cikisi - bkz.
    # core/strategies/major_trend_rider.py). major_strategy_hunt.py ile
    # BTC/ETH/BNB/SOL/ZEC'te IS/OOS dogrulandi: en saglam ETH ve BNB 4h'de
    # (56 kombinasyon 4/5 sembolde tutarli PF>=1.1 gecti) - BTC/ZEC bu
    # mekanikte zayif kaldi, onlar icin ayri arastirma gerekebilir.
    "major_stratejisi": [
        {"breakout_len": 55, "adx_min": 20, "chandelier_mult": 2.5, "vol_mult": 1.3},
        {"breakout_len": 55, "adx_min": 25, "chandelier_mult": 3.0, "vol_mult": 1.3},
        {"breakout_len": 10, "adx_min": 30, "chandelier_mult": 4.0, "vol_mult": 1.0},
        {"breakout_len": 30, "adx_min": 20, "chandelier_mult": 2.5, "vol_mult": 1.3},
    ],
}


def split_is_oos(df: pd.DataFrame, is_ratio: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * is_ratio)
    return df.iloc[:cut], df.iloc[cut:]


def evaluate(df: pd.DataFrame, strategy_cls, params: dict, timeframe: str, market: str, costs: Costs) -> dict | None:
    if len(df) < 250:
        return None
    result = run_backtest(df, strategy_cls(**params), costs=costs)
    m = summarize(result, timeframe, market)
    return None if "error" in m else m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    bt_cfg = cfg["backtest_defaults"]
    costs = Costs(fee_bps=bt_cfg["fee_bps"], slippage_bps=bt_cfg["slippage_bps"])

    jobs = []  # (provider, symbol, timeframe, market)
    for symbol in cfg["binance"]["symbols"]:
        for tf in cfg["binance"]["timeframes"]:
            jobs.append(("binance", symbol, tf, "crypto"))
    for symbol in cfg["us_stocks"]["symbols"]:
        for tf in cfg["us_stocks"]["timeframes"]:
            jobs.append(("yahoo", symbol, tf, "stock"))
    for symbol in cfg["bist"]["symbols"]:
        for tf in cfg["bist"]["timeframes"]:
            jobs.append(("yahoo", symbol, tf, "stock"))

    if args.provider:
        jobs = [j for j in jobs if j[0] == args.provider]
    if args.timeframe:
        jobs = [j for j in jobs if j[2] == args.timeframe]

    # Yeni listelenmis / dusuk gecmisli sembollerde IS+OOS bolununce her
    # parca birkaç haftaya duser - o kadar az veriden cikan "harika Sharpe"
    # neredeyse her zaman tesadüftür, gercek edge degil. Ikisi de kaba ama
    # etkili filtre: toplam veri uzunlugu ve minimum islem sayisi.
    MIN_TOTAL_BARS = 1000
    MIN_TRADES = 5

    rows = []
    skipped_thin = 0
    skipped_few_trades = 0
    for provider, symbol, tf, market in jobs:
        df = datastore.get(provider, symbol, tf)
        if df.empty:
            print(f"[atlandi] {provider} {symbol} {tf} - onbellekte veri yok "
                  f"(once: python scripts/fetch_data.py)")
            continue
        if len(df) < MIN_TOTAL_BARS:
            skipped_thin += 1
            continue
        df_is, df_oos = split_is_oos(df)

        for strat_name, strat_cls in REGISTRY.items():
            for params in PARAM_GRID.get(strat_name, [{}]):
                m_is = evaluate(df_is, strat_cls, params, tf, market, costs)
                m_oos = evaluate(df_oos, strat_cls, params, tf, market, costs)
                if m_is is None or m_oos is None:
                    continue
                if m_is["islem_sayisi"] < MIN_TRADES or m_oos["islem_sayisi"] < MIN_TRADES:
                    skipped_few_trades += 1
                    continue
                rows.append({
                    "provider": provider, "symbol": symbol, "tf": tf, "strateji": strat_name,
                    "params": params,
                    "IS_sharpe": m_is["sharpe"], "OOS_sharpe": m_oos["sharpe"],
                    "IS_getiri_%": m_is["toplam_getiri_%"], "OOS_getiri_%": m_oos["toplam_getiri_%"],
                    "OOS_maxdd_%": m_oos["max_drawdown_%"], "OOS_islem": m_oos["islem_sayisi"],
                    "OOS_kazanma_%": m_oos["kazanma_orani_%"],
                    "OOS_profit_factor": m_oos["profit_factor"],
                })

    print(f"\n(Elendi: {skipped_thin} sembol yetersiz gecmis (<{MIN_TOTAL_BARS} mum), "
          f"{skipped_few_trades} kombinasyon yetersiz islem sayisi (<{MIN_TRADES}) yuzunden)")

    if not rows:
        print("Sonuc yok. Once 'python scripts/fetch_data.py' calistirdiniz mi?")
        return

    result_df = pd.DataFrame(rows)
    # Tutarlilik skoru: IS ve OOS ikisi de pozitif VE birbirine yakin olmali.
    result_df["tutarlilik_skoru"] = result_df[["IS_sharpe", "OOS_sharpe"]].min(axis=1) - \
        (result_df["IS_sharpe"] - result_df["OOS_sharpe"]).abs() * 0.5

    result_df = result_df.sort_values("tutarlilik_skoru", ascending=False)
    out_path = Path(__file__).resolve().parent.parent / "reports" / "scan_sonuclari.csv"
    out_path.parent.mkdir(exist_ok=True)
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n=== En tutarli {args.top} kombinasyon (IS ve OOS ikisinde de calisan) ===\n")
    display_cols = ["provider", "symbol", "tf", "strateji", "IS_sharpe", "OOS_sharpe",
                     "OOS_getiri_%", "OOS_maxdd_%", "OOS_islem", "OOS_kazanma_%", "OOS_profit_factor"]
    print(result_df[display_cols].head(args.top).to_string(index=False))

    # Yuksek kazanma orani aramasi: sadece kazanma orani degil, profit_factor
    # >= 1 (net kar) ve yeterli islem sayisi (>=10, istatistiksel guven icin
    # 5'in biraz uzeri) sarti da araniyor - yoksa "yuksek kazanma ama net
    # zararli" sahte kazananlar listeye sizar.
    high_wr = result_df[(result_df["OOS_kazanma_%"] >= 60) & (result_df["OOS_profit_factor"] >= 1.0)
                         & (result_df["OOS_islem"] >= 10)].sort_values("OOS_kazanma_%", ascending=False)
    print(f"\n=== Yuksek kazanma oranli VE net karli (>=60%, profit_factor>=1, >=10 islem) - {len(high_wr)} sonuc ===\n")
    if not high_wr.empty:
        print(high_wr[display_cols].head(20).to_string(index=False))
    else:
        print("(Bu esikleri gecen kombinasyon bulunamadi)")
    print(f"\nTam sonuclar: {out_path}")


if __name__ == "__main__":
    main()
