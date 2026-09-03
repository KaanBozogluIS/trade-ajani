"""Trade Ajani - ana panel giris sayfasi: canli piyasa ozeti.

Calistirma: scripts\\panel_ac.bat (veya: streamlit run dashboard/Home.py)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from core import datastore
from core.providers.binance import DataProviderError, get_24h_stats

st.set_page_config(page_title="Trade Ajanı", page_icon="📈", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 2rem; padding-bottom: 2rem;}
  div[data-testid="stMetricValue"] {font-size: 1.4rem;}
</style>
""", unsafe_allow_html=True)

st.title("📈 Trade Ajanı")
st.caption("Strateji araştırma, backtest ve canlı sinyal paneli — gerçek para ile emir göndermez.")

with st.sidebar:
    st.header("Durum")
    inv = datastore.describe_cache()
    st.metric("Önbellekteki seri sayısı", len(inv))
    if not inv.empty:
        st.metric("Toplam mum", f"{inv['bars'].sum():,}")
    st.divider()
    st.caption("Sayfalar soldaki menüden: Veri Gezgini, Strateji Taraması, "
               "Backtest, İzleme & Sinyaller.")

st.subheader("🟢 Canlı Piyasa — Binance USDT Pariteleri")
st.caption("Kaynak: Binance genel API, doğrudan borsadan — gecikmesiz. "
           "Sayfayı yenilemek güncel fiyatı çeker.")

col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    search = st.text_input("Sembol ara (örn. BTC, SOL, DOGE)", "").strip().upper()
with col_b:
    sort_by = st.selectbox("Sırala", ["24s Hacim", "24s Değişim %", "Fiyat"], index=0)
with col_c:
    limit = st.selectbox("Göster", [25, 50, 100, 250, "Hepsi"], index=1)

refresh = st.button("🔄 Fiyatları yenile", use_container_width=False)

@st.cache_data(ttl=15, show_spinner="Binance'ten canlı fiyatlar çekiliyor...")
def _load_ticker(_cache_bust: float) -> pd.DataFrame:
    return get_24h_stats()

try:
    df = _load_ticker(time.time() // 15 if not refresh else time.time())
except DataProviderError as exc:
    st.error(f"Binance'e ulaşılamadı: {exc}")
    df = pd.DataFrame()

if not df.empty:
    df = df[df["symbol"].str.endswith("USDT")].copy()
    if search:
        df = df[df["symbol"].str.contains(search)]

    sort_col = {"24s Hacim": "quote_volume_24h", "24s Değişim %": "change_24h_pct", "Fiyat": "price"}[sort_by]
    df = df.sort_values(sort_col, ascending=False)
    if limit != "Hepsi":
        df = df.head(int(limit))

    show = df.rename(columns={
        "symbol": "Sembol", "price": "Fiyat", "change_24h_pct": "24s Değişim %",
        "quote_volume_24h": "24s Hacim (USDT)", "high_24h": "24s Yüksek", "low_24h": "24s Düşük",
    })[["Sembol", "Fiyat", "24s Değişim %", "24s Hacim (USDT)", "24s Yüksek", "24s Düşük"]]

    st.dataframe(
        show,
        use_container_width=True,
        height=560,
        hide_index=True,
        column_config={
            "Fiyat": st.column_config.NumberColumn(format="%.6g"),
            "24s Değişim %": st.column_config.NumberColumn(format="%.2f%%"),
            "24s Hacim (USDT)": st.column_config.NumberColumn(format="$%,.0f"),
            "24s Yüksek": st.column_config.NumberColumn(format="%.6g"),
            "24s Düşük": st.column_config.NumberColumn(format="%.6g"),
        },
    )
    st.caption(f"{len(df)} parite gösteriliyor · son güncelleme: az önce")
else:
    st.info("Veri bekleniyor...")
