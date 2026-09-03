"""Ampirik faktor arastirmasi.

Literaturden strateji kopyalamak yerine, SORUYU DOGRUDAN VERIYE SORUYORUZ:
"su an olculebilen hangi ozellik (feature), ileride ne kadar getiri
geldigini onceden haber veriyor?"

Yontem (klasik faktor arastirmasi / "quantile sort"):
  1. Evrendeki her sembol icin bir dizi ozellik hesapla (hacim orani, RSI,
     ATR yuzdesi, N-bar yuksek/dusukten uzaklik, trend egimi, ADX, kisa/orta
     vadeli getiri, Bollinger icindeki konum, ardisik yukselis sayisi...).
  2. Her bar icin "ileri donuk getiri"yi (t'den t+H bar sonrasina kadar) hesapla.
     Bu SADECE arastirma icin - gercek strateji backtesti gibi ileriye
     bakmiyor, ciinki burada "X ozelligi Y getiriyi onceden haber veriyor mu"
     sorusunun kendisini test ediyoruz (supervised ogrenmedeki 'target' ile
     ayni mantik - klasik backtest degil, KESIF calismasi).
  3. TUM sembolleri TEK bir havuzda birlestir (tek coinin sansı degil, evren
     genelinde tekrarlayan bir orunti mi arıyoruz).
  4. Her ozelligi 5 dilime (quantile) bol, her dilimde ortalama ileri getiriyi
     olc. GUCLU VE MONOTON bir iliski (dilim arttikca getiri de duzenli
     artiyor/azaliyorsa) gercek sinyal adayidir - rastgele gurultu boyle
     duzenli bir siralama uretmez.
  5. Spearman IC (Information Coefficient): ozellik sirasi ile ileri getiri
     sirasinin korelasyonu. |IC| > ~0.02-0.03 havuzlanmis, binlerce
     gozlemli bir ornekte bile dikkate deger sayilir (tek tek islemler
     gurultulu olsa da, ortalamada tutarli bir kenar).

Kullanim:
    python research/factor_lab.py --timeframe 1h --horizon 24 --top-symbols 40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yaml

from core import datastore
from core import indicators as ta

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yaml"


def consecutive_up(close: pd.Series) -> pd.Series:
    """Kac bardir ust uste yukselis var (0 = son bar dustu/degismedi)."""
    sign = np.sign(close.diff())
    is_up = sign > 0
    grp = (~is_up).cumsum()
    run_len = is_up.groupby(grp).cumsum()
    return run_len.where(is_up, 0.0)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    bb = ta.bollinger(df["close"], 20, 2.0)
    band_width = (bb["upper"] - bb["lower"]).replace(0.0, np.nan)
    feats = pd.DataFrame(index=df.index)
    feats["vol_ratio"] = df["volume"] / df["volume"].rolling(20, min_periods=20).mean()
    feats["rsi14"] = ta.rsi(df["close"], 14)
    feats["atr_pct"] = ta.atr(df, 14) / df["close"] * 100.0
    feats["dist_high20_%"] = (df["close"] - df["high"].rolling(20, min_periods=20).max()) / df["close"] * 100.0
    feats["dist_low20_%"] = (df["close"] - df["low"].rolling(20, min_periods=20).min()) / df["close"] * 100.0
    feats["ema_slope50"] = ta.slope(ta.ema(df["close"], 50), 20)
    feats["adx14"] = ta.adx(df, 14)["adx"]
    feats["ret_5_%"] = df["close"].pct_change(5) * 100.0
    feats["ret_20_%"] = df["close"].pct_change(20) * 100.0
    feats["bb_pos"] = (df["close"] - bb["lower"]) / band_width
    feats["consec_up"] = consecutive_up(df["close"])
    return feats


def forward_return(df: pd.DataFrame, horizon: int) -> pd.Series:
    return (df["close"].shift(-horizon) / df["close"] - 1.0) * 100.0


def quantile_report(pooled: pd.DataFrame, feature_cols: list[str], n_bins: int = 5) -> pd.DataFrame:
    rows = []
    for col in feature_cols:
        sub = pooled[[col, "fwd_ret"]].dropna()
        if len(sub) < 500:
            continue
        ic = sub[col].corr(sub["fwd_ret"], method="spearman")
        try:
            sub["bin"] = pd.qcut(sub[col], n_bins, labels=False, duplicates="drop")
        except ValueError:
            continue
        by_bin = sub.groupby("bin")["fwd_ret"].agg(["mean", "count"])
        if len(by_bin) < 2:
            continue
        spread = by_bin["mean"].iloc[-1] - by_bin["mean"].iloc[0]
        monotonic = by_bin["mean"].is_monotonic_increasing or by_bin["mean"].is_monotonic_decreasing
        rows.append({
            "feature": col, "IC_spearman": round(ic, 4),
            "en_dusuk_dilim_ort_%": round(by_bin["mean"].iloc[0], 3),
            "en_yuksek_dilim_ort_%": round(by_bin["mean"].iloc[-1], 3),
            "spread_%": round(spread, 3), "monoton": monotonic, "n": int(sub[col].count()),
        })
    return pd.DataFrame(rows).sort_values("IC_spearman", key=lambda s: s.abs(), ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--horizon", type=int, default=24, help="ileri-donuk getiri ufku, bar cinsinden")
    parser.add_argument("--top-symbols", type=int, default=40)
    args = parser.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    symbols = cfg["binance"]["symbols"][: args.top_symbols]

    frames = []
    used, skipped = 0, 0
    for sym in symbols:
        df = datastore.get("binance", sym, args.timeframe)
        if len(df) < 1500:
            skipped += 1
            continue
        feats = build_features(df)
        feats["fwd_ret"] = forward_return(df, args.horizon)
        feats["symbol"] = sym
        frames.append(feats)
        used += 1

    pooled = pd.concat(frames, ignore_index=True)
    pooled = pooled.replace([np.inf, -np.inf], np.nan)
    feature_cols = [c for c in pooled.columns if c not in ("fwd_ret", "symbol")]

    print(f"Havuzlanan gozlem: {len(pooled):,} bar ({used} sembol kullanildi, {skipped} sembol atlandi - yetersiz gecmis)")
    print(f"Zaman dilimi: {args.timeframe}, ileri-donuk ufuk: {args.horizon} bar\n")

    report = quantile_report(pooled, feature_cols)
    print("=== Tum ozelliklerin siralamasi (|IC| buyuklugune gore) ===\n")
    print(report.to_string(index=False))

    out_path = Path(__file__).resolve().parent.parent / "reports" / "factor_lab_sonuclari.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_path, index=False)
    print(f"\nTam rapor: {out_path}")

    # En guclu 2 ozelligin BIRLIKTE (ikisi de en iyi dilimindeyken) etkisine bak -
    # tek basina zayif iki ozellik bir arada guclu bir sinyal olusturabilir.
    if len(report) >= 2:
        top2 = report.head(2)["feature"].tolist()
        print(f"\n=== En guclu 2 ozelligin BIRLIKTE etkisi: {top2} ===")
        sub = pooled[top2 + ["fwd_ret"]].dropna()
        for col in top2:
            sub[f"{col}_yuksek"] = sub[col] >= sub[col].quantile(0.8)
            sub[f"{col}_dusuk"] = sub[col] <= sub[col].quantile(0.2)
        baseline = sub["fwd_ret"].mean()
        both_high = sub[sub[f"{top2[0]}_yuksek"] & sub[f"{top2[1]}_yuksek"]]
        both_low = sub[sub[f"{top2[0]}_dusuk"] & sub[f"{top2[1]}_dusuk"]]
        print(f"Genel ortalama ileri getiri: {baseline:.3f}%")
        print(f"Ikisi de EN YUKSEK dilimde ({len(both_high)} gozlem): {both_high['fwd_ret'].mean():.3f}%")
        print(f"Ikisi de EN DUSUK dilimde ({len(both_low)} gozlem): {both_low['fwd_ret'].mean():.3f}%")


if __name__ == "__main__":
    main()
