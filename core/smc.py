"""Smart Money Concepts (ICT/SMC) yapi taslari.

Bunlar "gostergeler" degil, PIYASA YAPISI oku(n)ma araclari: pivot noktalari
(swing high/low), yapi kirilimi (BOS - break of structure), fiyat
dengesizligi (FVG - fair value gap). Hepsi CAUSAL - yani t anindaki deger
sadece t'ye kadar bilinen veriden hesaplanir.

ONEMLI DURUSTLUK NOTU: Gercek "likidasyon bolgeleri" (borsalardaki
kaldiracli pozisyonlarin hangi fiyatta zorla kapatilacagi), acik pozisyon
(open interest) verisi gerektirir - bu bizim ucretsiz Binance kline
API'mizde YOK, ozel/ucretli bir veri kaynagi (ornegin Coinglass) gerekir.
Bunun yerine ICT/SMC tuccarlarinin fiilen kullandigi teknik VEKIL'i
kullaniyoruz: "esit tepe/dip" (equal highs/lows) - birbirine yakin birden
fazla swing noktasi, cogu tuccarin stop-loss'unun kumelendigi, dolayisiyla
"likidite havuzu" sayilan seviyelerdir. Bu core/strategies/liquidity_sweep_reversal.py
icinde kullaniliyor.

ONEMLI - GECIKME (LAG): Bir swing high/low, ancak `right` bar SONRASINDA
"onaylanir" (o barin gercekten yerel bir zirve/dip oldugu ancak sonraki
`right` bar gelince belli olur). Bu yuzden `confirmed_*` fonksiyonlari
degerleri `right` bar KAYDIRIR - t anindaki strateji, t aninda henuz
onaylanmamis bir swing'i GOREMEZ. Bu kaydirmayi atlamak klasik bir
ileriye-bakma (lookahead) hatasidir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def swing_points(df: pd.DataFrame, left: int = 5, right: int = 5) -> tuple[pd.Series, pd.Series]:
    """Fraktal pivot noktalari: bar i, [i-left, i+right] penceresindeki en
    yuksek/en dusuksa swing high/low sayilir. HAM (henuz onaylanmamis)
    etiketlerdir - dogrudan sinyal uretiminde kullanma, confirmed_swings'i
    kullan.
    """
    window = left + right + 1
    roll_max = df["high"].rolling(window, center=True, min_periods=window).max()
    roll_min = df["low"].rolling(window, center=True, min_periods=window).min()
    is_high = (df["high"] == roll_max).fillna(False)
    is_low = (df["low"] == roll_min).fillna(False)
    return is_high, is_low


def confirmed_swings(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    """t aninda BILINEN (onaylanmis) en son swing high/low fiyatlari.

    `right` bar gecikmeli - bkz. modul dokumantasyonu.
    """
    is_high, is_low = swing_points(df, left, right)
    conf_high_flag = is_high.shift(right).fillna(False)
    conf_low_flag = is_low.shift(right).fillna(False)
    swing_high_price = df["high"].shift(right).where(conf_high_flag)
    swing_low_price = df["low"].shift(right).where(conf_low_flag)
    return pd.DataFrame({
        "swing_high_event": conf_high_flag,       # bu barda YENI bir swing high onaylandi
        "swing_low_event": conf_low_flag,
        "swing_high_price": swing_high_price,      # o barda onaylanan fiyat (event disinda NaN)
        "swing_low_price": swing_low_price,
        "last_swing_high": swing_high_price.ffill(),  # o ana kadar bilinen en son swing high
        "last_swing_low": swing_low_price.ffill(),
    })


def market_structure(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    """Basit yapi/BOS (break of structure) modeli.

    Fiyat son onayli swing high'in USTUNE kaparsa yapi 'yukselis' (1) olur;
    son onayli swing low'un ALTINA kaparsa 'dusus' (-1) olur; aksi halde
    onceki durum korunur. `structure_up_event`/`structure_down_event`,
    yapinin TAM O BARDA degistigi (yeni bir BOS oldugu) anlari isaretler -
    Order Block tespiti bu olaylari kullanir.
    """
    sw = confirmed_swings(df, left, right)
    close = df["close"]
    bos_up = close > sw["last_swing_high"]
    bos_down = close < sw["last_swing_low"]
    raw = pd.Series(np.where(bos_up, 1, np.where(bos_down, -1, np.nan)), index=df.index)
    structure = raw.ffill().fillna(0).astype("int64")
    prev = structure.shift(1).fillna(0)
    return pd.DataFrame({
        "structure": structure,
        "structure_up_event": (structure == 1) & (prev != 1),
        "structure_down_event": (structure == -1) & (prev != -1),
    })


def fair_value_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """FVG (Fair Value Gap) - 3 ardisik mumda ortadaki mumun buyuk hareketi
    yuzunden 1. ve 3. mum arasinda fiyatin hic islem gormedigi bir bosluk
    olusmasi. Fiyatin bu bosluga geri donup "doldurma" egilimi ICT
    literaturunun temel varsayimlarindan biridir.
    """
    high, low = df["high"], df["low"]
    bull_fvg = low > high.shift(2)
    bear_fvg = high < low.shift(2)
    return pd.DataFrame({
        "bull_fvg": bull_fvg.fillna(False),
        "bull_gap_top": low.where(bull_fvg),
        "bull_gap_bottom": high.shift(2).where(bull_fvg),
        "bear_fvg": bear_fvg.fillna(False),
        "bear_gap_top": low.shift(2).where(bear_fvg),
        "bear_gap_bottom": high.where(bear_fvg),
    })
