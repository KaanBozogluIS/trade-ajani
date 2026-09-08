"""Korelasyon Analizi - altcoinlerin BTC'ye (ya da secilen baska bir
referansa) gore ne kadar "bagli" hareket ettigini gosterir.

Gunluk/kaldiracli trader'in sorusu: "BTC kirilim yaptiginda hangi coin
DAHA HIZLI/BUYUK tepki verir?" - yuksek beta + yuksek korelasyon =
BTC'nin kaldiracli yansimasi (hizli hareket, ama risk de buyuk). Dusuk
korelasyon = BTC'den bagimsiz, kendi dinamigi olan coin.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import datastore
from core.correlation import compute_correlation_beta, log_returns, normalized_price

st.set_page_config(page_title="Korelasyon Analizi", page_icon="🔗", layout="wide")
st.title("🔗 Korelasyon Analizi — Altcoin ↔ BTC Karşılaştırması")
st.caption("Hangi altcoin BTC ile birlikte mi hareket ediyor, hangisi bağımsız? "
           "Yüksek beta = BTC hareket edince bu coin DAHA BÜYÜK tepki verir (hız da risk de artar).")

inv = datastore.describe_cache()
binance_inv = inv[inv["provider"] == "binance"] if not inv.empty else inv
if binance_inv.empty:
    st.warning("Önbellekte Binance verisi yok. Önce `python scripts/fetch_data.py` çalıştırın.")
    st.stop()

top1, top2, top3, top4 = st.columns([1.2, 1, 1, 1.4])
with top1:
    all_symbols = sorted(binance_inv["symbol"].unique())
    ref_symbol = st.selectbox("Referans sembol", all_symbols,
                               index=all_symbols.index("BTCUSDT") if "BTCUSDT" in all_symbols else 0)
with top2:
    tfs = sorted(binance_inv.loc[binance_inv["symbol"] == ref_symbol, "tf"].unique())
    timeframe = st.selectbox("Zaman dilimi", tfs, index=tfs.index("1h") if "1h" in tfs else 0)
with top3:
    lookback_n = st.number_input("Son N mum (korelasyon penceresi)", min_value=100, max_value=5000,
                                  value=720, step=100, help="1h için 720 ≈ son 30 gün")
with top4:
    min_bars = st.slider("Min. ortak bar (istatistiksel eşik)", 30, 500, 100, step=10)

st.divider()

ref_df = datastore.load("binance", ref_symbol, timeframe)
if ref_df.empty:
    st.error(f"{ref_symbol} ({timeframe}) için önbellekte veri yok.")
    st.stop()
ref_df = ref_df.tail(int(lookback_n))
ref_ret = log_returns(ref_df["close"])

candidates = sorted(binance_inv.loc[binance_inv["tf"] == timeframe, "symbol"].unique())
candidates = [s for s in candidates if s != ref_symbol]

rows = []
for sym in candidates:
    df = datastore.load("binance", sym, timeframe)
    if df.empty:
        continue
    df = df.tail(int(lookback_n))
    corr, beta, n = compute_correlation_beta(ref_ret, log_returns(df["close"]), min_overlap=min_bars)
    if n < min_bars:
        continue
    rows.append({"Sembol": sym, "Korelasyon": corr, "Beta": beta, "Ortak Bar": n})

if not rows:
    st.warning("Yeterli ortak veriye sahip sembol bulunamadı — lookback penceresini artırmayı deneyin.")
    st.stop()

corr_df = pd.DataFrame(rows).dropna(subset=["Korelasyon", "Beta"])


def _classify(row) -> str:
    if row["Korelasyon"] >= 0.7 and row["Beta"] >= 1.2:
        return "🚀 Yüksek Beta (BTC'yi büyütür)"
    if row["Korelasyon"] >= 0.7:
        return "🔗 Yakın Takip (BTC ile birlikte)"
    if row["Korelasyon"] <= 0.3:
        return "🧭 Bağımsız (BTC'den kopuk)"
    return "〰️ Orta"


corr_df["Sınıf"] = corr_df.apply(_classify, axis=1)
corr_df = corr_df.sort_values("Beta", ascending=False)

st.subheader(f"📊 {ref_symbol} referansına göre {len(corr_df)} sembol")
c1, c2, c3 = st.columns(3)
c1.metric("En yüksek Beta", corr_df.iloc[0]["Sembol"], f"{corr_df.iloc[0]['Beta']:.2f}x")
low_corr = corr_df.sort_values("Korelasyon").iloc[0]
c2.metric("En düşük korelasyon (en bağımsız)", low_corr["Sembol"], f"{low_corr['Korelasyon']:.2f}")
c3.metric("Ortalama korelasyon", f"{corr_df['Korelasyon'].mean():.2f}")

st.dataframe(
    corr_df.style.format({"Korelasyon": "{:.2f}", "Beta": "{:.2f}", "Ortak Bar": "{:.0f}"})
    .background_gradient(subset=["Beta"], cmap="RdYlGn", vmin=0, vmax=2)
    .background_gradient(subset=["Korelasyon"], cmap="RdYlGn", vmin=-1, vmax=1),
    use_container_width=True, hide_index=True, height=420,
)
st.caption("**Beta** > 1: BTC %1 hareket ederken bu coin ORTALAMA daha fazla hareket eder (kaldıraçlı gibi davranır). "
           "**Korelasyon** BTC ile aynı YÖNDE hareket etme derecesi (-1..+1). İkisi birlikte yüksekse, BTC'de net "
           "bir sinyal gördüğünde bu coin daha hızlı/büyük bir fırsat sunabilir — ama tersi de doğru, kayıp da büyür.")

st.divider()

# --------------------------------------------------------------------
st.subheader("📈 Fiyat Grafiği Karşılaştırması (yüzdesel, aynı eksende)")
sel1, sel2 = st.columns([1, 3])
with sel1:
    compare_symbol = st.selectbox("Karşılaştırılacak coin", corr_df["Sembol"].tolist())

cmp_df = datastore.load("binance", compare_symbol, timeframe).tail(int(lookback_n))
ref_norm = normalized_price(ref_df["close"])
cmp_norm = normalized_price(cmp_df["close"])

row = corr_df[corr_df["Sembol"] == compare_symbol].iloc[0]
st.caption(f"**{compare_symbol}** — Korelasyon: `{row['Korelasyon']:.2f}` · Beta: `{row['Beta']:.2f}x` · "
           f"Sınıf: {row['Sınıf']}")

fig = go.Figure()
fig.add_trace(go.Scatter(x=ref_norm.index, y=ref_norm.values, name=ref_symbol,
                          line=dict(color="#f7931a", width=2)))
fig.add_trace(go.Scatter(x=cmp_norm.index, y=cmp_norm.values, name=compare_symbol,
                          line=dict(color="#3b82f6", width=2)))
fig.update_layout(height=450, margin=dict(l=10, r=10, t=30, b=10),
                   yaxis_title="Değer (başlangıç=100)",
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --------------------------------------------------------------------
st.subheader("🗺️ Korelasyon × Beta Haritası")
scatter = go.Figure()
scatter.add_trace(go.Scatter(
    x=corr_df["Korelasyon"], y=corr_df["Beta"], mode="markers+text",
    text=corr_df["Sembol"], textposition="top center", textfont=dict(size=9),
    marker=dict(size=9, color=corr_df["Beta"], colorscale="RdYlGn", cmin=0, cmax=2,
                showscale=True, colorbar=dict(title="Beta")),
))
scatter.add_hline(y=1.0, line_dash="dot", line_color="gray")
scatter.add_vline(x=0.7, line_dash="dot", line_color="gray")
scatter.update_layout(height=550, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title="Korelasyon", yaxis_title="Beta")
st.plotly_chart(scatter, use_container_width=True)
st.caption("Sağ-üst köşe: BTC ile birlikte hareket eden VE onu büyüten coinler (günlük trader için en 'hızlı' "
           "fırsatlar). Sol taraf: BTC'den bağımsız, kendi haberi/dinamiği olan coinler.")
