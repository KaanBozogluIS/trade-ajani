"""Strateji Rehberi - hangi strateji hangi coin'de dogrulandi, sabit
(elle kuratorlu) bir referans sayfasi.

Diger sayfalarin aksine bu sayfa canli hesaplama YAPMAZ - bu oturumda
IS/OOS dogrulamali genis taramalarla (bkz. reports/*_hunt_sonuclari.csv)
bulunan, gercekten calisan kombinasyonlarin ELLE ISLENMIS ozeti. Yeni
arastirma sonuclari geldikce bu dosya guncellenmeli.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Strateji Rehberi", page_icon="📒", layout="wide")
st.title("📒 Strateji Rehberi")
st.caption("Hangi strateji hangi coin'de çalışıyor — bu oturumda eğitim/test (IS/OOS) ayrımıyla "
           "doğrulanmış, gerçek sonuçların özeti. Panelin diğer sayfalarındaki canlı taramaların "
           "aksine bu sayfa elle derlenmiştir; referans/hafıza amaçlıdır.")

st.subheader("🔎 Hızlı bakış: coin → strateji")
quick_lookup = {
    "Coin": ["SEI", "SHIB", "FET", "BNB", "SOL", "ETH", "ZEC", "BTC",
             "TUSDT", "DOTUSDT", "UNIUSDT", "FETUSDT", "LINKUSDT", "PEPEUSDT",
             "SANDUSDT", "BONKUSDT", "ETHUSDT (2)", "BNBUSDT (2)", "ONGUSDT", "DOTUSDT (2)"],
    "Strateji": ["Altcoin Stratejisi", "Altcoin Stratejisi", "Altcoin Stratejisi",
                 "Major Stratejisi", "Major Stratejisi", "Major Stratejisi",
                 "ema_cross", "ict_swing",
                 "Tepe/Dip Stratejisi", "Tepe/Dip Stratejisi", "Tepe/Dip Stratejisi",
                 "Tepe/Dip Stratejisi", "Tepe/Dip Stratejisi", "Tepe/Dip Stratejisi",
                 "Hacim Uyumsuzluğu", "Hacim Uyumsuzluğu", "Hacim Uyumsuzluğu",
                 "Hacim Uyumsuzluğu", "Hacim Uyumsuzluğu", "Hacim Uyumsuzluğu"],
    "Zaman Dilimi": ["1h", "1h", "1h", "4h", "4h", "4h", "1h", "1d",
                      "1h", "1h", "1h", "1h", "1h", "1h",
                      "1h", "1h", "1h", "1h", "1h", "1h"],
    "Durum": ["✅ Güçlü", "✅ Güçlü", "🟡 Orta", "✅ Güçlü", "🟡 Orta (büyük düşüş riski)",
              "⚠️ Kaldıraçta kırılgan", "✅ Çok Güçlü (dev örneklem)", "🟡 Mütevazı ama tutarlı",
              "📡 Canlı", "📡 Canlı", "📡 Canlı",
              "📡 Canlı", "📡 Canlı", "📡 Canlı",
              "📡 Canlı", "📡 Canlı", "📡 Canlı",
              "📡 Canlı", "📡 Canlı", "📡 Canlı"],
}
import pandas as pd
st.dataframe(pd.DataFrame(quick_lookup), use_container_width=True, hide_index=True)

st.divider()

# --------------------------------------------------------------------
st.subheader("1️⃣ Altcoin Stratejisi — orta/küçük ölçekli coinler")
st.markdown("""
**Mantık:** Kendi tasarladığımız, isimli olmayan bir strateji — çoklu-dokunuşlu destek/direnç
(en az 2 temas gerekir) + kararlı kırılım (kapanış bazlı, fitil değil) + kırılan seviyeye geri
çekilme + güçlü kapanışlı "toparlanma mumu" ile giriş. `core/strategies/breakout_retest_recovery.py`
""")
altcoin_data = {
    "Coin": ["SEIUSDT", "SHIBUSDT", "FETUSDT"],
    "Zaman Dilimi": ["1h", "1h", "1h"],
    "Kazanma Oranı": ["%56.1", "%50.0", "%47.9"],
    "Kâr Faktörü": [1.71, 2.22, 1.33],
    "Sharpe": [1.00, 0.82, 0.41],
    "Max Düşüş": ["-%16.5", "-%9.0", "-%32.7"],
    "İşlem Sayısı": [57, 28, 96],
    "Ort. Tutma": ["~5.4 saat", "~11 saat", "~16.5 saat"],
}
st.dataframe(pd.DataFrame(altcoin_data), use_container_width=True, hide_index=True)
st.caption("Ayrıca 108 sembollük genel taramada BICO, WLD, ZKC, BMT, PENGU, ZEN'de de aynı örüntü "
           "görüldü (daha az derinlemesine doğrulandı — panelden kendin test edebilirsin).")
st.warning("**BTC/ETH/SOL/ZEC/BNB'de ÇALIŞMIYOR** — BTC'de denenen 54 parametrenin hiçbiri "
           "kâr faktörünü 1'in üzerine çıkaramadı (en iyisi 0.81). Bu strateji bilerek "
           "sadece küçük/orta ölçekli, teknik seviyelere saygılı coinler için kullanılmalı.")

st.divider()

# --------------------------------------------------------------------
st.subheader("2️⃣ Major Stratejisi — büyük/likit coinler")
st.markdown("""
**Mantık:** Kendi tasarladığımız başka bir strateji — N-bar kırılım + ADX (trend teyidi) +
hacim oranı (katılım teyidi, kendi faktör araştırmamızdan) + uzun EMA filtresi ile giriş;
sabit kâr hedefi YOK — "chandelier" (candan) iz süren stop ile trend sürdükçe pozisyon taşınır.
`core/strategies/major_trend_rider.py`
""")
major_data = {
    "Coin": ["BNBUSDT", "SOLUSDT", "ETHUSDT"],
    "Zaman Dilimi": ["4h", "4h", "4h"],
    "Tam Tarih Getiri": ["+%801", "+%411", "+%142"],
    "Sharpe": [1.12, 0.76, 0.59],
    "Kazanma Oranı": ["%41.5", "%46.7", "%41.2"],
    "Kâr Faktörü": [1.43, 1.29, 1.30],
    "Max Düşüş": ["-%46.6", "-%80.8 ⚠️", "-%42.0"],
    "Kaldıraçlı (risk %2, 10x)": ["+%1333", "+%357", "-%6 ile +%14 arası"],
}
st.dataframe(pd.DataFrame(major_data), use_container_width=True, hide_index=True)
st.warning("**ETHUSDT dikkat:** kapanış-bazlı testte iyi görünüyor ama gerçek bir stop emrinin "
           "bar-içi (anlık) dokunuşuyla test edilince kırılganlaşıyor — kaldıraçla kullanmadan "
           "önce panelden kendi risk ayarlarınla mutlaka doğrula.")
st.warning("**BTC/ZEC'te ÇALIŞMIYOR** — bu mekanik (chandelier trend rider) bu ikisinde IS/OOS "
           "tutarlılığı sağlayamadı, onlar için ayrı stratejiler bulundu (aşağıya bak).")

st.divider()

# --------------------------------------------------------------------
st.subheader("3️⃣ ZEC — klasik ema_cross")
st.markdown("""
Karmaşık hiçbir şeye gerek kalmadı — **düz EMA kesişimi** (fast=20, slow=50, trend_filter=200,
hepsi varsayılan parametreler) ZEC'te bu oturumun en güçlü, en büyük örneklemli sonucunu verdi.
""")
zec_data = {
    "Metrik": ["Eğitim Dönemi İşlem", "Test Dönemi İşlem", "Eğitim Kâr Faktörü", "Test Kâr Faktörü",
               "Eğitim Sharpe", "Test Sharpe", "Test Dönemi Getiri"],
    "Değer": [203, 77, 1.68, 2.50, 1.34, 2.33, "+%3446"],
}
st.dataframe(pd.DataFrame(zec_data), use_container_width=True, hide_index=True)
st.caption("280 işlemlik dev örneklem, eğitim VE test döneminde ikisi de net kârlı — bu oturumun "
           "en güvenilir tek sonucu. Zaman dilimi: 1h.")

st.divider()

# --------------------------------------------------------------------
st.subheader("4️⃣ BTC — ict_swing")
st.markdown("""
Yapı (BOS) + FVG/Order Block geri çekilme girişi, ATR stop + R-katı hedef.
`core/strategies/ict_swing.py`. Parametreler: `tp_r_mult=2.0, sl_atr_buffer=0.3`.
""")
btc_data = {
    "Metrik": ["Eğitim Dönemi İşlem", "Test Dönemi İşlem", "Eğitim Kâr Faktörü", "Test Kâr Faktörü",
               "Eğitim Sharpe", "Test Sharpe", "Test Dönemi Getiri", "Test Dönemi Max Düşüş"],
    "Değer": [64, 31, 1.19, 1.38, 0.60, 0.73, "+%38.5", "-%36.5"],
}
st.dataframe(pd.DataFrame(btc_data), use_container_width=True, hide_index=True)
st.caption("Zaman dilimi: 1d. Mütevazı ama bu oturumda BTC için bulunan İLK gerçekten IS/OOS "
           "tutarlı sonuç — BTC bu evrende en zor piyasa oldu, hiçbir yöntem çok güçlü bir edge "
           "vermedi. Aynı strateji SOLUSDT 4h'de de çalışıyor (563 işlem, tam tarih +%260).")

st.divider()

# --------------------------------------------------------------------
st.subheader("5️⃣ Tepe/Dip Stratejisi — rejime uyarlanan dönüş/düzeltme")
st.markdown("""
**Mantık:** Kendi tasarladığımız, REJIME göre iki farklı mantık çalıştıran bir strateji —
ADX **trendli** ise (fiyat EMA200'ün doğru tarafında) kısa bir düzeltmede (RSI sığ dalış,
MACD histogram dönüşü, hacim teyidi) trend YÖNÜNDE giriş yapar ("artan coin'de düzeltmede alım");
ADX **yatay** ise çok-dokunuşlu bir destek/direnç bölgesinden derin bir RSI aşırılığıyla
gelen dönüşü yakalar (mean-reversion). `core/strategies/reversal_pullback.py`
""")
tepe_dip_data = {
    "Coin": ["TUSDT", "DOTUSDT", "UNIUSDT", "FETUSDT", "LINKUSDT", "PEPEUSDT"],
    "Kaldıraçlı Getiri (8x, %1.5 risk)": ["+%38.9", "+%37.9", "+%32.4", "+%30.1", "+%30.0", "+%18.9"],
    "Sharpe": [1.08, 0.95, 1.09, 1.05, 0.81, 0.98],
    "Max Düşüş": ["-%9.7", "-%5.3", "-%7.4", "-%5.2", "-%9.9", "-%5.8"],
    "İşlem Sayısı": [54, 47, 46, 34, 51, 22],
    "Kazanma Oranı": ["%59.3", "%55.3", "%65.2", "%64.7", "%51.0", "%63.6"],
    "Kâr Faktörü": [2.01, 1.92, 2.12, 2.41, 1.67, 2.37],
}
st.dataframe(pd.DataFrame(tepe_dip_data), use_container_width=True, hide_index=True)
st.caption("108 sembol × 3 zaman dilimi IS/OOS taramasında 20 farklı 1sa sembolde bağımsız "
           "doğrulandı (ETHUSDT, DOGEUSDT, ARUSDT, SANDUSDT dahil — panelden kendin test "
           "edebilirsin); yukarıdaki 6'sı 8x kaldıraçlı tam-tarih testinde en sağlam çıkanlar.")
st.warning("**TRXUSDT/SCUSDT/ONGUSDT'de kaldıraçlı halde net ZARARLI** — kaldıraçsız IS/OOS "
           "eşiğini az farkla geçmişlerdi ama gerçekçi pozisyon boyutlandırmasında tutmadı. "
           "Bu üçü bilerek watchlist'e eklenmedi.")
st.info("📡 **CANLI** (`notify: true`, 2026-09-08'de kullanıcı talebiyle etkinleştirildi) — "
        "diğer stratejiler gibi sinyal değiştiğinde Telegram'a bildirim gönderiyor.")

st.divider()

# --------------------------------------------------------------------
st.subheader("6️⃣ Hacim-Fiyat Uyumsuzluğu (Absorbsiyon) Stratejisi")
st.markdown("""
**Mantık:** Wyckoff'un "efor vs sonuç" fikrinden esinlenen, sıfırdan tasarlanmış bir strateji —
bir mumda **hacim (efor) anormal yüksekken fiyat aralığı (sonuç) ATR'a göre küçükse**, bu bir
uyumsuzluktur: büyük bir taraf agresif girmiş ama fiyatı hareket ettirememiş — o seviyede
**karşı tarafın emri "emdiğinin"** (absorbe ettiğinin) izidir. Tek başına yeterli değil; bu yüzden
çok-dokunuşlu bir destek/direnç bölgesinde gerçekleşmesi VE ardından fiyatın o "emilim mumunun"
ucunu kırarak yön teyidi vermesi şart koşuluyor. `core/strategies/volume_absorption.py`
""")
absorption_data = {
    "Coin": ["SANDUSDT", "BONKUSDT", "ETHUSDT", "BNBUSDT", "ONGUSDT", "DOTUSDT"],
    "Kaldıraçlı Getiri (8x, %1.5 risk)": ["+%28.8", "+%29.1", "+%23.1", "+%20.3", "+%26.8", "+%24.8"],
    "Sharpe": [1.09, 1.07, 0.72, 0.74, 0.59, 0.47],
    "Max Düşüş": ["-%4.5", "-%11.5", "-%5.4", "-%7.4", "-%12.3", "-%15.6"],
    "İşlem Sayısı": [22, 44, 40, 22, 62, 95],
    "Kazanma Oranı": ["%59.1", "%43.2", "%52.5", "%50.0", "%48.4", "%39.0"],
    "Kâr Faktörü": [2.75, 1.66, 1.74, 2.03, 1.43, 1.24],
}
st.dataframe(pd.DataFrame(absorption_data), use_container_width=True, hide_index=True)
st.caption("108 sembol × 3 zaman dilimi IS/OOS taramasında 33 farklı kombinasyonda (24 benzersiz "
           "1sa sembolde) doğrulandı; yukarıdaki 6'sı 8x kaldıraçlı tam-tarih testinde en sağlam "
           "çıkanlar (24 sembolün 22'si kaldıraçlı halde net karlı).")
st.warning("**BTCUSDT/SCUSDT'de kaldıraçlı halde net ZARARLI/başabaş** (PF 0.88 / 0.98) — "
           "kaldıraçsız IS/OOS eşiğini az farkla geçmişlerdi ama gerçekçi boyutlandırmada tutmadı, "
           "bilerek watchlist'e eklenmedi.")
st.info("📡 **CANLI** (`notify: true`, 2026-09-08'de kullanıcı talebiyle etkinleştirildi) — "
        "diğer stratejiler gibi sinyal değiştiğinde Telegram'a bildirim gönderiyor.")

st.divider()
st.info("📌 **Watchlist'te bu kombinasyonların tümü aktif** — İzleme & Sinyaller sayfasından "
        "canlı sinyalleri takip edebilirsin. Yeni bulgular geldikçe bu sayfa güncellenecek.")
