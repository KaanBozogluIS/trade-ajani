"""research/scan.py ciktisini (reports/scan_sonuclari.csv) filtrelenebilir,
Turkce acikli bir tablo olarak gosterir. Taramayi panelden tetiklemek de
mumkun (uzun surebilir)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Strateji Taraması", page_icon="🔍", layout="wide")
st.title("🔍 Strateji Taraması")
st.caption("Her satır bir sembol × zaman dilimi × strateji × parametre kombinasyonunun test sonucudur.")

with st.expander("📖 Bu sayfadaki terimler ne anlama geliyor? (önce bunu okuyun)", expanded=True):
    st.markdown("""
Her stratejiyi tek bir dönemde test etmek yanıltıcıdır — o dönemin tesadüflerine göre
"ezberlenmiş" olabilir. Bunu yakalamak için elimizdeki geçmiş veriyi **ikiye bölüyoruz**:

- 🟦 **Eğitim Dönemi (IS)** — *In-Sample*. Verinin ilk ~%70'i. Strateji burada "denenir".
- 🟩 **Test Dönemi (OOS)** — *Out-of-Sample*. Verinin son ~%30'u, strateji bu bölümü
  **hiç görmeden** çalıştırılır. Gerçek hayatta karşılaşacağı, önceden bilmediği veriyi
  temsil eder — asıl güvenilir sonuç budur.

**Bir strateji sadece Eğitim Dönemi'nde iyiyse ve Test Dönemi'nde kötüyse, bu strateji
büyük ihtimalle o dönemin tesadüfi hareketlerine "ezberlenmiş"tir — gerçek bir edge değildir.**
Bu yüzden aşağıdaki tabloda asıl bakmanız gereken kolonlar **Test Dönemi** ile başlayanlardır.

| Kolon | Anlamı |
|---|---|
| **Sharpe Oranı** | Getiriyi, alınan riske (oynaklığa) oranlar. 1.0 üzeri iyi, 2.0 üzeri çok iyi kabul edilir. Negatifse strateji zarar ediyor demektir. |
| **Getiri %** | O dönemde sermayenin toplam yüzde kaç büyüdüğü/küçüldüğü. |
| **Max Düşüş %** | Dönem içinde sermayenin tepe noktasından en fazla ne kadar gerilediği (risk göstergesi). -%50 demek, bir ara sermayenin yarısının eridiği anlamına gelir. |
| **İşlem Sayısı** | O dönemde kaç kez pozisyon açılıp kapandığı. Çok azsa (5'in altı) istatistiksel olarak güvenilmez, bu yüzden zaten elendi. |
| **Kazanma Oranı %** | İşlemlerin yüzde kaçının kârla kapandığı. **Düşük olması kötü değildir** — trend takip stratejileri genelde %20-40 kazanır ama kazandığında büyük kazanır. |
| **Tutarlılık Skoru** | Bizim ürettiğimiz özet puan: hem Eğitim hem Test döneminde birlikte iyi olan, aralarında büyük fark olmayan kombinasyonları öne çıkarır. **Sıralama bu skora göre yapılır.** |
""")

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "reports" / "scan_sonuclari.csv"

with st.expander("Yeni tarama çalıştır (birkaç dakika sürebilir)"):
    st.caption("Önce `python scripts/fetch_data.py` ile veri çekilmiş olmalı.")
    if st.button("▶ Taramayı şimdi çalıştır"):
        with st.spinner("Taranıyor..."):
            proc = subprocess.run(
                [sys.executable, str(ROOT / "research" / "scan.py")],
                cwd=str(ROOT), capture_output=True, text=True,
            )
        if proc.returncode == 0:
            st.success("Tarama tamamlandı.")
            st.text(proc.stdout[-3000:])
        else:
            st.error("Tarama başarısız oldu.")
            st.text((proc.stdout + proc.stderr)[-3000:])

if not CSV_PATH.exists():
    st.warning("Henüz tarama sonucu yok. Yukarıdan tarama başlatın ya da terminalde "
               "`python research/scan.py` çalıştırın.")
    st.stop()

df = pd.read_csv(CSV_PATH)
if "OOS_profit_factor" not in df.columns:  # eski taramalardan kalma CSV - kolon henuz yoktu
    # NaN degil sonsuz: NaN >= esik karsilastirmasi False doner ve satirlari
    # sessizce gizler; sonsuz ise "bu deger bilinmiyor, filtreleme" anlaminda
    # her zaman filtreyi gecer.
    df["OOS_profit_factor"] = float("inf")


def _alan(row) -> str:
    if row["provider"] == "binance":
        return "Kripto"
    return "BIST" if str(row["symbol"]).endswith(".IS") else "ABD Hisse"


df["alan"] = df.apply(_alan, axis=1)

st.subheader("🏆 Alanlara Göre En Başarılı Stratejiler")
st.caption("Her piyasa alanında (Kripto / ABD Hisse / BIST), o alandaki tüm sembol ve zaman "
           "dilimi kombinasyonları üzerinden ortalama Tutarlılık Skoru'na göre en başarılı strateji. "
           "**Pozitif Oran**, o stratejinin denemelerinin yüzde kaçında Test Dönemi'nde kâr çıktığını gösterir — "
           "ne kadar çok sembolde/zaman diliminde tekrarlandığı, tek bir coinin şansı olmadığının göstergesi.")

leaderboard = df.groupby(["alan", "strateji"]).agg(
    ort_tutarlilik=("tutarlilik_skoru", "mean"),
    ort_oos_sharpe=("OOS_sharpe", "mean"),
    pozitif_oran=("OOS_sharpe", lambda s: (s > 0).mean() * 100.0),
    kombinasyon=("OOS_sharpe", "size"),
).reset_index()

alanlar = [a for a in ["Kripto", "ABD Hisse", "BIST"] if a in leaderboard["alan"].unique()]
cols = st.columns(len(alanlar)) if alanlar else []
for col, alan in zip(cols, alanlar):
    best = leaderboard[leaderboard["alan"] == alan].sort_values("ort_tutarlilik", ascending=False).iloc[0]
    is_positive = best["ort_tutarlilik"] > 0
    with col:
        st.metric(
            f"{alan} → en iyi strateji",
            best["strateji"],
            help=f"{int(best['kombinasyon'])} kombinasyonun ortalaması. "
                 f"Ortalama Tutarlılık Skoru: {best['ort_tutarlilik']:.2f}, "
                 f"pozitif OOS oranı: %{best['pozitif_oran']:.0f}",
        )
        st.caption(f"Ort. Tutarlılık: {best['ort_tutarlilik']:.2f} · "
                   f"Pozitif Oran: %{best['pozitif_oran']:.0f} · "
                   f"{int(best['kombinasyon'])} kombinasyon")
        if not is_positive:
            st.caption("⚠️ Bu alanda test edilen **hiçbir strateji ortalamada kârlı değil** — "
                       "bu sadece 'diğerlerinden daha az kötü' olan seçenek. Aşağıdaki tabloda "
                       "tek tek satırlara bakıp gerçekten tutarlı, pozitif satırları aramak gerekir.")

with st.expander("Tüm alan × strateji karşılaştırması"):
    pivot = leaderboard.pivot(index="strateji", columns="alan", values="ort_tutarlilik")
    st.dataframe(
        pivot.style.background_gradient(cmap="RdYlGn", axis=None).format("{:.2f}"),
        use_container_width=True,
    )
    st.caption("Hücreler: o alan × strateji kombinasyonunun ortalama Tutarlılık Skoru'dur "
               "(yüksek yeşil = iyi, kırmızı = kötü). Boş hücre, o alanda o strateji için "
               "yeterli veri/işlem olmadığı anlamına gelir.")

st.divider()
st.subheader("Filtrele")
col0, col1, col2, col3, col4 = st.columns(5)
with col0:
    alan_secim = st.multiselect("Alan", alanlar, default=alanlar)
with col1:
    providers = st.multiselect("Piyasa (kaynak)", sorted(df["provider"].unique()), default=list(df["provider"].unique()))
with col2:
    strategies = st.multiselect("Strateji", sorted(df["strateji"].unique()), default=list(df["strateji"].unique()))
with col3:
    tfs = st.multiselect("Zaman Dilimi", sorted(df["tf"].unique()), default=list(df["tf"].unique()))
with col4:
    min_oos_sharpe = st.slider("Min. Test Dönemi Sharpe", -3.0, 5.0, 0.0, step=0.1,
                                help="Sadece test döneminde (OOS) bu değerin üzerinde Sharpe oranına sahip "
                                     "kombinasyonları göster.")

col5, col6 = st.columns(2)
with col5:
    min_winrate = st.slider("Min. Test Dönemi Kazanma %", 0, 100, 0, step=5)
with col6:
    min_pf = st.slider("Min. Kâr Faktörü (Profit Factor)", 0.0, 3.0, 0.0, step=0.1,
                        help="Toplam kazanç / toplam kayıp. 1.0 altı = net zarar demektir — "
                             "kazanma oranı ne kadar yüksek olursa olsun bu değer 1'in altındaysa "
                             "strateji para kaybediyordur.")

filtered = df[
    df["alan"].isin(alan_secim) & df["provider"].isin(providers) & df["strateji"].isin(strategies)
    & df["tf"].isin(tfs) & (df["OOS_sharpe"] >= min_oos_sharpe)
    & (df["OOS_kazanma_%"] >= min_winrate) & (df["OOS_profit_factor"] >= min_pf)
].sort_values("tutarlilik_skoru", ascending=False)

st.metric("Eşleşen kombinasyon", len(filtered))

_TR_COLUMNS = {
    "alan": "Alan",
    "provider": "Piyasa",
    "symbol": "Sembol",
    "tf": "Zaman Dilimi",
    "strateji": "Strateji",
    "IS_sharpe": "Eğitim Dönemi Sharpe",
    "OOS_sharpe": "Test Dönemi Sharpe",
    "IS_getiri_%": "Eğitim Dönemi Getiri %",
    "OOS_getiri_%": "Test Dönemi Getiri %",
    "OOS_maxdd_%": "Test Dönemi Max Düşüş %",
    "OOS_islem": "Test Dönemi İşlem Sayısı",
    "OOS_kazanma_%": "Test Dönemi Kazanma %",
    "OOS_profit_factor": "Kâr Faktörü",
    "tutarlilik_skoru": "Tutarlılık Skoru",
}
display_df = filtered.drop(columns=["params"]).rename(columns=_TR_COLUMNS)

st.dataframe(
    display_df.style.background_gradient(
        subset=["Tutarlılık Skoru", "Test Dönemi Sharpe"], cmap="RdYlGn"
    ),
    use_container_width=True, height=560, hide_index=True,
    column_config={
        "Eğitim Dönemi Sharpe": st.column_config.NumberColumn(
            help="IS (Eğitim Dönemi): verinin ilk ~%70'inde ölçülen Sharpe oranı.", format="%.2f"),
        "Test Dönemi Sharpe": st.column_config.NumberColumn(
            help="OOS (Test Dönemi): verinin, stratejinin hiç görmediği son ~%30'unda ölçülen Sharpe oranı. "
                 "Asıl güvenilir olan bu değerdir.", format="%.2f"),
        "Eğitim Dönemi Getiri %": st.column_config.NumberColumn(format="%.2f%%"),
        "Test Dönemi Getiri %": st.column_config.NumberColumn(format="%.2f%%"),
        "Test Dönemi Max Düşüş %": st.column_config.NumberColumn(
            help="Test döneminde sermayenin tepe noktasından en fazla ne kadar gerilediği.", format="%.2f%%"),
        "Test Dönemi Kazanma %": st.column_config.NumberColumn(format="%.2f%%"),
        "Kâr Faktörü": st.column_config.NumberColumn(
            help="Toplam kazanç / toplam kayıp. 1.0 altı = net zarar. Kazanma oranı yüksek olsa bile "
                 "bu 1'in altındaysa strateji para kaybediyordur.", format="%.2f"),
        "Tutarlılık Skoru": st.column_config.NumberColumn(
            help="Eğitim ve Test dönemlerinde birlikte iyi çalışan kombinasyonları öne çıkaran özet puan.",
            format="%.2f"),
    },
)

st.caption("İzleme listesine eklemek için `config/watchlist.yaml` dosyasına "
           "sembol/zaman dilimi/strateji/parametreleri (aşağıdaki `params` kolonu) girin.")
with st.expander("Seçili satırların ham parametreleri"):
    st.dataframe(filtered[["provider", "symbol", "tf", "strateji", "params"]]
                 .rename(columns=_TR_COLUMNS),
                 use_container_width=True, hide_index=True)
