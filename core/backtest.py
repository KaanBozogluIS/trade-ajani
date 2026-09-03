"""Vektorel olmayan (bar-by-bar), maliyet-farkinda backtest motoru.

Bilerek bar-by-bar dongu kullanildi: vektorel backtestler stop-loss /
take-profit / pozisyon boyutlandirma gibi 'yol-bagimli' kurallarda sessizce
yanlis sonuc uretmeye cok yatkindir. Bu yavastir ama dogrudur; hiz
gerektiginde numba eklenebilir - once dogruluk.

Ileriye-bakma kacagina karsi tasarim karari:
  t mumunda uretilen sinyal, t+1 mumunun ACILIS fiyatinda uygulanir.
  Bu, 't kapaninda karar ver, bir sonraki mumda gir' gercek disiplinini
  taklit eder. Ayni mumun kapanisinda hem karar veren hem oradan giren
  backtestler sistematik olarak sisirilmis sonuc verir.

TAKE-PROFIT / STOP-LOSS (bracket) destegi:
  Strateji, StrategyResult.stop_loss / take_profit alanlarinda (opsiyonel)
  bir FIYAT SEVIYESI dondurebilir. Pozisyon acildiginda o bardaki seviye
  "kilitlenir" (gercek bir bracket emri gibi) ve pozisyon KAPANANA KADAR
  sabit kalir - her barda yeniden hesaplanmaz.
  MUHAFAZAKAR VARSAYIM: bir barin YUKSEK ve DUSUK degeri arasinda hem SL
  hem TP teorik olarak tetiklenebiliyorsa (OHLC verisinden hangisinin ONCE
  geldigini bilemeyiz - tick verisi yok), KOTU ihtimali varsayiyoruz: SL
  once tetiklenir. Bu, performansi ABARTMAMAK icin bilinçli bir secim.

IZ SUREN (TRAILING) STOP DESTEGI:
  trailing_stop=True verilirse, stop_loss ARTIK giriste kilitlenmiyor -
  HER BARDA strategy'nin dondurdugu (varsa) yeni degerle GUNCELLENIYOR
  (sadece lehte hareket edip etmedigi stratejinin sorumlulugunda - motor
  bunu zorlamiyor). Boyle bir strateji, StrategyResult.stop_loss'ta pozisyon
  acikken HER BARDA guncel "iz suren" seviyeyi dondurmelidir (sadece giris
  barinda degil). Varsayilan (False) eski davranistir: stop_loss sadece
  giriste okunur ve pozisyon kapanana kadar SABIT kalir.

RISK-BAZLI POZISYON BUYUKLUGU (kaldiracli islem icin):
  Varsayilan davranis (risk_per_trade_pct=None) her islemde sermayenin
  TAMAMINI kullanir - kaldiracsiz/spot dusunulmustur. Gercek kaldiracli
  trader'lar boyle YAPMAZ: her islemde sermayenin KUCUK bir yuzdesini
  (ornegin %1-2) riske atarlar, kaldiraci sadece o riski verirken pozisyon
  BUYUKLUGUNU ayarlamak icin kullanirlar. risk_per_trade_pct verilirse:
      pozisyon_carpani = min(max_leverage, risk_per_trade_pct / stop_mesafesi_%)
  Yani stop dar ise (riskli/hassas giris) daha az kaldirac gerekir (ayni
  riski daha kucuk pozisyonla tutturursun); stop genis ise daha fazla
  kaldirac gerekir - max_leverage bunu ustten sinirlar. Strateji stop_loss
  DONDURMEZSE bu hesap yapilamaz, carpan 1.0'a (kaldiracsiz) duser.
  BILINEN SINIRLAMA: fiyat bir barda SL seviyesini "gap" ile atlarsa (ornegin
  ani haber), gercek dolum SL fiyatindan daha kotu olabilir - bu motor byle
  bir kaymayi modellemiyor, bu yuzden YUKSEK kaldiracta gercek kayip burada
  hesaplanandan DAHA BUYUK olabilir.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy import Signal, Strategy


@dataclass
class Costs:
    fee_bps: float = 10.0        # islem basina, taraf basina (Binance spot ~%0.1 = 10bps)
    slippage_bps: float = 5.0    # emrin gerceklestigi fiyatta varsayilan kayma
    spread_bps: float = 0.0      # ek olarak sabit spread (hisse icin kullanisli)

    @property
    def total_bps(self) -> float:
        return self.fee_bps + self.slippage_bps + self.spread_bps


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: pd.DataFrame
    position: pd.Series
    costs: Costs

    @property
    def returns(self) -> pd.Series:
        return self.equity.pct_change().fillna(0.0)


def run(
    df: pd.DataFrame,
    strategy: Strategy,
    costs: Costs = Costs(),
    initial_capital: float = 10_000.0,
    allow_short: bool = True,
    risk_per_trade_pct: float | None = None,
    max_leverage: float = 1.0,
    trailing_stop: bool = False,
) -> BacktestResult:
    result = strategy.generate(df)
    signal = result.signal.reindex(df.index).fillna(Signal.FLAT).astype(int)
    if not allow_short:
        signal = signal.clip(lower=0)

    # Sinyal t'de karar verilir, t+1 acilisinda uygulanir -> 1 bar kaydir.
    target_position = signal.shift(1).fillna(0).astype(int)

    has_sl = result.stop_loss is not None
    has_tp = result.take_profit is not None
    entry_sl = (result.stop_loss.reindex(df.index) if has_sl
                else pd.Series(np.nan, index=df.index)).shift(1)
    entry_tp = (result.take_profit.reindex(df.index) if has_tp
                else pd.Series(np.nan, index=df.index)).shift(1)
    entry_sl_arr, entry_tp_arr = entry_sl.to_numpy(), entry_tp.to_numpy()

    open_, close = df["open"].to_numpy(), df["close"].to_numpy()
    high_, low_ = df["high"].to_numpy(), df["low"].to_numpy()
    idx = df.index
    n = len(df)

    # Muhasebe modeli: 'capital' pozisyon KAPALIYKEN duz sermaye buyuklugu.
    # Pozisyon aciksa equity, capital'i giris fiyatina gore mark-to-market
    # eder. Ayri 'cash' ve 'qty' degiskenleri tutup carpip cikarmak yerine
    # dogrudan getiri carpani kullaniyoruz - boylece giris/cikista notional'i
    # yanlislikla iki kez saymak (klasik backtest hatasi) imkansiz hale gelir.
    equity = np.empty(n, dtype="float64")
    position = np.zeros(n, dtype="int64")
    capital = initial_capital
    pos_dir = 0             # -1, 0, 1
    entry_price = np.nan
    entry_time = None
    active_sl = active_tp = None
    active_size_mult = 1.0  # kaldirac carpani - risk_per_trade_pct verilmezse hep 1.0
    trade_rows: list[dict] = []

    fee_rate = costs.total_bps / 10_000.0

    def _close_trade(exit_price: float, exit_time, reason: str) -> None:
        nonlocal capital, pos_dir
        exec_price = exit_price * (1 - fee_rate) if pos_dir > 0 else exit_price * (1 + fee_rate)
        trade_return = pos_dir * (exec_price / entry_price - 1.0) * active_size_mult
        pnl = capital * trade_return
        capital = max(capital * (1.0 + trade_return), 0.0)
        trade_rows.append({
            "entry_time": entry_time, "exit_time": exit_time,
            "side": "long" if pos_dir > 0 else "short",
            "entry_price": entry_price, "exit_price": exec_price,
            "pnl": pnl, "return_pct": trade_return * 100.0, "exit_reason": reason,
            "leverage": active_size_mult,
        })
        pos_dir = 0

    for i in range(n):
        if trailing_stop and pos_dir != 0:
            new_sl = entry_sl_arr[i]
            if not np.isnan(new_sl):
                active_sl = float(new_sl)

        bracket_hit = None  # ('stop_loss'|'take_profit', fiyat) ya da None
        if pos_dir != 0:
            sl_touched = active_sl is not None and (
                (pos_dir > 0 and low_[i] <= active_sl) or (pos_dir < 0 and high_[i] >= active_sl)
            )
            tp_touched = active_tp is not None and (
                (pos_dir > 0 and high_[i] >= active_tp) or (pos_dir < 0 and low_[i] <= active_tp)
            )
            if sl_touched:
                bracket_hit = ("stop_loss", active_sl)
            elif tp_touched:
                bracket_hit = ("take_profit", active_tp)

        if bracket_hit is not None:
            reason, price = bracket_hit
            _close_trade(price, idx[i], reason)
            active_sl = active_tp = None
            equity[i] = capital
            position[i] = 0
            continue  # bu barda yeni giris yok - sinyal zaten bir onceki barda karar verildi

        want = int(target_position.iloc[i])
        if want != pos_dir:
            price = open_[i]
            if pos_dir != 0:
                _close_trade(price, idx[i], "signal")
                active_sl = active_tp = None

            if want != 0:
                exec_price = price * (1 + fee_rate) if want > 0 else price * (1 - fee_rate)
                entry_price = exec_price
                entry_time = idx[i]
                pos_dir = want
                sl_level = entry_sl_arr[i]
                tp_level = entry_tp_arr[i]
                active_sl = float(sl_level) if not np.isnan(sl_level) else None
                active_tp = float(tp_level) if not np.isnan(tp_level) else None
                if risk_per_trade_pct is not None and active_sl is not None:
                    stop_dist_pct = abs(entry_price - active_sl) / entry_price
                    active_size_mult = (min(max_leverage, (risk_per_trade_pct / 100.0) / stop_dist_pct)
                                         if stop_dist_pct > 1e-9 else 1.0)
                else:
                    active_size_mult = 1.0

        if pos_dir == 0:
            equity[i] = capital
        else:
            unrealized = pos_dir * (close[i] / entry_price - 1.0) * active_size_mult
            equity[i] = max(capital * (1.0 + unrealized), 0.0)
        position[i] = pos_dir

    trades = pd.DataFrame(trade_rows)

    return BacktestResult(
        equity=pd.Series(equity, index=idx, name="equity"),
        trades=trades,
        position=pd.Series(position, index=idx, name="position"),
        costs=costs,
    )
