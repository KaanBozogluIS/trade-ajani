"""Onbellekteki OHLCV verisini tablo + mum grafigi olarak gezinme sayfasi."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.graph_objects as go
import streamlit as st
import yaml

from core import datastore

st.set_page_config(page_title="Veri Gezgini", page_icon="🗂️", layout="wide")
st.title("🗂️ Veri Gezgini")

ROOT = Path(__file__).resolve().parent.parent.parent
cfg = yaml.safe_load((ROOT / "config" / "universe.yaml").read_text(encoding="utf-8"))

inv = datastore.describe_cache()
if inv.empty:
    st.warning("Önbellekte henüz veri yok. Terminalde şunu çalıştırın: "
               "`python scripts/fetch_data.py`")
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    provider = st.selectbox("Kaynak", sorted(inv["provider"].unique()))
with col2:
    symbols = sorted(inv.loc[inv["provider"] == provider, "symbol"].unique())
    symbol = st.selectbox("Sembol", symbols)
with col3:
    tfs = sorted(inv.loc[(inv["provider"] == provider) & (inv["symbol"] == symbol), "tf"].unique())
    timeframe = st.selectbox("Zaman dilimi", tfs)

n_bars = st.slider("Grafikte gösterilecek son mum sayısı", 50, 2000, 300, step=50)

df = datastore.load(provider, symbol, timeframe)
if df.empty:
    st.error("Bu kombinasyon için veri bulunamadı.")
    st.stop()

plot_df = df.tail(n_bars)

fig = go.Figure(data=[go.Candlestick(
    x=plot_df.index, open=plot_df["open"], high=plot_df["high"],
    low=plot_df["low"], close=plot_df["close"],
    increasing_line_color="#16a34a", decreasing_line_color="#dc2626", name=symbol,
)])
fig.update_layout(
    height=560, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10),
    template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white",
    title=f"{symbol} · {timeframe} · {provider}",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Özet")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam mum", f"{len(df):,}")
c2.metric("İlk mum", str(df.index.min().date()))
c3.metric("Son mum", str(df.index.max()))
c4.metric("Son kapanış", f"{df['close'].iloc[-1]:.6g}")

with st.expander("Ham veri tablosu (son 500 mum)"):
    st.dataframe(df.tail(500).sort_index(ascending=False), use_container_width=True, height=400)
