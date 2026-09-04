"""Canli Veri Gezgini - TradingView/Investing tarzi, kendiliginden yenilenen
mum grafigi ve fiyat kartlari.

Onceki versiyon SADECE onbellekteki (durgun) veriyi gosteriyordu. Bu
versiyon `st.fragment(run_every=...)` ile SADECE grafik+istatistik
bolgesini periyodik olarak yeniden cizer (secim kutulari yerinde kalir,
tum sayfa yeniden yuklenmez) ve her yenilemede Binance/Yahoo'dan GERCEKTEN
yeni veri ceker (datastore.update - sadece son mumdan itibaren, hizli).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core import datastore
from core.providers.base import DataProviderError
from core.providers.binance import get_24h_stats
from core.timeframes import to_timedelta
from core.tz import format_istanbul, to_istanbul

st.set_page_config(page_title="Canlı Veri Gezgini", page_icon="📡", layout="wide")

st.markdown("""
<style>
  div[data-testid="stMetricValue"] {font-size: 1.6rem;}
  div[data-testid="stMetricDelta"] {font-size: 1rem;}
</style>
""", unsafe_allow_html=True)

st.title("📡 Canlı Veri Gezgini")

inv = datastore.describe_cache()
if inv.empty:
    st.warning("Önbellekte henüz veri yok. Terminalde şunu çalıştırın: "
               "`python scripts/fetch_data.py`")
    st.stop()

# ---------------------------------------------------------------------
# Ust secim satiri
# ---------------------------------------------------------------------
sel1, sel2, sel3, sel4, sel5 = st.columns([1.2, 1.2, 1, 1.4, 1.2])
with sel1:
    provider = st.selectbox("Kaynak", sorted(inv["provider"].unique()))
with sel2:
    symbols = sorted(inv.loc[inv["provider"] == provider, "symbol"].unique())
    symbol = st.selectbox("Sembol", symbols)
with sel3:
    tfs = sorted(inv.loc[(inv["provider"] == provider) & (inv["symbol"] == symbol), "tf"].unique())
    timeframe = st.selectbox("Zaman dilimi", tfs)
with sel4:
    refresh_label = st.selectbox(
        "Otomatik yenileme",
        ["5 saniye", "10 saniye", "30 saniye", "1 dakika", "Kapalı"],
        index=1,
        help="Kısa aralıklar zoom/kaydırmayı sık sık sıfırlar - grafiği incelerken 'Kapalı' seçebilirsin.",
    )
with sel5:
    n_bars = st.slider("Gösterilecek mum", 50, 1000, 200, step=50)

_REFRESH_SECONDS = {"5 saniye": 5, "10 saniye": 10, "30 saniye": 30, "1 dakika": 60, "Kapalı": None}
refresh_seconds = _REFRESH_SECONDS[refresh_label]

st.divider()


def _fetch_live(provider: str, symbol: str, timeframe: str) -> pd.DataFrame | None:
    """Onbellegi son kapali mumdan itibaren tazeler; basarisiz olursa (ag
    hatasi, API limiti) onbellekteki en son hali sessizce kullanir."""
    try:
        return datastore.update(provider, symbol, timeframe, start="2025-01-01")
    except DataProviderError:
        return datastore.load(provider, symbol, timeframe)


# ---------------------------------------------------------------------
# Canli bolge - sadece bu fonksiyon periyodik yenilenir
# ---------------------------------------------------------------------
@st.fragment(run_every=refresh_seconds)
def live_panel() -> None:
    df = _fetch_live(provider, symbol, timeframe)
    if df is None or df.empty:
        st.error("Bu kombinasyon için veri bulunamadı.")
        return

    last_close = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else last_close
    bar_change_pct = (last_close / prev_close - 1.0) * 100 if prev_close else 0.0
    is_closed = df.index[-1] + to_timedelta(timeframe) <= pd.Timestamp.now(tz="UTC")

    # --- Fiyat karti: binance icin gercek 24s istatistigi, degilse mumlardan yaklasik ---
    change_24h = None
    high_24h = low_24h = vol_24h = None
    if provider == "binance":
        try:
            stats = get_24h_stats([symbol.upper()])
            if not stats.empty:
                row = stats.iloc[0]
                change_24h = float(row["change_24h_pct"])
                high_24h, low_24h, vol_24h = float(row["high_24h"]), float(row["low_24h"]), float(row["quote_volume_24h"])
        except DataProviderError:
            pass
    if change_24h is None:
        # yaklasik: zaman diliminden bagimsiz, elimizdeki mumlardan son ~24 saatlik degisim
        lookback = df[df.index >= df.index[-1] - pd.Timedelta(hours=24)]
        if len(lookback) > 1:
            change_24h = (last_close / float(lookback["close"].iloc[0]) - 1.0) * 100
            high_24h, low_24h = float(lookback["high"].max()), float(lookback["low"].min())

    top = st.columns([1.4, 1, 1, 1, 1.2])
    top[0].metric(f"{symbol} · {timeframe}", f"{last_close:.6g}",
                   delta=f"{bar_change_pct:+.2f}% (bu mum)")
    top[1].metric("24s Değişim", f"{change_24h:+.2f}%" if change_24h is not None else "—")
    top[2].metric("24s Yüksek", f"{high_24h:.6g}" if high_24h is not None else "—")
    top[3].metric("24s Düşük", f"{low_24h:.6g}" if low_24h is not None else "—")
    if vol_24h is not None:
        top[4].metric("24s Hacim", f"${vol_24h:,.0f}")
    else:
        top[4].metric("Toplam Mum", f"{len(df):,}")

    status = "🟢 CANLI" if refresh_seconds else "⏸️ Duraklatıldı"
    st.caption(f"{status} · Son güncelleme: {format_istanbul(datetime.now(timezone.utc))} · "
               f"Son mum {'kapandı' if is_closed else 'HENÜZ OLUŞUYOR (anlık)'}: "
               f"{format_istanbul(df.index[-1])}")

    # --- Grafik ---
    plot_df = df.tail(n_bars)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22],
                         vertical_spacing=0.02)
    fig.add_trace(go.Candlestick(
        x=plot_df.index, open=plot_df["open"], high=plot_df["high"],
        low=plot_df["low"], close=plot_df["close"],
        increasing_line_color="#16a34a", decreasing_line_color="#dc2626", name=symbol,
    ), row=1, col=1)
    vol_colors = ["#16a34a" if c >= o else "#dc2626" for o, c in zip(plot_df["open"], plot_df["close"])]
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df["volume"], marker_color=vol_colors,
                          showlegend=False, name="Hacim"), row=2, col=1)
    fig.update_layout(
        height=600, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10),
        template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white",
        showlegend=False,
    )
    fig.update_yaxes(title_text="Fiyat", row=1, col=1)
    fig.update_yaxes(title_text="Hacim", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{provider}_{symbol}_{timeframe}")

    with st.expander("Ham veri tablosu (son 500 mum)"):
        st.dataframe(df.tail(500).sort_index(ascending=False), use_container_width=True, height=400)


live_panel()
