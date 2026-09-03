"""Interaktif backtest: sembol/strateji/parametre secip aninda sonuc gorme."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core import datastore
from core.backtest import Costs, run as run_backtest
from core.metrics import summarize
from core.strategies import REGISTRY

st.set_page_config(page_title="Backtest", page_icon="🧪", layout="wide")
st.title("🧪 İnteraktif Backtest")

inv = datastore.describe_cache()
if inv.empty:
    st.warning("Önbellekte veri yok. Terminalde `python scripts/fetch_data.py` çalıştırın.")
    st.stop()

with st.sidebar:
    st.header("Ayarlar")
    provider = st.selectbox("Kaynak", sorted(inv["provider"].unique()))
    symbol = st.selectbox("Sembol", sorted(inv.loc[inv["provider"] == provider, "symbol"].unique()))
    tf_options = sorted(inv.loc[(inv["provider"] == provider) & (inv["symbol"] == symbol), "tf"].unique())
    timeframe = st.selectbox("Zaman dilimi", tf_options)
    market = st.radio("Piyasa tipi (yıllandırma için)", ["crypto", "stock"],
                       index=0 if provider == "binance" else 1, horizontal=True)

    strat_name = st.selectbox("Strateji", list(REGISTRY))
    strat_cls = REGISTRY[strat_name]

    st.subheader("Parametreler")
    import inspect
    sig = inspect.signature(strat_cls.__init__)
    params = {}
    for pname, p in sig.parameters.items():
        if pname in ("self",) or p.default is inspect._empty:
            continue
        default = p.default
        if isinstance(default, bool):
            params[pname] = st.checkbox(pname, value=default)
        elif isinstance(default, int):
            params[pname] = st.number_input(pname, value=default, step=1)
        elif isinstance(default, float):
            params[pname] = st.number_input(pname, value=default, step=0.5)
        elif isinstance(default, str):
            help_text = "Virgülle ayrılmış strateji adları (ör. supertrend,ichimoku)" if pname == "components" else None
            params[pname] = st.text_input(pname, value=default, help=help_text)
        else:
            params[pname] = default

    st.subheader("Maliyetler")
    fee_bps = st.number_input("Komisyon (bps, taraf başına)", value=10.0, step=1.0)
    slippage_bps = st.number_input("Slipaj (bps)", value=5.0, step=1.0)
    initial_capital = st.number_input("Başlangıç sermayesi", value=10_000, step=1000)
    allow_short = st.checkbox("Short işlemlere izin ver", value=True)

    st.subheader("Kaldıraç / Risk Boyutlandırma")
    use_leverage = st.checkbox("Risk-bazlı kaldıraçlı boyutlandırma kullan", value=False,
                                help="Kapalıyken her işlemde sermayenin TAMAMI kullanılır (spot/kaldıraçsız). "
                                     "Açıkken her işlemde sermayenin sadece küçük bir yüzdesi riske atılır, "
                                     "kaldıraç sadece pozisyon büyüklüğünü ayarlamak için kullanılır - gerçek "
                                     "kaldıraçlı trading mantığı. Sadece stop-loss döndüren stratejilerde "
                                     "(scalp_mean_reversion, ict_swing) anlamlıdır.")
    risk_per_trade_pct = None
    max_leverage = 1.0
    if use_leverage:
        risk_per_trade_pct = st.slider("İşlem başına risk %", 0.25, 5.0, 1.0, step=0.25,
                                        help="Stop-loss vurulursa sermayenin yüzde kaçının kaybedileceği.")
        max_leverage = st.slider("Maksimum kaldıraç", 1.0, 20.0, 10.0, step=1.0)

df = datastore.load(provider, symbol, timeframe)
if df.empty:
    st.error("Veri bulunamadı.")
    st.stop()

strategy = strat_cls(**params)
costs = Costs(fee_bps=fee_bps, slippage_bps=slippage_bps)
result = run_backtest(df, strategy, costs=costs, initial_capital=initial_capital, allow_short=allow_short,
                       risk_per_trade_pct=risk_per_trade_pct, max_leverage=max_leverage)
metrics = summarize(result, timeframe, market)

if use_leverage and not result.trades.empty and "leverage" in result.trades.columns:
    st.caption(f"Ortalama kullanılan kaldıraç: {result.trades['leverage'].mean():.2f}x · "
               f"En yüksek: {result.trades['leverage'].max():.2f}x · "
               f"(Strateji stop-loss döndürmüyorsa kaldıraç her zaman 1.0x kalır.)")

st.subheader(f"{symbol} · {timeframe} · {strategy}")

if "error" in metrics:
    st.error("Yetersiz veri.")
    st.stop()

cols = st.columns(6)
labels = [
    ("Toplam Getiri %", "toplam_getiri_%"), ("CAGR %", "cagr_%"), ("Sharpe", "sharpe"),
    ("Max Drawdown %", "max_drawdown_%"), ("Kazanma Oranı %", "kazanma_orani_%"), ("İşlem Sayısı", "islem_sayisi"),
]
for col, (label, key) in zip(cols, labels):
    col.metric(label, metrics[key])

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
fig.add_trace(go.Scatter(x=result.equity.index, y=result.equity.values, name="Sermaye",
                          line=dict(color="#2563eb", width=1.5)), row=1, col=1)
dd = result.equity / result.equity.cummax() - 1.0
fig.add_trace(go.Scatter(x=dd.index, y=dd.values * 100, name="Drawdown %", fill="tozeroy",
                          line=dict(color="#dc2626", width=1)), row=2, col=1)
fig.update_layout(height=560, margin=dict(l=10, r=10, t=20, b=10),
                   template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white")
st.plotly_chart(fig, use_container_width=True)

with st.expander(f"İşlem listesi ({len(result.trades)} işlem)"):
    if result.trades.empty:
        st.info("Hiç işlem yapılmadı.")
    else:
        st.dataframe(result.trades.sort_values("exit_time", ascending=False),
                     use_container_width=True, height=400, hide_index=True)

with st.expander("Tüm metrikler"):
    st.json(metrics)
