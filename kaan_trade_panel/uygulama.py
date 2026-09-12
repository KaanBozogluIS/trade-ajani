r"""
KAAN-TRADE PANELI
=================

Masaustunde calisan kripto analiz paneli.

  * Binance'teki BUTUN USDT ciftleri (~650 coin) tek tabloda
  * Arama cubugu ile coin secimi
  * Mum grafigi, RSI, Bollinger, hacim, karsilastirma, korelasyon
  * ANLIK veri: WebSocket ile saniyede bir guncellenen fiyatlar

Baslatmak icin: masaustundeki "kaan-trade Paneli" kisayoluna cift tiklayin.

NE YAPAR / NE YAPMAZ
    YAPAR  : Piyasanin su anki durumunu olcer, gosterir, karsilastirir.
    YAPMAZ : Fiyatin nereye gidecegini soylemez, al/sat tavsiyesi vermez.
             Test ettigimiz 16 standart gostergenin hicbiri gelecegi
             bilemedi -- ayrintisi README.md icinde.
"""

import streamlit as st

st.set_page_config(page_title="kaan-trade", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

import html
import json
import subprocess
import threading
import time
from datetime import datetime, timezone

import pandas as pd

import analiz_botu as ab
import canli_veri as cv
import grafikler as gr
import haberler as hb
import sanal_trader as strd
import veri_kaynaklari as vk
import trade_ajani_stratejileri as taj
from dogrulama import simule_et
from stratejiler import atr, rsi

# ============================================================
#  GORUNUM  (CSS)
# ============================================================
#
# TradingView ve benzeri islem platformlarindan esinlenildi: koyu,
# yuksek kontrastli zemin; mavi vurgu rengi; sikisik ama nefes alan
# bosluklar; duz (golgesiz) kartlar; renk KOD anlamli yerlerde
# kullanilir (yesil/kirmizi = yon), sekmeler pill/segmented-control
# gorunumunde.
#
# NOT (onemli kisit): st.dataframe canvas uzerine ciziyor (glide-data-grid
# kutuphanesi), yani buyuk coin tablosunun hucrelerini normal CSS ile
# boyayamiyoruz -- o yuzden tablodaki renkli % rozetleri pandas Styler
# ile (asagida tum_coinler_tablosu icinde) yapiliyor, CSS ile degil.

st.markdown("""
<style>
  /* NOT: Font/ikon yuklemeyi <link> etiketiyle degil @import ile
     yapiyoruz -- Streamlit'in markdown->HTML donusturucusu, bir
     st.markdown cagrisinda <style> etiketinden ONCE <link> etiketleri
     gelince bunu duzgun bir HTML blogu olarak tanimayip HAM METIN
     olarak sayfaya basiyordu (butun CSS kodu ekranda yazi olarak
     goruluyordu). @import, <style> etiketinin ICINDE oldugu icin bu
     sorunu yasamiyor -- gecerli CSS, HTML ayristirma belirsizligi yok.
  */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
  @import url('https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3/dist/tabler-icons.min.css');

  :root {
      --kt-bg: #131722;
      --kt-panel: #1a1e2a;
      --kt-panel-2: #1e222d;
      --kt-border: rgba(255,255,255,0.08);
      --kt-border-strong: rgba(255,255,255,0.16);
      --kt-text: #d1d4dc;
      --kt-text-dim: #868993;
      --kt-blue: #2962ff;
      --kt-blue-dim: rgba(41,98,255,0.14);
      --kt-green: #26a69a;
      --kt-green-bg: rgba(38,166,154,0.12);
      --kt-red: #ef5350;
      --kt-red-bg: rgba(239,83,80,0.12);
      --kt-amber: #ffb74d;
      --kt-radius: 10px;
      --kt-font: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
      --kt-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Code', monospace;
  }

  html, body, [class*="css"] { font-family: var(--kt-font); }
  .stApp { background: var(--kt-bg); }
  .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 100%; }
  #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }

  ::-webkit-scrollbar { width: 9px; height: 9px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.14); border-radius: 5px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.24); }

  h1, h2, h3 { font-family: var(--kt-font); letter-spacing: -0.01em; }
  h1 { font-weight: 600 !important; font-size: 1.5rem !important; }

  /* ============ UST NAVBAR ============ */
  .kt-brand { display: flex; align-items: center; gap: 9px; font-weight: 700;
              font-size: 1.05rem; color: var(--kt-text); white-space: nowrap; }
  .kt-brand .ti { font-size: 1.3rem; color: var(--kt-blue); }
  .kt-brand-sub { font-weight: 400; font-size: 0.72rem; color: var(--kt-text-dim);
                  border-left: 1px solid var(--kt-border); padding-left: 9px; margin-left: 2px; }

  /* Sayfa sekmelerini gosteren st.radio'yu pill/segmented-control gibi
     giydiriyoruz. aria-label, st.radio'ya verdigimiz "Sayfa" etiketinden
     geliyor -- label_visibility="collapsed" olsa bile erisilebilirlik
     icin DOM'da kalir, biz de secici olarak onu kullaniyoruz. */
  div[role="radiogroup"][aria-label="Sayfa"] {
      gap: 2px; background: rgba(255,255,255,0.04); padding: 3px;
      border-radius: 9px; border: 1px solid var(--kt-border);
      width: fit-content;
  }
  div[role="radiogroup"][aria-label="Sayfa"] label[data-baseweb="radio"] {
      margin: 0 !important; padding: 6px 16px !important; border-radius: 7px;
      transition: background 0.14s ease; cursor: pointer;
  }
  div[role="radiogroup"][aria-label="Sayfa"] label[data-baseweb="radio"]:hover {
      background: rgba(255,255,255,0.05);
  }
  div[role="radiogroup"][aria-label="Sayfa"] label[data-baseweb="radio"] > div:first-child {
      display: none !important;
  }
  div[role="radiogroup"][aria-label="Sayfa"] label[data-baseweb="radio"] p {
      font-size: 0.86rem !important; font-weight: 500; color: var(--kt-text-dim);
      white-space: nowrap;
  }
  div[role="radiogroup"][aria-label="Sayfa"] label[data-baseweb="radio"]:has(input:checked) {
      background: var(--kt-blue-dim);
  }
  div[role="radiogroup"][aria-label="Sayfa"] label[data-baseweb="radio"]:has(input:checked) p {
      color: #6d9bff !important;
  }

  .kt-live-badge { display: flex; align-items: center; gap: 6px; font-size: 0.78rem;
                   color: var(--kt-text-dim); white-space: nowrap; }

  /* ============ TICKER TAPE ============ */
  .kt-ticker-wrap {
      display: flex; gap: 8px; overflow-x: auto; padding: 9px 2px 13px 2px;
      margin-bottom: 4px; border-bottom: 1px solid var(--kt-border);
      scrollbar-width: thin;
  }
  .kt-ticker-item {
      display: flex; align-items: baseline; gap: 7px; flex-shrink: 0;
      padding: 7px 13px; border-radius: 8px; background: var(--kt-panel-2);
      border: 1px solid var(--kt-border); cursor: default;
      transition: border-color 0.14s ease;
  }
  .kt-ticker-item:hover { border-color: var(--kt-border-strong); }
  .kt-ticker-sym { font-weight: 600; font-size: 0.82rem; color: var(--kt-text); }
  .kt-ticker-fiyat { font-family: var(--kt-mono); font-size: 0.82rem; color: var(--kt-text); }
  .kt-ticker-yuzde { font-family: var(--kt-mono); font-size: 0.78rem; font-weight: 600; }

  /* ============ GENEL KART / OLCU GORUNUMU ============ */
  div[data-testid="stMetric"] {
      background: var(--kt-panel-2);
      border: 1px solid var(--kt-border);
      border-radius: var(--kt-radius);
      padding: 11px 14px 9px 14px;
      transition: border-color 0.14s ease;
  }
  div[data-testid="stMetric"]:hover { border-color: var(--kt-border-strong); }
  div[data-testid="stMetricLabel"] p {
      font-size: 0.70rem !important;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--kt-text-dim) !important;
      font-weight: 600;
  }
  div[data-testid="stMetricValue"] {
      font-size: 1.28rem !important;
      font-family: var(--kt-mono);
      font-variant-numeric: tabular-nums;
      color: var(--kt-text);
  }
  div[data-testid="stMetricDelta"] { font-size: 0.80rem !important; font-family: var(--kt-mono); }

  /* Canli gosterge noktasi */
  .canli-nokta {
      display: inline-block; width: 7px; height: 7px; border-radius: 50%;
      background: var(--kt-green); margin-right: 6px; vertical-align: middle;
      animation: nabiz 1.6s ease-in-out infinite;
      box-shadow: 0 0 6px 0 rgba(38,166,154,0.6);
  }
  .canli-nokta.kopuk { background: var(--kt-red); animation: none;
                        box-shadow: 0 0 6px 0 rgba(239,83,80,0.6); }
  @keyframes nabiz { 0%,100% { opacity: 1; } 50% { opacity: 0.28; } }
  .canli-yazi { font-size: 0.80rem; color: var(--kt-text-dim); vertical-align: middle; }

  /* Buyuk fiyat gosterimi (Coin analizi basligi) */
  .dev-fiyat {
      font-size: 2.6rem; font-weight: 600; line-height: 1.1;
      font-family: var(--kt-mono); font-variant-numeric: tabular-nums;
      color: var(--kt-text);
  }
  .dev-degisim {
      font-size: 1.05rem; font-weight: 600; margin-left: 8px;
      font-family: var(--kt-mono); padding: 3px 9px; border-radius: 6px;
      vertical-align: middle;
  }
  .yukari { color: var(--kt-green); }
  .asagi  { color: var(--kt-red); }
  .sabit  { color: var(--kt-text-dim); }
  .dev-degisim.yukari { background: var(--kt-green-bg); }
  .dev-degisim.asagi  { background: var(--kt-red-bg); }

  .bolum-basligi {
      display: flex; align-items: center; gap: 7px;
      font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.07em;
      color: var(--kt-text-dim); margin: 1.6rem 0 0.55rem 0; font-weight: 600;
  }
  .bolum-basligi::after {
      content: ""; flex: 1; height: 1px; background: var(--kt-border);
  }

  /* ============ KENAR CUBUGU ============ */
  section[data-testid="stSidebar"] {
      background: var(--kt-panel); border-right: 1px solid var(--kt-border);
  }
  section[data-testid="stSidebar"] .stCaption p { color: var(--kt-text-dim); }
  .kt-side-label {
      display: flex; align-items: center; gap: 6px;
      font-size: 0.78rem; font-weight: 600; color: var(--kt-text-dim);
      margin-bottom: 2px;
  }
  .kt-side-label .ti { font-size: 0.95rem; }

  /* ============ GIRDI BILESENLERI ============ */
  div[data-testid="stDataFrame"] {
      border-radius: var(--kt-radius); border: 1px solid var(--kt-border); overflow: hidden;
  }
  .stButton > button, .stDownloadButton > button {
      border-radius: 7px; border: 1px solid var(--kt-border);
      background: var(--kt-panel-2); font-weight: 500;
      transition: border-color 0.14s ease, background 0.14s ease;
  }
  .stButton > button:hover { border-color: var(--kt-blue); color: #6d9bff; }
  .stButton > button[kind="primary"] { background: var(--kt-blue); border-color: var(--kt-blue); }

  div[data-baseweb="select"] > div, div[data-baseweb="input"] {
      border-radius: 7px !important; background: var(--kt-panel-2) !important;
      border-color: var(--kt-border) !important;
  }
  div[data-baseweb="select"] > div:hover, div[data-baseweb="input"]:hover {
      border-color: var(--kt-border-strong) !important;
  }

  /* Cok secimli (multiselect) etiketler */
  span[data-baseweb="tag"] {
      background: var(--kt-blue-dim) !important; border-radius: 5px !important;
  }

  div[data-testid="stExpander"] {
      border: 1px solid var(--kt-border) !important; border-radius: var(--kt-radius) !important;
      background: var(--kt-panel-2);
  }

  /* ============ HABER KARTI ============ */
  .haber-kart {
      display: block; padding: 13px 15px; margin-bottom: 9px;
      border: 1px solid var(--kt-border);
      border-radius: var(--kt-radius); background: var(--kt-panel-2);
      text-decoration: none !important; color: inherit;
      transition: background 0.15s ease, border-color 0.15s ease, transform 0.1s ease;
  }
  .haber-kart:hover {
      background: #222735; border-color: var(--kt-border-strong);
  }
  .haber-ust { display: flex; align-items: center; gap: 8px; margin-bottom: 5px;
               font-size: 0.72rem; color: var(--kt-text-dim); }
  .haber-kaynak {
      font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;
      padding: 2px 8px; border-radius: 5px;
      background: var(--kt-blue-dim); color: #6d9bff;
  }
  .haber-kaynak.genel { background: rgba(255,183,77,0.14); color: var(--kt-amber); }
  .haber-baslik { font-size: 0.95rem; font-weight: 600; line-height: 1.4;
                  color: var(--kt-text); margin-bottom: 4px; }
  .haber-ozet { font-size: 0.82rem; color: var(--kt-text-dim); line-height: 1.5; }
  .haber-coin { display: inline-block; font-size: 0.68rem; font-weight: 600;
                padding: 2px 7px; border-radius: 5px; margin-right: 4px;
                background: var(--kt-green-bg); color: var(--kt-green); }

  /* ============ GOZLEM KARTI (Analiz Botu) ============ */
  /* Renk SADECE "bu gozlem yukari mi asagi mi okunur" bilgisini tasir --
     "iyi/kotu" ya da "al/sat" anlami YOK, bkz. analiz_botu.py basindaki not. */
  .gozlem-kart { display: block; padding: 12px 15px; margin-bottom: 9px;
      border: 1px solid var(--kt-border); border-left: 3px solid var(--kt-border-strong);
      border-radius: var(--kt-radius); background: var(--kt-panel-2); }
  .gozlem-kart.yukari { border-left-color: var(--kt-green); }
  .gozlem-kart.asagi { border-left-color: var(--kt-red); }
  .gozlem-kart.notr { border-left-color: var(--kt-text-dim); }
  .gozlem-ust { display: flex; align-items: center; gap: 8px; margin-bottom: 5px;
                font-size: 0.72rem; color: var(--kt-text-dim); }
  .gozlem-kategori { font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;
      padding: 2px 8px; border-radius: 5px; background: var(--kt-blue-dim); color: #6d9bff; }
  .gozlem-yon { font-weight: 600; }
  .gozlem-kart.yukari .gozlem-yon { color: var(--kt-green); }
  .gozlem-kart.asagi .gozlem-yon { color: var(--kt-red); }
  .gozlem-kart.notr .gozlem-yon { color: var(--kt-text-dim); }
  .gozlem-baslik { font-size: 0.95rem; font-weight: 600; line-height: 1.4;
                   color: var(--kt-text); margin-bottom: 4px; }
  .gozlem-aciklama { font-size: 0.82rem; color: var(--kt-text-dim); line-height: 1.5; }

  /* ============ TARAMA KARTI (Piyasa Taramasi) ============ */
  /* Renk burada da yon ("yukselecek/dusecek") tasimaz -- sadece durumun
     ne kadar dikkat cekici oldugunu (guclu/sikisma) siniflandirir. */
  .tarama-kart { display: block; padding: 9px 13px; margin-bottom: 7px;
      border: 1px solid var(--kt-border); border-left: 3px solid var(--kt-border-strong);
      border-radius: var(--kt-radius); background: var(--kt-panel-2); }
  .tarama-kart.guclu { border-left-color: var(--kt-amber); }
  .tarama-kart.teyitli { border-left-color: var(--kt-green); }
  .tarama-kart-ust { display: flex; align-items: center; gap: 7px; margin-bottom: 3px; }
  .tarama-kart-kod { font-weight: 700; font-family: var(--kt-mono); font-size: 0.88rem;
                      color: var(--kt-text); }
  .tarama-kart-etiket { font-size: 0.68rem; font-weight: 600; padding: 2px 7px;
      border-radius: 5px; background: rgba(255,255,255,0.06); color: var(--kt-text-dim); }
  .tarama-kart-etiket.guclu { background: rgba(255,183,77,0.14); color: var(--kt-amber); }
  .tarama-kart-etiket.teyitli { background: var(--kt-green-bg); color: var(--kt-green); }
  .tarama-kart-detay { font-size: 0.76rem; color: var(--kt-text-dim); line-height: 1.4; }

  /* Plotly grafiklerinde daha yumusak gecis */
  .js-plotly-plot .plotly { transition: opacity 0.15s ease; }
</style>
""", unsafe_allow_html=True)


# ============================================================
#  CANLI VERI DEPOSU
# ============================================================

@st.cache_resource(show_spinner=False)
def canli():
    """
    Anlik veri deposu. cache_resource sayesinde uygulama boyunca
    TEK BIR tane olusturulur ve butun sayfalar onu paylasir.
    """
    return cv.piyasa()


# ============================================================
#  ONBELLEKLI (yavas degisen) VERILER
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def c_mumlar(sembol, dilim, adet):
    return vk.mum_verisi(sembol, dilim, adet)


@st.cache_data(ttl=120, show_spinner=False)
def c_genel():
    return vk.piyasa_geneli()


@st.cache_data(ttl=600, show_spinner=False)
def c_korku():
    return vk.korku_acgozluluk(60)


@st.cache_data(ttl=300, show_spinner=False)
def c_gecko_ilk250():
    """
    CoinGecko'dan piyasa degerine gore ilk 250 coin. Tek cagri.
    Kod (BTC, ETH...) -> bilgi seklinde sozluk dondurur.
    """
    try:
        y = vk._oturum.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc",
                    "per_page": 250, "page": 1,
                    "price_change_percentage": "1h,24h,7d,30d"},
            timeout=vk.ZAMAN_ASIMI).json()
        return {c["symbol"].upper(): c for c in y}
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def c_fonlama(vadeli_sembol):
    return vk.fonlama_orani(vadeli_sembol)


@st.cache_data(ttl=60, show_spinner=False)
def c_acik_pozisyon(vadeli_sembol, fiyat):
    return vk.acik_pozisyon(vadeli_sembol, fiyat)


@st.cache_data(ttl=20, show_spinner=False)
def c_defter(sembol):
    # Emir defteri saniyeler icinde degisir; digerlerinden (60-300 sn)
    # cok daha kisa bir onbellek suresi kullaniyoruz.
    return vk.emir_defteri_ozeti(sembol)


@st.cache_data(ttl=300, show_spinner=False)
def c_oi_gecmisi(vadeli_sembol):
    return vk.acik_pozisyon_gecmisi(vadeli_sembol, 10)


@st.cache_data(ttl=300, show_spinner=False)
def c_haberler():
    """
    9 kaynaktan haberleri toplar. 5 dakika onbellekte tutulur --
    haberler saniyede degismez, boylece her sayfa yenilemesinde
    9 siteye birden istek atilmaz.
    """
    return hb.tumunu_getir()


# ============================================================
#  BICIMLENDIRME
# ============================================================

def al(sozluk, anahtar):
    """Sozlukten guvenli okuma: yoksa None doner, cokmez."""
    return sozluk.get(anahtar) if sozluk else None


def esc(metin):
    """
    Disaridan gelen metni (haber basligi gibi) HTML'e gomerken kacirir.

    "$" isaretini de kaciriyoruz: Streamlit'in markdown isleyicisi tek
    "$" isaretlerini LaTeX matematik formulu baslangici saniyor ve bir
    sonraki "$" isaretine kadar her seyi (HTML etiketlerimiz dahil) o
    formulun parcasi sayip oldugu gibi metin olarak basiyor. Finans
    haberleri "$1 milyar" gibi ifadelerle dolu oldugu icin bu gercekten
    yasanan bir hataydi -- &#36; sayisal karsiligi tarayicida yine "$"
    olarak gorunur ama markdown ayristiricisini tetiklemez.
    """
    kacirilmis = html.escape(str(metin), quote=True)
    return kacirilmis.replace("$", "&#36;")


def buyuk_sayi(x, para=True):
    """
    Buyuk sayilari okunur hale getirir.

    Kisaltma yerine kelimeyi aciyoruz: "1.29 T" yazsak T'nin trilyon mu
    baska bir sey mi oldugu belirsiz kalir. Turkce'de "B" ise bin ile
    milyar arasinda karisir. Bu yuzden kelimeyi yaziyoruz.
    """
    if x is None:
        return "—"
    on = "$" if para else ""
    a = abs(x)
    if a >= 1e12:
        return f"{on}{x / 1e12:.2f} trilyon"
    if a >= 1e9:
        return f"{on}{x / 1e9:.2f} milyar"
    if a >= 1e6:
        return f"{on}{x / 1e6:.1f} milyon"
    if a >= 1e3:
        return f"{on}{x / 1e3:.1f} bin"
    return f"{on}{x:,.2f}" if a < 100 else f"{on}{x:,.0f}"


def fiyat_yaz(x):
    """
    Coin fiyatlari cok farkli buyuklukte; basamak sayisini uyarliyoruz.

    ONEMLI: yuksek fiyatli coinlerde (BTC gibi) bile kurus/cent kismi
    ATILMAZ -- "$63,822" degil "$63,822.47" yazilir. Eskiden 1000$
    uzerindeki fiyatlar tam sayiya yuvarlaniyordu, bu "fiyat eksik
    gosteriliyor" hissi veriyordu.
    """
    if x is None:
        return "—"
    a = abs(x)
    if a >= 1:
        return f"${x:,.2f}"
    if a >= 0.01:
        return f"${x:,.4f}"
    return f"${x:,.8f}".rstrip("0")


def yuzde(x, basamak=2):
    return "—" if x is None else f"{x:+.{basamak}f}%"


def yas_yaz(saniye):
    if saniye is None:
        return "—"
    if saniye < 5:
        return "şimdi"
    if saniye < 60:
        return f"{saniye:.0f} sn önce"
    if saniye < 3600:
        return f"{saniye/60:.0f} dk önce"
    return f"{saniye/3600:.1f} sa önce"


def yon_sinifi(x):
    if x is None:
        return "sabit"
    return "yukari" if x > 0 else ("asagi" if x < 0 else "sabit")


def canli_gosterge(depo):
    """Sag ustteki 'canli' isareti ve gecikme bilgisi."""
    o = depo.ozet()
    bagli = o.get("baglandi")
    gecikme = o.get("gecikme")
    sinif = "canli-nokta" if bagli else "canli-nokta kopuk"
    if bagli:
        yazi = f"canlı · {o.get('toplam_coin', 0)} coin"
        if gecikme is not None:
            yazi += f" · gecikme {gecikme:.0f} sn"
    else:
        yazi = "bağlantı kuruluyor…"
        if o.get("hata"):
            yazi = "bağlantı koptu, yeniden deneniyor…"
    return f'<span class="{sinif}"></span><span class="canli-yazi">{yazi}</span>'


def ticker_serit(depo, adet=16):
    """
    TradingView'deki "ticker tape" seridine benzer: en cok islem goren
    coinlerin sembol + fiyat + yuzde degisimini yatay bir seritte
    gosterir. Her sayfanin ustunde, canli parcanin icinde cizilir.

    NEDEN OTOMATIK KAYMIYOR (marquee) DEGIL DE ELLE KAYDIRILABILIR?
    Bu serit saniyede bir yeniden ciziliyor (yeni HTML). Bir CSS
    "marquee" animasyonu her yeniden cizimde basa donerdi ve surekli
    "sicrayan" bir gorunum olustururdu. Elle kaydirilan sakin bir serit,
    canli veriyle daha uyumlu.
    """
    df = depo.tablo(1e6)  # sadece anlamli hacimli coinler
    if df is None or df.empty:
        return
    df = df.nlargest(adet, "hacim")

    parcalar = []
    for _, r in df.iterrows():
        yon = yon_sinifi(r["degisim"])
        ok = "▲" if yon == "yukari" else ("▼" if yon == "asagi" else "")
        parcalar.append(
            f'<div class="kt-ticker-item">'
            f'<span class="kt-ticker-sym">{esc(r["kod"])}</span>'
            f'<span class="kt-ticker-fiyat">{fiyat_yaz(r["fiyat"])}</span>'
            f'<span class="kt-ticker-yuzde {yon}">{ok} {yuzde(r["degisim"])}</span>'
            f'</div>')
    st.markdown(f'<div class="kt-ticker-wrap">{"".join(parcalar)}</div>',
               unsafe_allow_html=True)


# ============================================================
#  TEKNIK DURUM
# ============================================================

def teknik_durum(df):
    """Mum verisinden 'su an neredeyiz' tablosu. Tahmin degil, tarif."""
    if df is None or len(df) < 30:
        return None
    kapanis = df["kapanis"]
    son = float(kapanis.iloc[-1])
    d = {"rsi": None, "ortalamalar": {}, "oynaklik": None,
         "zirve": None, "dip": None, "zirveden": None}

    r = rsi(kapanis, 14)
    if not r.isna().all():
        d["rsi"] = float(r.iloc[-1])
    for p in (20, 50, 100, 200):
        if len(kapanis) >= p:
            ort = float(kapanis.rolling(p).mean().iloc[-1])
            d["ortalamalar"][p] = {"deger": ort, "uzeri": son > ort,
                                   "fark": (son / ort - 1) * 100}
    a = atr(df, 14)
    if not a.isna().all():
        d["oynaklik"] = float(a.iloc[-1]) / son * 100
    d["zirve"] = float(kapanis.max())
    d["dip"] = float(kapanis.min())
    d["zirveden"] = (son / d["zirve"] - 1) * 100
    return d


def rsi_etiket(deger):
    if deger is None:
        return "—", "veri yok"
    if deger >= 70:
        return f"{deger:.0f}", "aşırı alım bölgesi"
    if deger <= 30:
        return f"{deger:.0f}", "aşırı satım bölgesi"
    if deger >= 55:
        return f"{deger:.0f}", "yükseliş tarafında"
    if deger <= 45:
        return f"{deger:.0f}", "düşüş tarafında"
    return f"{deger:.0f}", "nötr bölge"


# ============================================================
#  SAYFA 1 — PIYASA
# ============================================================

def piyasa_olculeri(depo):
    """Anlik yenilenen piyasa ozeti."""
    o = depo.ozet()
    genel = c_genel()
    korku = c_korku()

    k = st.columns(6)
    with k[0]:
        st.metric("Toplam hacim (24s)", buyuk_sayi(o.get("toplam_hacim")),
                  help="Binance USDT çiftlerinin 24 saatlik toplam işlem "
                       "hacmi. Canlı veriden hesaplanıyor.")
    with k[1]:
        yuk, dus = o.get("yukselen", 0), o.get("dusen", 0)
        st.metric("Yükselen / düşen", f"{yuk} / {dus}",
                  help="Kaç coin 24 saat öncesine göre yukarıda, kaçı "
                       "aşağıda. Piyasanın genel yönünü tek bakışta verir.")
    with k[2]:
        med = o.get("medyan_degisim")
        st.metric("Ortanca değişim", yuzde(med) if med is not None else "—",
                  help="Bütün coinlerin 24 saatlik değişiminin ortası. "
                       "Ortalamadan daha güvenilir, çünkü tek bir coinin "
                       "%400 sıçraması bu sayıyı bozmaz.")
    with k[3]:
        bh = al(genel, "btc_hakimiyet")
        st.metric("BTC hakimiyeti", f"{bh:.1f}%" if bh is not None else "—",
                  help="Bitcoin'in toplam piyasa içindeki payı. Yükselmesi "
                       "paranın Bitcoin'e, düşmesi diğer coinlere kaydığını "
                       "gösterir. Kaynak: CoinGecko (2 dakikada bir)")
    with k[4]:
        st.metric("Toplam piyasa", buyuk_sayi(al(genel, "toplam_deger")),
                  help="Bütün kripto paraların toplam değeri. "
                       "Kaynak: CoinGecko (2 dakikada bir)")
    with k[5]:
        kd = al(korku, "deger")
        if kd is not None:
            ham = al(korku, "sinif")
            st.metric("Korku & Açgözlülük",
                      f"{kd} · {vk.TURKCE_SINIF.get(ham, ham or '')}",
                      help="0-100 arası duygu ölçüsü. 0 aşırı korku, 100 "
                           "aşırı açgözlülük. Günde bir güncellenir, "
                           "anlık olması mümkün değil. "
                           "Kaynak: alternative.me")
        else:
            st.metric("Korku & Açgözlülük", "—")


def _yavas_yenile(anahtar, uretici, saniye=5):
    """
    Bir degeri saniyede bir yerine en fazla <saniye>'de bir yeniden
    hesaplar; arada session_state'teki onbellekten okur.

    NEDEN GEREKLI: "En cok yukselen/dusen" gibi SIRALAMAYA dayali
    grafikler saniyede bir yeniden cizilirse, ufak fiyat oynamalarinda
    bile cubuklar yer degistirir -- goze surekli "titriyor" gibi gorunur.
    5 saniyede bir tazelenmek hem yeterince guncel kalir hem de sakin
    durur. Metrik kutulari (fiyat, yuzde) bundan ETKILENMEZ, onlar hep
    her saniye taze kalir -- sadece SIRALAMA iceren gorseller yavaslatilir.
    """
    depo_anahtari = f"_yavas_{anahtar}"
    simdi = time.time()
    onceki = st.session_state.get(depo_anahtari)
    if onceki is None or simdi - onceki["zaman"] >= saniye:
        deger = uretici()
        st.session_state[depo_anahtari] = {"deger": deger, "zaman": simdi}
        return deger
    return onceki["deger"]


def sayfa_piyasa_canli(depo, en_az_hacim):
    """
    Piyasa sayfasinin SANIYEDE BIR yenilenen kismi: ozet sayilar ve
    genislik gostergesi tam canli; siralamaya dayali grafikler (dagilim,
    en hareketliler) 5 saniyede bir tazelenir -- bkz. _yavas_yenile.

    Arama kutusu icermez -- bkz. asagidaki not.
    """
    st.markdown('<div class="bolum-basligi">Piyasa geneli</div>',
                unsafe_allow_html=True)
    piyasa_olculeri(depo)

    o = depo.ozet()
    df = _yavas_yenile(f"piyasa_df_{en_az_hacim}", lambda: depo.tablo(en_az_hacim))

    s = st.columns([1, 1])
    with s[0]:
        f = gr.genislik_gostergesi(o.get("yukselen", 0), o.get("dusen", 0))
        if f:
            st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                            key="genislik")
        st.caption("Yeşil bölüm yükselen, kırmızı bölüm düşen coin sayısı. "
                   "Hangisi geniş olursa piyasa o yöne meyilli demektir.")
    with s[1]:
        f = gr.piyasa_dagilimi(df)
        if f:
            st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                            key="dagilim")
        st.caption("Sarı çizgi ortanca değişim, noktalı çizgi sıfır. "
                   "Tepe sıfırın sağındaysa çoğunluk yükselmiş. "
                   "(5 saniyede bir tazelenir, sakin durması için.)")

    st.markdown('<div class="bolum-basligi">En hareketli coinler</div>',
                unsafe_allow_html=True)
    s = st.columns(3)
    with s[0]:
        f = gr.degisim_cubuklari(df, "En çok yükselenler", adet=12, artan=True)
        if f:
            st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                            key="yukselenler")
    with s[1]:
        f = gr.degisim_cubuklari(df, "En çok düşenler", adet=12, artan=False)
        if f:
            st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                            key="dusenler")
    with s[2]:
        f = gr.hacim_cubuklari(df, "En yüksek hacimliler", adet=12)
        if f:
            st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                            key="hacimliler")
    st.caption("Bu üç grafik yalnızca hacim süzgecini geçen coinleri kapsar "
               "ve 5 saniyede bir tazelenir (sıralama sürekli değişmesin diye). "
               "Süzgeci kaldırırsanız listeye kimsenin alıp satmadığı, "
               "fiyatı güvenilmez coinler dolar.")


def sayfa_piyasa_tablo(depo, en_az_hacim):
    """
    Bütün coinler tablosu. BILEREK saniyelik canlı parçanın DIŞINDA:
    arama kutusu içindeyken her saniye bir yeniden çizim olsaydı,
    yazarken karakter kaybı ya da imlecin sıçraması gibi can sıkıcı
    bir davranış ortaya çıkabilirdi. Bunun yerine tablo, siz arama/
    sıralama/süzgeç gibi bir şey değiştirdiğinizde güncellenir --
    yüzlerce satırlık bir tabloda zaten saniyede bir yenilenmesine
    gerek yok.
    """
    st.markdown('<div class="bolum-basligi">Bütün coinler</div>',
                unsafe_allow_html=True)
    tum_coinler_tablosu(depo, en_az_hacim)


def _yuzde_renklendir(v):
    """Pandas Styler icin: pozitif yesil, negatif kirmizi, sifir notr."""
    if pd.isna(v):
        return ""
    if v > 0:
        return "color: #26a69a; font-weight: 600;"
    if v < 0:
        return "color: #ef5350; font-weight: 600;"
    return "color: #868993;"


def tum_coinler_tablosu(depo, en_az_hacim):
    ust = st.columns([3, 2, 2, 2])
    with ust[0]:
        arama = st.text_input("Ara", placeholder="BTC, ETH, SOL…",
                              key="tablo_arama", label_visibility="collapsed")
    with ust[1]:
        sirala = st.selectbox("Sırala", ["Hacim", "En çok yükselen",
                                         "En çok düşen", "Fiyat", "İsim"],
                              key="tablo_sirala", label_visibility="collapsed")
    with ust[2]:
        kac = st.selectbox("Kaç satır", [25, 50, 100, 250, "Tümü"], index=1,
                           key="tablo_kac", label_visibility="collapsed")
    with ust[3]:
        st.markdown(canli_gosterge(depo), unsafe_allow_html=True)

    if True:
        df = depo.tablo(en_az_hacim)
        if df.empty:
            st.info("Veri bekleniyor…")
            return

        if arama:
            aranan = arama.strip().upper()
            df = df[df["kod"].str.contains(aranan, na=False)]
            if df.empty:
                st.warning(f"'{arama}' ile eşleşen coin bulunamadı. "
                           "Hacim süzgeci onu gizliyor olabilir.")
                return

        if sirala == "Hacim":
            df = df.sort_values("hacim", ascending=False, na_position="last")
        elif sirala == "En çok yükselen":
            df = df.sort_values("degisim", ascending=False, na_position="last")
        elif sirala == "En çok düşen":
            df = df.sort_values("degisim", ascending=True, na_position="last")
        elif sirala == "Fiyat":
            df = df.sort_values("fiyat", ascending=False, na_position="last")
        else:
            df = df.sort_values("kod")

        toplam = len(df)
        if kac != "Tümü":
            df = df.head(int(kac))

        gosterim = pd.DataFrame({
            "Coin": df["kod"],
            "Fiyat": df["fiyat"],
            "24s %": df["degisim"],
            "Hacim ($)": df["hacim"],
            "24s yüksek": df["yuksek"],
            "24s düşük": df["dusuk"],
            "Güncellik": df["yas_saniye"],
        })

        # "24s %" sutununu yesil/kirmizi renklendiriyoruz. st.dataframe
        # canvas uzerine cizdigi icin normal CSS hucreleri boyayamaz --
        # ama pandas Styler ile verilen background/text rengini
        # Streamlit ozel olarak destekliyor.
        stil = gosterim.style.map(_yuzde_renklendir, subset=["24s %"])

        secim = st.dataframe(
            stil, width="stretch", height=440, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="coin_tablosu",
            column_config={
                "Coin": st.column_config.TextColumn(width="small"),
                "Fiyat": st.column_config.NumberColumn(format="%.6g"),
                "24s %": st.column_config.NumberColumn(format="%+.2f%%"),
                "Hacim ($)": st.column_config.NumberColumn(format="localized"),
                "24s yüksek": st.column_config.NumberColumn(format="%.6g"),
                "24s düşük": st.column_config.NumberColumn(format="%.6g"),
                "Güncellik": st.column_config.NumberColumn(
                    format="%.0f sn", help="Bu coinin fiyatı kaç saniye önce "
                                           "değişti. Büyük sayı, o coinin "
                                           "uzun süre işlem görmediğini gösterir."),
            })

        st.caption(f"{toplam:,} coin listelendi (süzgeç sonrası). "
                   "Bir satıra tıklayıp aşağıdaki düğmeyle analiz sayfasına "
                   "geçebilirsiniz.")

        secili = (secim.selection.rows if secim and secim.selection else [])
        if secili:
            sembol = df.iloc[secili[0]]["sembol"]
            if st.button(f"**{sembol}** analiz sayfasında aç", type="primary",
                         key="secili_ac"):
                st.session_state.secili_coin = sembol
                st.session_state.sayfa = "Coin analizi"
                st.rerun()


# ============================================================
#  SAYFA 2 — COIN ANALIZI
# ============================================================

def canli_fiyat_basligi(depo, sembol):
    """Anlik yenilenen buyuk fiyat gosterimi."""
    k = depo.coin(sembol)
    kod = sembol.split("/")[0]
    if not k:
        st.info("Bu coin için canlı veri bekleniyor…")
        return

    sinif = yon_sinifi(al(k, "degisim"))
    ok = "▲" if sinif == "yukari" else ("▼" if sinif == "asagi" else "■")

    ust = st.columns([4, 1])
    with ust[0]:
        st.markdown(
            f'<div style="font-size:1.15rem; font-weight:600; color:var(--kt-text); '
            f'margin-bottom:2px;">{esc(kod)}<span style="color:var(--kt-text-dim); '
            f'font-weight:400; font-size:0.85rem"> / USDT</span></div>'
            f'<div><span class="dev-fiyat">{fiyat_yaz(k["fiyat"])}</span>'
            f'<span class="dev-degisim {sinif}">{ok} {yuzde(al(k, "degisim"))}</span></div>'
            f'<div class="canli-yazi">son değişim: {yas_yaz(al(k, "yas_saniye") or (time.time() - k["guncelleme"]))}</div>',
            unsafe_allow_html=True)
    with ust[1]:
        # Son ~4 gunun 1 saatlik mumlarindan hafif bir egilim cizgisi.
        # c_mumlar zaten 5 dakika onbellekli, o yuzden saniyelik
        # yenilemede agir bir maliyeti yok.
        mumlar_kisa = c_mumlar(sembol, "1h", 96)
        if mumlar_kisa is not None and len(mumlar_kisa) > 5:
            st.markdown(
                f'<div style="padding-top:14px">'
                f'{gr.mini_sparkline_svg(mumlar_kisa["kapanis"].tolist())}'
                f'<div style="font-size:0.66rem; color:var(--kt-text-dim); '
                f'margin-top:2px;">son 4 gün</div></div>',
                unsafe_allow_html=True)

    s = st.columns(5)
    with s[0]:
        st.metric("24s yüksek", fiyat_yaz(al(k, "yuksek")))
    with s[1]:
        st.metric("24s düşük", fiyat_yaz(al(k, "dusuk")))
    with s[2]:
        st.metric("24s açılış", fiyat_yaz(al(k, "acilis")))
    with s[3]:
        st.metric("Hacim (24s)", buyuk_sayi(al(k, "hacim")))
    with s[4]:
        th = al(k, "temel_hacim")
        st.metric("Miktar (24s)", buyuk_sayi(th, para=False) if th else "—",
                  help="24 saatte kaç tane coin el değiştirdi.")


def coin_statik(depo, sembol):
    """
    Coin sayfasinin YAVAS degisen kismi: piyasa bilgileri, teknik durum,
    vadeli piyasa. Kendini otomatik yenilemez -- sadece siz bir sey
    degistirdiginizde (coin secimi gibi) guncellenir.

    Mum grafigi ARTIK BURADA DEGIL -- bkz. coin_grafik_bolumu(), o canli
    parcaya tasindi ki grafik de "hareketli" hissettirsin.
    """
    kod = sembol.split("/")[0]

    # --- CoinGecko bilgileri (varsa) --------------------
    gecko = c_gecko_ilk250().get(kod)
    if gecko:
        st.markdown('<div class="bolum-basligi">Piyasa bilgileri · CoinGecko</div>',
                    unsafe_allow_html=True)
        s = st.columns(6)
        with s[0]:
            st.metric("Piyasa değeri", buyuk_sayi(gecko.get("market_cap")))
        with s[1]:
            st.metric("Sıralama", f"#{gecko.get('market_cap_rank')}"
                      if gecko.get("market_cap_rank") else "—")
        with s[2]:
            st.metric("Zirve", fiyat_yaz(gecko.get("ath")))
        with s[3]:
            st.metric("Zirveden", yuzde(gecko.get("ath_change_percentage"), 1))
        with s[4]:
            st.metric("7 gün", yuzde(gecko.get("price_change_percentage_7d_in_currency")))
        with s[5]:
            st.metric("30 gün", yuzde(gecko.get("price_change_percentage_30d_in_currency")))

    # --- Teknik durum -----------------------------------
    gunluk = c_mumlar(sembol, "1d", 400)
    teknik = teknik_durum(gunluk)
    if teknik:
        st.markdown('<div class="bolum-basligi">Teknik durum · günlük mumlardan hesaplandı</div>',
                    unsafe_allow_html=True)
        s = st.columns(6)
        with s[0]:
            deger, etiket = rsi_etiket(teknik["rsi"])
            st.metric("RSI (14)", deger, help=f"Şu an: {etiket}")
            st.caption(etiket)
        for sutun, p in zip(s[1:5], (20, 50, 100, 200)):
            with sutun:
                o = teknik["ortalamalar"].get(p)
                if o:
                    st.metric(f"{p} gün ort.", fiyat_yaz(o["deger"]),
                              f"{o['fark']:+.1f}%")
                    st.caption("üzerinde ✓" if o["uzeri"] else "altında ✗")
                else:
                    st.metric(f"{p} gün ort.", "—")
        with s[5]:
            oyn = teknik["oynaklik"]
            st.metric("Günlük oynaklık", f"{oyn:.2f}%" if oyn else "—",
                      help="ATR: fiyat günde ortalama yüzde kaç oynuyor.")

    # --- Vadeli (varsa) ---------------------------------
    canli_k = depo.coin(sembol)
    fonlama = c_fonlama(f"{kod}/USDT:USDT")
    if fonlama:
        acik = c_acik_pozisyon(f"{kod}/USDT:USDT", al(canli_k, "fiyat"))
        st.markdown('<div class="bolum-basligi">Vadeli piyasa</div>',
                    unsafe_allow_html=True)
        s = st.columns(6)
        with s[0]:
            st.metric("Fonlama oranı", f"{fonlama['oran_yuzde']:+.4f}%",
                      help="8 saatte bir el değiştiren ödeme. Pozitif: "
                           "yükseliş bekleyenler kalabalık ve ödüyor. "
                           "Kalabalığın yönünü gösterir, doğru yönü göstermez.")
        with s[1]:
            st.metric("Yıllık karşılığı", f"{fonlama['yillik_yuzde']:+.1f}%")
        with s[2]:
            st.metric("Açık pozisyon", buyuk_sayi(al(acik, "deger_usd")),
                      help="Vadeli piyasada açık duran toplam pozisyon.")


def coin_grafik_bolumu(depo, sembol):
    """
    Mum grafigi bolumu. BILEREK CANLI PARCANIN ICINDE cagriliyor (bkz.
    canli_bolum), yenileme araligina gore (1-5 sn) kendini yeniler.

    Onceden bu bolum coin_statik icindeydi ve hic kendiliginden
    yenilenmiyordu -- grafik hep "az once biten mum"da donuk kalirdi.
    Simdi:
      1. Grafigin sagina, WebSocket'ten gelen canli fiyatla olusan
         "su an olusmakta olan mum" ekleniyor (bkz. grafikler.py
         _canli_mum_ekle).
      2. Fiyatin uzerine, o anki degeri gosteren kesikli bir cizgi
         cizilyor.
      3. uirevision hala korundugu icin yakinlastirmaniz bozulmuyor --
         sadece EN SAGDAKI kisim hareket ediyor, gecmis mumlar yeniden
         cizilmiyor gibi HISSETTIRIYOR (aslinda tum grafik yeniden
         gonderiliyor ama uirevision goruntude sureklilik sagliyor).
    """
    st.markdown('<div class="bolum-basligi">Mum grafiği</div>',
                unsafe_allow_html=True)
    grafik_kontrolleri(depo, sembol)


# TradingView'deki "gosterge ekle" diyaloguna benzer tek bir liste.
# Her secenegin mum_grafigi()'ye nasil aktarilacagi asagida cozuluyor.
GOSTERGE_SECENEKLERI = [
    "Hacim", "RSI", "MACD", "Stokastik",
    "Bollinger Bantları", "VWAP", "Parabolic SAR", "Fibonacci",
]

GOSTERGE_ACIKLAMA = {
    "Hacim": "Alt panelde işlem hacmi çubukları.",
    "RSI": "Alt panelde Göreli Güç Endeksi — 70 üstü aşırı alım, 30 altı aşırı satım.",
    "MACD": "Alt panelde iki hareketli ortalamanın farkı ve momentum histogramı.",
    "Stokastik": "Alt panelde fiyatın son dönemin aralığına göre konumu (0-100).",
    "Bollinger Bantları": "Fiyatın üzerine, 20 dönemlik oynaklık bantları çizer.",
    "VWAP": "Fiyatın üzerine, ekrandaki mumlar boyunca hacim ağırlıklı ortalama fiyat çizgisi.",
    "Parabolic SAR": "Fiyatın üzerine, trend yönünü gösteren noktalar.",
    "Fibonacci": "Fiyatın üzerine, ekrandaki en yüksek/düşük arasında standart geri çekilme seviyeleri.",
}


def canli_grafik_anahtari(sembol):
    """Bu coin icin 'grafigi canli tut' anahtarinin session_state key'i."""
    return f"canli_grafik_{sembol}"


def grafik_kontrolleri(depo, sembol):
    a = st.columns([2, 2, 2, 2])
    with a[0]:
        dilim_adi = st.selectbox("Zaman dilimi", list(gr.ZAMAN_DILIMLERI.keys()),
                                 index=5, key=f"dilim_{sembol}")
    with a[1]:
        adet = st.select_slider("Mum sayısı", [100, 200, 300, 500, 800, 1000],
                                value=300, key=f"adet_{sembol}")
    with a[2]:
        ortalama_tipi = st.radio("Ortalama tipi", ["SMA", "EMA"], horizontal=True,
                                 key=f"orttip_{sembol}",
                                 help="SMA: basit ortalama. EMA: son fiyatlara daha "
                                      "fazla ağırlık verir, daha hızlı tepki verir.")
    with a[3]:
        st.write("")
        if st.button("Grafiği yenile", key=f"yen_{sembol}", width="stretch"):
            c_mumlar.clear()
            st.rerun()

    c = st.columns([3, 5])
    with c[0]:
        canli_tut = st.toggle(
            "Grafiği canlı tut", value=True, key=canli_grafik_anahtari(sembol),
            help="Açıkken grafik saniyede bir güncellenir ve fiyat hareket eder. "
                 "Kapatırsanız grafik sabitlenir ve ÜZERİNE ÇİZDİĞİNİZ ŞEKİLLER "
                 "SİLİNMEZ -- rahatça çizim yapmak için kapatın.")

    # BILEREK tam sayfa yenilemesi zorluyoruz: bu anahtar canli parcanin
    # (fragment) icinde. Icindeki bir seyi degistirmek normalde SADECE
    # o parcayi yeniden calistirir -- ama grafik degisince onu DISARIDAKI
    # durgun bolumde cizdirmemiz gerekiyor, o da ancak tam sayfa
    # yenilemesiyle olur. (Streamlit'in on_change geri cagrisi icinden
    # st.rerun() cagirmak "no-op" -- calismiyor, denedik.)
    #
    # BUNUN YERINE: grafik HER ZAMAN ayni yerde (canli parcada) cizilir.
    # canli_tut kapaliyken tek fark, canli_fiyat=None gecmemiz -- bu da
    # ayni ayarlarla cagrilan gr.mum_grafigi()'nin HER SEFERINDE AYNI
    # (byte-byte ozdes) figur uretmesini saglar. Streamlit, bir onceki
    # turdekiyle AYNI olan buyuk mesajlari tekrar gondermiyor (dahili
    # mesaj onbellegi) -- yani figur degismedigi surece tarayiciya
    # HICBIR SEY gitmiyor ve orada duran cizimleriniz dokunulmadan kalir.
    # (bkz. asagidaki test notu)

    with c[1]:
        st.write("")
        if not canli_tut:
            st.caption("Grafik sabit — çizim yapabilirsiniz, silinmez. "
                       "Tekrar canlı yapmak için anahtarı açın.")

    b = st.columns([3, 3])
    with b[0]:
        ortalamalar = st.multiselect(f"{ortalama_tipi} periyotları", [9, 20, 50, 100, 200],
                                     default=[20, 50, 200], key=f"ort_{sembol}")
    with b[1]:
        secili_gostergeler = st.multiselect(
            "Göstergeler", GOSTERGE_SECENEKLERI, default=["Hacim", "RSI"],
            key=f"gost_{sembol}",
            help="TradingView'deki gösterge listesine benzer: istediğiniz kadar "
                 "ekleyip çıkarabilirsiniz. Her birinin ne çizdiği aşağıda yazıyor.")

    if secili_gostergeler:
        with st.expander(f"Seçili {len(secili_gostergeler)} gösterge ne çiziyor?"):
            for g in secili_gostergeler:
                st.caption(f"**{g}** — {GOSTERGE_ACIKLAMA[g]}")

    dilim = gr.ZAMAN_DILIMLERI[dilim_adi]
    mumlar = c_mumlar(sembol, dilim, adet)
    if mumlar is None or len(mumlar) < 5:
        st.warning("Mum verisi alınamadı. 'Grafiği yenile' düğmesini deneyin.")
        return

    # canli_tut kapaliyken canli fiyat/mum eklemiyoruz -- eklesek bile
    # grafik yeniden cizilmeyecegi icin "donmus ama canli gibi gorunen"
    # yaniltici bir cizgi kalirdi.
    canli_fiyat = al(depo.coin(sembol), "fiyat") if canli_tut else None
    canli_etiket = " · +canlı mum" if canli_fiyat else ""

    secili = set(secili_gostergeler)
    figur = gr.mum_grafigi(
        mumlar, baslik=f"{sembol} · {dilim_adi} · {len(mumlar)} mum{canli_etiket}",
        ortalamalar=tuple(sorted(ortalamalar)), ortalama_tipi=ortalama_tipi,
        rsi_periyot=14 if "RSI" in secili else None,
        bollinger="Bollinger Bantları" in secili,
        hacim="Hacim" in secili,
        macd_panel="MACD" in secili,
        stokastik_panel="Stokastik" in secili,
        vwap_cizgisi="VWAP" in secili,
        parabolik_sar="Parabolic SAR" in secili,
        fibonacci="Fibonacci" in secili,
        canli_fiyat=canli_fiyat,
    )
    if figur:
        st.plotly_chart(figur, width="stretch", config=gr.MUM_PLOTLY_AYARLARI,
                        key=f"mum_{sembol}")
        st.caption("Araç çubuğundaki ✏️ simgelerinden çizgi/dikdörtgen/serbest "
                   "çizim yapabilir, silgi ile tek tek silebilirsiniz. "
                   "Çizimler tarayıcınızda tutulur; coin veya zaman dilimi "
                   "değiştirirseniz temizlenir.")

    ilk, son = mumlar["zaman"].iloc[0], mumlar["zaman"].iloc[-1]
    st.caption(
        f"{ilk:%d.%m.%Y %H:%M} – {son:%d.%m.%Y %H:%M} · Binance · "
        "yeşil mum yükseliş, kırmızı mum düşüş · sürükleyerek kaydırın, "
        "tekerlekle yakınlaştırın · **grafik otomatik yenilenmez** "
        "(yakınlaştırmanız bozulmasın diye)")


# ============================================================
#  SAYFA 3 — KARSILASTIRMA
# ============================================================

def kars_canli_serit(depo):
    """
    Karsilastirma sayfasindaki canli fiyat seridi. Secili coinlerin
    anlik fiyatlarini yan yana gosterir.
    """
    secilenler = st.session_state.get("kars_secim") or ["BTC/USDT", "ETH/USDT"]
    sutunlar = st.columns(max(len(secilenler), 1))
    for sutun, sembol in zip(sutunlar, secilenler):
        k = depo.coin(sembol)
        with sutun:
            st.metric(sembol.replace("/USDT", ""), fiyat_yaz(al(k, "fiyat")),
                      yuzde(al(k, "degisim")) if al(k, "degisim") is not None else None)


def sayfa_karsilastirma(depo, en_az_hacim):
    semboller = depo.semboller(en_az_hacim)
    if not semboller:
        st.info("Coin listesi yükleniyor…")
        return

    ust = st.columns([4, 2, 2])
    with ust[0]:
        varsayilan = [s for s in ("BTC/USDT", "ETH/USDT", "SOL/USDT")
                      if s in semboller][:3]
        secilenler = st.multiselect("Karşılaştırılacak coinler", semboller,
                                    default=varsayilan, max_selections=8,
                                    key="kars_secim",
                                    help="En fazla 8 coin seçebilirsiniz.")
    with ust[1]:
        dilim_adi = st.selectbox("Zaman dilimi", list(gr.ZAMAN_DILIMLERI.keys()),
                                 index=5, key="kars_dilim")
    with ust[2]:
        adet = st.select_slider("Mum sayısı", [60, 100, 200, 365, 500],
                                value=200, key="kars_adet")

    if len(secilenler) < 2:
        st.info("Karşılaştırma için en az 2 coin seçin.")
        return

    dilim = gr.ZAMAN_DILIMLERI[dilim_adi]
    veriler = {}
    for s in secilenler:
        d = c_mumlar(s, dilim, adet)
        if d is not None and len(d) > 5:
            veriler[s] = d

    if len(veriler) < 2:
        st.warning("Seçilen coinler için yeterli veri alınamadı.")
        return

    st.markdown('<div class="bolum-basligi">Aynı başlangıçtan karşılaştırma</div>',
                unsafe_allow_html=True)
    f = gr.karsilastirma(veriler, f"Hepsi başlangıçta 100 kabul edildi · {dilim_adi}")
    if f:
        st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                        key="kars_grafik")
    st.caption("Fiyatlar çok farklı büyüklükte olduğu için (BTC 64.000 $, "
               "DOGE 0,20 $) hepsi başlangıçta 100'e eşitlendi. Böylece "
               "hangisinin yüzde kaç değiştiği doğrudan karşılaştırılabilir.")

    # --- Dönem getirileri tablosu -----------------------
    satirlar = []
    for s, d in veriler.items():
        ilk, son = float(d["kapanis"].iloc[0]), float(d["kapanis"].iloc[-1])
        getiri = (son / ilk - 1) * 100
        gunluk_getiri = d["kapanis"].pct_change().dropna()
        satirlar.append({
            "Coin": s.replace("/USDT", ""),
            "Dönem getirisi %": getiri,
            "En yüksek": float(d["kapanis"].max()),
            "En düşük": float(d["kapanis"].min()),
            "Oynaklık %": float(gunluk_getiri.std() * 100) if len(gunluk_getiri) else None,
            "En büyük düşüş %": _en_buyuk_dusus(d["kapanis"]),
        })
    tablo = pd.DataFrame(satirlar).sort_values("Dönem getirisi %", ascending=False)
    st.dataframe(tablo, width="stretch", hide_index=True,
                 column_config={
                     "Dönem getirisi %": st.column_config.NumberColumn(format="%+.2f%%"),
                     "Oynaklık %": st.column_config.NumberColumn(format="%.2f%%"),
                     "En büyük düşüş %": st.column_config.NumberColumn(format="%.2f%%"),
                     "En yüksek": st.column_config.NumberColumn(format="%.6g"),
                     "En düşük": st.column_config.NumberColumn(format="%.6g"),
                 })
    st.caption("**Oynaklık**: mum başına değişimin standart sapması — büyük "
               "olması fiyatın çok zıpladığını gösterir. **En büyük düşüş**: "
               "bu dönemde zirveden dibe en fazla yüzde kaç kaybedildi. "
               "Getiriden daha güvenilir bir risk ölçüsüdür.")

    st.markdown('<div class="bolum-basligi">Birlikte hareket etme</div>',
                unsafe_allow_html=True)
    f = gr.korelasyon_haritasi(veriler)
    if f:
        st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI,
                        key="kars_korelasyon")
        st.caption("+1'e yakın: neredeyse aynı anda aynı yöne gidiyorlar. "
                   "0'a yakın: birbirinden bağımsız. **Neden önemli:** hepsi "
                   "+0,9 korelasyonlu 10 coin almak, tek coinden 10 kat almak "
                   "gibidir — riski dağıtmış olmazsınız.")
    else:
        st.info("Korelasyon için daha fazla ortak veri gerekiyor.")


def _en_buyuk_dusus(seri):
    zirve, en_kotu = None, 0.0
    for v in seri:
        if zirve is None or v > zirve:
            zirve = v
        d = (v / zirve - 1) * 100
        if d < en_kotu:
            en_kotu = d
    return en_kotu


# ============================================================
#  SAYFA 4 — HABERLER
# ============================================================

def _haber_karti(h):
    """
    NOT: Baslik/ozet RSS'ten geliyor ve icinde <, >, & gibi karakterler
    olabilir (ornek: "A&B", "5 < 10 seviyesi"). html.escape() ile
    kacirilmazsa bu karakterler HTML yapisini bozar -- kartin govdesi
    disina tasabilir ya da bir sonraki karta karisabilir. Kacirmak,
    hem gorunumu korur hem de guvenlik acisindan dogru olandir.
    """
    kaynak_bilgi = hb.KAYNAKLAR.get(h["kaynak"], {})
    sinif = "genel" if kaynak_bilgi.get("tur") == "genel" else ""
    coin_html = "".join(f'<span class="haber-coin">{esc(c)}</span>' for c in h["coinler"])
    yas = esc(hb.yas_yaz(h["zaman"]))
    link = esc(h["link"] or "#")
    kaynak = esc(h["kaynak"])
    baslik = esc(h["baslik"])
    ozet = esc(h["ozet"]) if h["ozet"] else ""

    parcalar = [f'<a class="haber-kart" href="{link}" target="_blank" rel="noopener">']
    parcalar.append(
        f'<div class="haber-ust"><span class="haber-kaynak {sinif}">{kaynak}</span>'
        f'<span>{yas}</span></div>')
    parcalar.append(f'<div class="haber-baslik">{baslik}</div>')
    if ozet:
        parcalar.append(f'<div class="haber-ozet">{ozet}</div>')
    if coin_html:
        parcalar.append(f'<div style="margin-top:6px">{coin_html}</div>')
    parcalar.append("</a>")
    return "".join(parcalar)


def sayfa_haberler():
    """
    9 global kaynaktan (7 kripto-odakli + 2 genel piyasa) toplanan
    haber akisi. RSS ile calisir, API anahtari gerektirmez.

    5 dakikada bir kendini yeniliyor -- haberler saniyede degismiyor,
    o yuzden bu sayfa "anlik" canli parcanin DISINDA tutuluyor.
    """
    hepsi, basarili, basarisiz = c_haberler()

    ust = st.columns([2, 2, 5, 1])
    with ust[0]:
        tur_secim = st.selectbox("Tür", ["Hepsi", "Sadece kripto", "Sadece genel piyasa"],
                                 key="haber_tur")
    with ust[1]:
        kaynaklar_secili = st.multiselect(
            "Kaynak", sorted(hb.KAYNAKLAR.keys()), default=[], key="haber_kaynak",
            placeholder="Tüm kaynaklar")
    with ust[2]:
        arama = st.text_input("Haberlerde ara", placeholder="BTC, ETF, Fed…",
                              key="haber_arama", label_visibility="collapsed")
    with ust[3]:
        if st.button("Yenile", key="haber_yenile", help="Haberleri şimdi yeniden çek"):
            c_haberler.clear()
            st.rerun()

    liste = hepsi
    if tur_secim == "Sadece kripto":
        liste = [h for h in liste if hb.KAYNAKLAR.get(h["kaynak"], {}).get("tur") == "kripto"]
    elif tur_secim == "Sadece genel piyasa":
        liste = [h for h in liste if hb.KAYNAKLAR.get(h["kaynak"], {}).get("tur") == "genel"]
    if kaynaklar_secili:
        liste = [h for h in liste if h["kaynak"] in kaynaklar_secili]
    if arama:
        a = arama.strip().lower()
        liste = [h for h in liste if a in h["baslik"].lower() or a in (h["ozet"] or "").lower()]

    if basarisiz:
        st.caption(f"⚠️ Şu kaynaklara şu an ulaşılamadı: {', '.join(basarisiz)}. "
                   "Diğer kaynaklardan gelen haberler gösteriliyor.")

    if not liste:
        st.info("Bu süzgeçlerle eşleşen haber yok. Süzgeçleri gevşetmeyi deneyin.")
        return

    st.caption(f"{len(liste)} haber · {len(basarili)} kaynaktan · "
               "5 dakikada bir tazeleniyor · başlığa tıklayınca kaynağında açılır")

    # Her karti AYRI bir st.markdown cagrisiyla basmak yerine, her
    # sutunun butun kartlarini TEK bir metinde birlestirip TEK seferde
    # basiyoruz. Boylece hem daha az Streamlit elemani olusuyor (daha
    # akici) hem de art arda gelen benzer HTML parcalarinin birbirine
    # karismasi ihtimali ortadan kalkiyor.
    sol_kartlar, sag_kartlar = [], []
    for i, h in enumerate(liste):
        (sol_kartlar if i % 2 == 0 else sag_kartlar).append(_haber_karti(h))

    sol, sag = st.columns(2)
    with sol:
        st.markdown("".join(sol_kartlar), unsafe_allow_html=True)
    with sag:
        st.markdown("".join(sag_kartlar), unsafe_allow_html=True)


# ============================================================
#  ANALIZ BOTU
# ============================================================
#
# BU SAYFA TAVSIYE VERMEZ. Tek bir "AL/SAT" ya da genel bir puan
# URETMEZ -- BILEREK. Asagida analiz_botu.py'deki fonksiyonlarin
# dondurdugu HAM, birbirinden BAGIMSIZ gozlemleri, tek tek, oldugu
# gibi listeler. Bazen ayni anda hem "yukari" hem "asagi" yonlu
# gozlemler birlikte gorunur -- bu bir hata degil, piyasanin dogasi
# (bkz. analiz_botu.py basindaki durustluk notu).
#
# Gunluk mum verisi kullanir (teknik durum kutusuyla ayni kaynak),
# o yuzden saniyede bir degismez -- bu sayfa da Haberler gibi CANLI
# PARCANIN DISINDA, sadece coin degistirince yenilenir.

_YON_ETIKET = {
    "yukari": "▲ yukarı yönlü okunuyor",
    "asagi": "▼ aşağı yönlü okunuyor",
    "notr": "● yön belirtmiyor",
}


def _gozlem_karti(g):
    yon_etiket = _YON_ETIKET.get(g["yon"], g["yon"])
    return (
        f'<div class="gozlem-kart {g["yon"]}">'
        f'<div class="gozlem-ust">'
        f'<span class="gozlem-kategori">{esc(g["kategori"])}</span>'
        f'<span class="gozlem-yon">{yon_etiket}</span>'
        f'</div>'
        f'<div class="gozlem-baslik">{esc(g["baslik"])}</div>'
        f'<div class="gozlem-aciklama">{esc(g["aciklama"])}</div>'
        f'</div>'
    )


def _likidite_karti(r):
    """
    _gozlem_karti ile ayni CSS'i (gozlem-kart) kullanir -- likidite avi
    gozlemleri de yon tasidigi icin (yukari/asagi) ayni yesil/kirmizi
    renklendirme anlamli. Ust etikette kategori yerine COIN KODU
    gosterilir (bu, coklu-coin taramasi sonucu oldugu icin).
    """
    yon_etiket = _YON_ETIKET.get(r["yon"], r["yon"])
    return (
        f'<div class="gozlem-kart {r["yon"]}">'
        f'<div class="gozlem-ust">'
        f'<span class="gozlem-kategori">{esc(r["kod"])}</span>'
        f'<span class="gozlem-yon">{yon_etiket}</span>'
        f'</div>'
        f'<div class="gozlem-baslik">{esc(r["baslik"])}</div>'
        f'<div class="gozlem-aciklama">{esc(r["aciklama"])}</div>'
        f'</div>'
    )


_TARAMA_ETIKET = {
    "teyitli": "sıkışma + hacim + vadeli teyidi",
    "guclu": "sıkışma + yukarı hacim",
    "sikisma": "sadece sıkışma",
}


def _tarama_karti(r):
    seviye = r["seviye"]
    etiket_metin = _TARAMA_ETIKET[seviye]
    detay = " · ".join(o["baslik"] for o in r["gozlemler"])
    return (
        f'<div class="tarama-kart {seviye}">'
        f'<div class="tarama-kart-ust">'
        f'<span class="tarama-kart-kod">{esc(r["kod"])}</span>'
        f'<span class="tarama-kart-etiket {seviye}">{esc(etiket_metin)}</span>'
        f'</div>'
        f'<div class="tarama-kart-detay">{esc(detay)}</div>'
        f'</div>'
    )


def _tarama_karti_goster(r):
    """
    Karti cizer. NOT: kartin altina dogrudan "bu coine git" dugmesi
    KOYMAYA CALISTIK ama koymadik -- bu kart bir @st.fragment icinde
    cizildigi icin (bkz. _piyasa_taramasi_bolumu), o dugmenin
    st.session_state.secili_coin degistirip sayfanin geri kalanini
    (kenar cubugundaki arama kutusu, asagidaki tek-coin gozlem bolumu)
    guncellemesi gerekiyordu. Hem "if st.button(): ...; st.rerun()" hem
    "on_click callback" yollarini denedik; ikisinde de dugmeye basmak
    hicbir hataya yol acmadan sessizce hicbir sey degistirmedi (coin
    secimi degismedi) -- Streamlit'in fragment icindeki widget'lari
    varsayilan olarak SADECE o fragment'i yeniden calistirmasindan
    kaynaklaniyor gibi gorunuyor. O yuzden burada sadece kart var;
    incelemek istediginiz coini kenar cubugundaki arama kutusundan
    seciyorsunuz.
    """
    st.markdown(_tarama_karti(r), unsafe_allow_html=True)


class _TaramaDurumu:
    """
    Arka planda calisan piyasa taramasinin PAYLASILAN durumu.

    NEDEN GEREKLI: Tarama 100+ coin icin sirayla agdan veri cekiyor,
    bu da (ozellikle hacim suzgecini gevsetince) dakikalar surebilir.
    Bunu dugmeye basar basmaz ANA BETIKTE calistirsaydik, Streamlit o
    sure boyunca butun sayfayi (fiyat seridi, sayfa/coin degistirme,
    her sey) dondururdu -- "uygulama kitlendi" hissi verirdi. Bunun
    yerine tarama ARKA PLANDA (ayri bir is parcacigi) calisiyor, bu
    nesne ilerlemeyi tasiyor, kucuk bir parca (fragment) da periyodik
    olarak buradan okuyup ekrani guncelliyor -- sayfanin geri kalani
    bu sirada tikanmiyor.
    """

    def __init__(self):
        self.kilit = threading.Lock()
        self.calisiyor = False
        self.asama = ""          # "spot" | "vadeli" | ""
        self.ilerleme = 0
        self.toplam = 0
        self.sonuc = None
        self.zaman = None
        self.hacim_esigi = None  # son taramanin hangi suzgecle yapildigi
        self.likidite_sonuc = None  # likidite avi (SFP) tespitleri, ayrı liste


def _tarama_durumu():
    if "tarama_durumu" not in st.session_state:
        st.session_state.tarama_durumu = _TaramaDurumu()
    return st.session_state.tarama_durumu


def _piyasa_taramasi_arka_plan(durum, semboller):
    """
    ARKA PLAN IS PARCACIGINDA calisir -- ICINDE HICBIR st.* CAGRISI
    OLAMAZ (Streamlit'in ekrana yazma fonksiyonlari sadece ana betik
    parcaciginda calisir, baska bir threadden cagrilirsa calismaz).
    Bu fonksiyon SADECE veri ceker/hesaplar ve ilerlemeyi 'durum'
    nesnesine yazar; ekrana yazdirmayi disaridaki fragment
    (_piyasa_taramasi_bolumu) yapar.

    IKI ASAMALI tarama:
    1) HER coin icin (spot, zaten 5 dk onbellekli c_mumlar uzerinden)
       gunluk mum cekip ab.tarama_adayi ile sikisma/yukari-hacim deseni
       arar.
    2) Sadece 1. asamada "guclu" cikan -- genelde COK daha kucuk --
       bir alt kumeye, vadeli piyasa (fonlama + acik pozisyon) teyidi
       arar. Coklarin cogu vadeli piyasasi olmayan altcoin'ler oldugu
       icin 2. asama onlarda hicbir zaman "teyitli"ye yukselmez -- bu
       bir hata degil, teyit edilecek veri olmadigi anlamina gelir.
    """
    sonuclar = []
    likidite_sonuclari = []
    toplam = len(semboller)
    with durum.kilit:
        durum.asama, durum.ilerleme, durum.toplam = "spot", 0, toplam

    # TUM govde try/finally ICINDE: burada beklenmedik bir hata (ag
    # sorunu, bozuk veri...) cikarsa bile finally BLOGU calisiyor=False
    # yazmayi GARANTI eder. Bu olmadan, herhangi bir istisna bu is
    # parcacigini sessizce olduruyor ve durum.calisiyor sonsuza kadar
    # True kaliyor -- kullanici "taranıyor…" ekraninda kilitli kaliyor
    # ve "Piyasayı tara" dugmesi uygulama yeniden baslatilana kadar
    # devre disi kaliyor. (Bu tam olarak once yasadigimiz bir hataydi:
    # gozlem_likidite_avi bir coin icin df=None geldiginde patliyordu --
    # bkz. analiz_botu.py'deki None kontrolu -- ama bu try/finally,
    # BENZER herhangi bir gelecekteki hataya karsi da bir guvenlik agi.)
    try:
        for i, sembol in enumerate(semboller):
            df = c_mumlar(sembol, "1d", 400)
            aday = ab.tarama_adayi(df)
            if aday:
                sonuclar.append({"sembol": sembol, "kod": sembol.split("/")[0], **aday})
            # Likidite avi (SFP) tespiti AYNI veriyle (df) yapiliyor -- ek
            # borsa istegi gerekmiyor, o yuzden butun listeye uygulamak
            # ucuz. Sonuc bagimsiz bir liste: sikisma/hacim taramasindan
            # tamamen farkli bir desen, coklarin ikisi de gorebilir.
            for g in ab.gozlem_likidite_avi(df):
                likidite_sonuclari.append({"sembol": sembol, "kod": sembol.split("/")[0], **g})
            with durum.kilit:
                durum.ilerleme = i + 1

        guclu_adaylar = [r for r in sonuclar if r["seviye"] == "guclu"]
        if guclu_adaylar:
            with durum.kilit:
                durum.asama = "vadeli"
                durum.ilerleme, durum.toplam = 0, len(guclu_adaylar)
            for i, r in enumerate(guclu_adaylar):
                vsembol = f"{r['kod']}/USDT:USDT"
                fonlama = c_fonlama(vsembol)
                oi_gecmisi = c_oi_gecmisi(vsembol)
                if ab.kurulum_teyidi(fonlama, oi_gecmisi):
                    r["seviye"] = "teyitli"
                with durum.kilit:
                    durum.ilerleme = i + 1

        # Sadece katmana gore sirala -- koda gore AYRICA sirlamiyoruz ki her
        # katman icinde semboller'den gelen "hacme gore buyukten kucuge"
        # sirasi (bkz. canli_veri.semboller) korunsun. Boylece en likit
        # coinler her katmanin basinda gorunur.
        sira = {"teyitli": 0, "guclu": 1, "sikisma": 2}
        sonuclar.sort(key=lambda r: sira[r["seviye"]])

        # Hacim teyitli likidite avilari once, sonra semboller sirasi (yine
        # hacme/likiditeye gore) korunur.
        likidite_sonuclari.sort(key=lambda r: "teyitli" not in r["baslik"])
    finally:
        # Yarida kesilse bile (istisna), o ana kadar toplanan sonuclari
        # gosteriyoruz -- hicbir sey gostermemekten iyidir. Onemli olan
        # calisiyor=False'un HER KOSULDA yazilmasi.
        with durum.kilit:
            durum.sonuc = sonuclar
            durum.likidite_sonuc = likidite_sonuclari
            durum.zaman = datetime.now().strftime("%H:%M:%S")
            durum.calisiyor = False
            durum.asama = ""


def _fragment_rerun_dene():
    """
    st.rerun(scope="fragment") cagirir -- ama kullanici tam da bu sirada
    baska bir sayfaya gecmisse (kenar cubugundaki radyo tam sayfa
    yenilemesi baslattiysa), bu betik artik bir fragment icinde
    calismiyor sayilabilir ve Streamlit StreamlitAPIException firlatir
    ("scope=fragment sadece fragment yeniden calismalarinda kullanilabilir").
    Bunu YAKALAYIP YOK SAYIYORUZ -- zaten kullanici baska sayfaya
    gectiyse, sayfa degisikligini tetikleyen TAM SAYFA yenilemesi
    kendiliginden devam edecek, burada patlamamiza gerek yok.
    """
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        pass


@st.fragment
def _piyasa_taramasi_bolumu(depo, en_az_hacim):
    """
    ONEMLI: run_every KULLANMIYORUZ. Once run_every=1.5 ile denedik ama
    bu, tarama bitse BILE sonsuza kadar 1.5 saniyede bir bu parcayi
    yeniden calistirmaya devam ediyordu -- bu da kenar cubugundaki sayfa
    degistirme gibi TAM SAYFA yenilemesi gereken tiklamalarin bir turlu
    islenememesine yol aciyordu (test ederken yakaladik: taramadan cok
    sonra bile "Piyasa" sekmesine tiklamak calismiyordu). Bunun yerine,
    SADECE tarama gercekten calisirken kendini kisa araliklarla yeniden
    calistiriyor (asagidaki st.rerun(scope="fragment")); tarama
    bittiginde kendiliginden susuyor ve sayfa navigasyonu normale doner.
    """
    st.markdown('<div class="bolum-basligi">Piyasa taraması · 3 faktör hizalanması</div>',
                unsafe_allow_html=True)
    with st.expander("Bu ne demek? (üç faktör nedir, neden garanti değildir)"):
        st.caption(
            "Üç bağımsız durumu birlikte arar: (1) fiyat sıkışması — hareket "
            "yaklaşıyor olabilir, (2) yukarı yönlü hacim — birikim/patlama "
            "işareti, (3) vadeli piyasa teyidi — fonlama aşırı kalabalık "
            "değil ve açık pozisyon artıyor. **Üçü birden hizalandığında bile "
            "bu bir tahmin ya da garanti değildir** — sadece piyasada yaygın "
            "izlenen üç durumun AYNI ANDA görüldüğü anlamına gelir. Vadeli "
            "piyasası olmayan coinler (çoğu küçük altcoin) 3. bacağı hiç "
            "teyit edemez, bu onların 'kötü' olduğu anlamına gelmez.")

    semboller = depo.semboller(en_az_hacim)
    durum = _tarama_durumu()

    with durum.kilit:
        calisiyor = durum.calisiyor
        asama = durum.asama
        ilerleme = durum.ilerleme
        toplam_durum = durum.toplam
        sonuc = durum.sonuc
        likidite_sonuc = durum.likidite_sonuc
        zaman = durum.zaman
        eski_esik = durum.hacim_esigi

    uyari_esik = 400
    if len(semboller) > uyari_esik and not calisiyor:
        st.caption(f"⚠️ Şu an {len(semboller)} coin taranacak — bu, "
                   "birkaç dakika sürebilir. Arka planda çalıştığı için "
                   "uygulamanın diğer kısımlarını bu sırada kullanabilirsiniz.")

    tara_tiklandi = st.button(
        "Piyasayı tara", key="tarama_dugmesi", disabled=calisiyor,
        help=f"Hacim süzgecini geçen {len(semboller)} coini tarar. Arka "
             "planda çalışır -- taranırken sayfanın diğer kısımlarını "
             "kullanabilirsiniz. Daha geniş taramak için kenar çubuğundaki "
             "'En az 24s hacim' süzgecini 'Süzgeç yok' yapabilirsiniz -- ama "
             "o zaman listeye kimsenin alıp satmadığı, fiyatı güvenilmez "
             "coinler de girer.")

    if tara_tiklandi and not calisiyor:
        with durum.kilit:
            durum.calisiyor = True
            durum.hacim_esigi = en_az_hacim
        threading.Thread(target=_piyasa_taramasi_arka_plan,
                         args=(durum, semboller), daemon=True,
                         name="piyasa-taramasi").start()
        _fragment_rerun_dene()

    if calisiyor:
        etiket = ("Spot veriler taranıyor" if asama == "spot"
                  else "Vadeli piyasa teyidi kontrol ediliyor")
        oran = (ilerleme / toplam_durum) if toplam_durum else 0.0
        st.progress(oran, text=f"{etiket}… {ilerleme}/{toplam_durum}")
        st.markdown("---")
        # Tarama surdukce kendini kisa araliklarla yeniden calistirip
        # ilerlemeyi tazeler. Tarama bitince (calisiyor False olunca)
        # bu satira hic gelinmez -- parca sessizce durur, bkz. yukaridaki
        # not.
        time.sleep(1.2)
        _fragment_rerun_dene()
        return

    if zaman:
        uyari_metni = ""
        if eski_esik is not None and eski_esik != en_az_hacim:
            uyari_metni = (f" · ⚠️ o zamanki hacim süzgeci farklıydı "
                          f"({buyuk_sayi(eski_esik)} — şimdi "
                          f"{buyuk_sayi(en_az_hacim)}); sonuçlar güncel "
                          "süzgeçle eşleşmeyebilir, tekrar tarayın")
        st.caption(f"Son tarama: {zaman} · {len(sonuc or [])} coin "
                   f"işaretlendi{uyari_metni}")

    if sonuc is None:
        st.info("Henüz taranmadı. Yukarıdaki düğmeye basın.")
    elif not sonuc:
        st.info("Şu an sıkışma ya da yukarı yönlü hacim sinyali gösteren "
                "coin yok.")
    else:
        teyitli = [r for r in sonuc if r["seviye"] == "teyitli"]
        guclu = [r for r in sonuc if r["seviye"] == "guclu"]
        sikisma = [r for r in sonuc if r["seviye"] == "sikisma"]

        if teyitli:
            st.markdown("**Sıkışma + yukarı hacim + vadeli teyidi** (3 faktör hizalı)")
            kolonlar = st.columns(3)
            for i, r in enumerate(teyitli):
                with kolonlar[i % 3]:
                    _tarama_karti_goster(r)
        if guclu:
            st.markdown("**Sıkışma + yukarı hacim**" +
                        (" (vadeli teyidi yok/yetersiz)" if teyitli else ""))
            kolonlar = st.columns(3)
            for i, r in enumerate(guclu):
                with kolonlar[i % 3]:
                    _tarama_karti_goster(r)
        if sikisma:
            st.markdown("**Sadece sıkışma** (hacim henüz hareketlenmedi)")
            kolonlar = st.columns(3)
            for i, r in enumerate(sikisma):
                with kolonlar[i % 3]:
                    _tarama_karti_goster(r)
        st.caption("İncelemek istediğiniz coini kenar çubuğundaki arama "
                   "kutusundan seçebilirsiniz.")

    # Likidite avi (SFP) sonuclari, yukaridaki sikisma taramasindan
    # BAGIMSIZ -- sonuc bos/None olsa bile burada bir sey cikabilir,
    # o yuzden ayri, kosulsuz bir blok.
    if likidite_sonuc:
        st.markdown('<div class="bolum-basligi" style="margin-top:14px;">'
                    'Likidite avı / sahte kırılım taraması</div>',
                    unsafe_allow_html=True)
        st.caption(
            "Fiyatın bir önceki destek/direnç seviyesini FİTİLLE kırıp "
            "KAPANIŞTA geri döndüğü coinleri arar — 'likidite avı', "
            "'stop hunt' ya da 'Swing Failure Pattern (SFP)' olarak "
            "bilinen, o seviyede bekleyen stop-loss/kırılım emirlerinin "
            "süpürüldüğü örüntü. Hacmi de ortalamanın belirgin üzerinde "
            "olanlar '(hacim teyitli)' diye işaretlenir — bu, süpürmenin "
            "gerçek bir emir akışıyla mı yoksa sessiz bir dalgalanmayla mı "
            "olduğunu ayırt etmeye yardım eder. **Bu bir tahmin değildir** "
            "— desen yaygın izlenir ama her sahte kırılım gerçekten "
            "dönmez.")

        boga = [r for r in likidite_sonuc if r["yon"] == "yukari"]
        ayi = [r for r in likidite_sonuc if r["yon"] == "asagi"]

        if boga:
            st.markdown("**Destek fitille kırıldı, kapanış geri döndü** "
                        "(olası sahte düşüş)")
            kolonlar = st.columns(3)
            for i, r in enumerate(boga):
                with kolonlar[i % 3]:
                    st.markdown(_likidite_karti(r), unsafe_allow_html=True)
        if ayi:
            st.markdown("**Direnç fitille kırıldı, kapanış geri döndü** "
                        "(olası sahte yükseliş)")
            kolonlar = st.columns(3)
            for i, r in enumerate(ayi):
                with kolonlar[i % 3]:
                    st.markdown(_likidite_karti(r), unsafe_allow_html=True)
        st.caption("İncelemek istediğiniz coini kenar çubuğundaki arama "
                   "kutusundan seçebilirsiniz.")

    st.markdown("---")


def sayfa_analiz_botu(depo, sembol, en_az_hacim):
    kod = sembol.split("/")[0]

    st.markdown('<div class="bolum-basligi">Analiz Botu</div>', unsafe_allow_html=True)
    st.warning(
        "**Bu bot tavsiye vermez.** Al/sat önerisi, hedef fiyat ya da genel "
        "bir 'sinyal puanı' üretmez. Piyasada yaygın olarak izlenen teknik "
        "durumları tek tek, ham haliyle listeler — yorumu size bırakır. "
        "Bazı gözlemler birbiriyle çelişebilir; bu normaldir. Ayrıca daha "
        "önce test ettiğimiz gibi (bkz. README.md), bu gözlemlerin dayandığı "
        "standart göstergelerin hiçbiri geleceği güvenilir şekilde tahmin "
        "edemedi — burada olmalarının sebebi piyasa katılımcıları tarafından "
        "yaygın izlenmeleri, 'işe yaradıklarının kanıtlanmış olması' değil.")

    _piyasa_taramasi_bolumu(depo, en_az_hacim)

    gunluk = c_mumlar(sembol, "1d", 400)
    if gunluk is None or len(gunluk) < 25:
        st.info("Bu coin için yeterli geçmiş veri yok, gözlem üretilemiyor.")
        return

    fonlama = c_fonlama(f"{kod}/USDT:USDT")
    defter = c_defter(sembol)
    oi_gecmisi = c_oi_gecmisi(f"{kod}/USDT:USDT")
    btc_gunluk = c_mumlar("BTC/USDT", "1d", 400) if kod != "BTC" else None

    gozlemler = ab.tum_gozlemler(gunluk, fonlama=fonlama, defter=defter,
                                  df_btc=btc_gunluk, sembol_kodu=kod,
                                  oi_gecmisi=oi_gecmisi)

    if not gozlemler:
        st.info(f"{kod} için şu an dikkat çekici bir gözlem yok — fiyat, "
                "izlenen seviyelerin ve göstergelerin çoğundan uzakta "
                "seyrediyor.")
        return

    st.caption(f"{kod} için {len(gozlemler)} gözlem · günlük mumlardan "
               "hesaplandı · coin değiştirince yenilenir")

    kategoriler = []
    for g in gozlemler:
        if g["kategori"] not in kategoriler:
            kategoriler.append(g["kategori"])

    sol, sag = st.columns(2)
    for i, kategori in enumerate(kategoriler):
        hedef = sol if i % 2 == 0 else sag
        kartlar = [_gozlem_karti(g) for g in gozlemler if g["kategori"] == kategori]
        with hedef:
            st.markdown(f'<div class="bolum-basligi" style="font-size:0.85rem; '
                        f'margin-top:10px;">{esc(kategori)}</div>', unsafe_allow_html=True)
            st.markdown("".join(kartlar), unsafe_allow_html=True)


# ============================================================
#  TRADE AJANI  (ayri bir projeden aktarilan 4 dogrulanmis strateji)
# ============================================================
#
# trade_ajani_stratejileri.py, "Trade-ajani" adli AYRI bir projede
# (egitim/test - IS/OOS - ayrimli genis taramalarla dogrulanmis)
# stratejilerin bu projenin kalibina uyarlanmis hali (-1.0=SHORT,
# 0.0=nakit, 1.0=LONG -- 2026-09-12'de SHORT destegi ORIJINAL Trade-ajani
# mantigina gore geri getirildi, ilk aktarimda LONG-only'ye
# indirgenmisti). Bu sayfa SADECE onlarin GUNCEL durumunu gosterir -
# sanal_trader.py (canli rotasyon botu) AYNI stratejileri kullanir ama
# bu sayfa onu tetiklemez, sadece kendi anlik hesabini gosterir.
# Ayrintili bulgular: TRADE_AJANI_BULGULARI.md.
#
# Gunluk mum ile calisan Analiz Botu'nun aksine bu sayfa 1 SAATLIK mum
# kullanir (stratejiler o zaman diliminde dogrulandi) - o yuzden bu da
# CANLI PARCANIN DISINDA, sadece coin degistirince yenilenir.

_TRADE_AJANI_DURUM_ETIKET = {
    "LONG": ("🟢", "Pozisyonda (LONG)"),
    "SHORT": ("🔴", "Pozisyonda (SHORT)"),
    "NAKIT": ("⚪", "Nakitte"),
    "ISINIYOR": ("🟡", "Isınıyor (yetersiz geçmiş)"),
}


def _trade_ajani_pozisyon_ozeti(poz: pd.Series, zaman: pd.Series) -> dict:
    gecerli = poz.dropna()
    if gecerli.empty:
        return {"durum": "ISINIYOR", "beri": None}
    son = float(gecerli.iloc[-1])
    degisim = gecerli[gecerli != gecerli.shift(1)]
    ilk_idx = gecerli.index[0]
    son_degisim_idx = degisim.index[-1] if len(degisim) else ilk_idx
    if son == 1.0:
        durum = "LONG"
    elif son == -1.0:
        durum = "SHORT"
    else:
        durum = "NAKIT"
    return {"durum": durum, "beri": zaman.loc[son_degisim_idx]}


def sayfa_trade_ajani(sembol):
    kod = sembol.split("/")[0]
    st.markdown('<div class="bolum-basligi">Trade Ajanı Stratejileri</div>', unsafe_allow_html=True)
    st.info(
        "Bu 4 strateji **ayrı bir projede** (Trade-ajanı), eğitim/test (IS/OOS) "
        "ayrımlı geniş taramalarla doğrulandı ve buraya **LONG+SHORT** (orijinal) "
        "mantığıyla aktarıldı. **Kırılım-GeriÇekilme-Toparlanma** küçük/orta "
        "ölçekli altcoinler, **Major Trend Sürücüsü** büyük/likit coinler için "
        "tasarlandı — seçili coin ikisine de uymayabilir. Bu sayfa yalnızca "
        "GÜNCEL durumu gösterir; canlı Sanal Trader botu aynı stratejileri "
        "kendi rotasyonunda kullanır. Ayrıntılı doğrulama sonuçları: "
        "`TRADE_AJANI_BULGULARI.md`."
    )

    df = c_mumlar(sembol, "1h", 1000)
    if df is None or len(df) < 250:
        st.info(f"{kod} için 1 saatlik yeterli geçmiş veri yok, gösterilemiyor.")
        return

    ozetler = []
    for isim, fn, params in taj.STRATEJILER:
        try:
            poz = fn(df, **params)
            ozet = _trade_ajani_pozisyon_ozeti(poz, df["zaman"])
            ozet["isim"], ozet["hata"] = isim, None
        except Exception as exc:
            ozet = {"isim": isim, "hata": str(exc), "durum": None, "beri": None}
        ozetler.append(ozet)

    kol = st.columns(len(ozetler))
    for hedef, ozet in zip(kol, ozetler):
        with hedef:
            if ozet["hata"]:
                st.error(f"**{ozet['isim']}**\n\nHata: {ozet['hata'][:80]}")
                continue
            simge, etiket = _TRADE_AJANI_DURUM_ETIKET[ozet["durum"]]
            beri_metin = ozet["beri"].strftime("%Y-%m-%d %H:%M") if ozet["beri"] is not None else "—"
            st.metric(ozet["isim"], f"{simge} {etiket}")
            st.caption(f"beri: {beri_metin}")

    st.caption(f"{kod} · 1 saatlik mumlar · son {len(df)} bar · coin değiştirince yenilenir.")

    # --- GECMISE DONUK ANALIZ (2026-09-12'de eklendi) -----------
    # Kullanicinin KENDI SECTIGI strateji + coin + gun sayisiyla, ayri bir
    # "Calistir" butonuna basinca calisan, tek seferlik bir geriye donuk
    # test. Sayfanin geri kalani (yukaridaki durum kartlari) SURESIZ/
    # otomatik calisirken, bu bolum BILEREK sadece butona basinca calisir
    # -- 40 gunluk saatlik veri + simulasyon her navigasyonda/1 saniyede
    # bir kosarsa gereksiz agir olur.
    st.markdown('<div class="bolum-basligi" style="margin-top:20px;">Geçmişe Dönük Analiz</div>',
                unsafe_allow_html=True)
    st.caption(
        "Seçtiğiniz stratejiyi, seçili coin için geçmiş veride tek seferlik çalıştırır — "
        "getiri, en büyük düşüş, işlem listesi ve bir portföy eğrisi gösterir. **Bu bir "
        "garanti değildir**: geçmişte iyi giden bir strateji geleceği garanti etmez, "
        "burada IS/OOS (eğitim/test) ayrımı da yapılmaz — sadece tek bir dönemin "
        "sonucunu gösterir (tarafsız doğrulama için bkz. `research/` klasöründeki "
        "Trade-ajanı taramaları)."
    )
    kontrol = st.columns([2, 2, 1])
    with kontrol[0]:
        secilen_isim = st.selectbox(
            "Strateji", [isim for isim, _, _ in taj.STRATEJILER], key="ta_analiz_strateji")
    with kontrol[1]:
        gun_sayisi = st.slider(
            "Kaç gün geriye bakılsın", min_value=7, max_value=40, value=30, step=1,
            key="ta_analiz_gun", help="1 saatlik mumlarla tek bir borsa isteğinin "
            "güvenle döndürebildiği üst sınıra göre 40 günle sınırlandı.")
    with kontrol[2]:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        calistir = st.button("Çalıştır", key="ta_analiz_calistir", width="stretch")

    if calistir:
        strateji_sozlugu = {isim: (fn, params) for isim, fn, params in taj.STRATEJILER}
        fn, params = strateji_sozlugu[secilen_isim]
        isinma = taj.isinma_suresi(secilen_isim, params)
        adet = gun_sayisi * 24 + isinma + 20
        df_analiz = c_mumlar(sembol, "1h", adet)
        if df_analiz is None or len(df_analiz) < isinma + 30:
            st.warning(f"{kod} için seçilen aralıkta yeterli veri alınamadı.")
        else:
            try:
                poz = fn(df_analiz, **params)
            except Exception as exc:
                st.error(f"Strateji çalıştırılamadı: {exc}")
                poz = None
            if poz is not None:
                a_ayarlar = {"baslangic_bakiye": 1000.0, "islem_ucreti_yuzde": 0.1, "islem_orani": 0.95}
                sonuc = simule_et(df_analiz, poz, a_ayarlar, baslangic=min(isinma, len(df_analiz) - 2),
                                  detay_don=True)
                if sonuc is None:
                    st.warning("Bu ayarlarla simülasyon sonucu üretilemedi.")
                else:
                    m = st.columns(5)
                    with m[0]:
                        st.metric("Getiri", f"{sonuc['getiri']:+.1f}%")
                    with m[1]:
                        st.metric("Al-tut getirisi", f"{sonuc['al_tut_getiri']:+.1f}%")
                    with m[2]:
                        st.metric("En büyük düşüş", f"{sonuc['dusus']:.1f}%")
                    with m[3]:
                        st.metric("İşlem sayısı", f"{sonuc['tur']}")
                    with m[4]:
                        st.metric("Kazanma oranı", f"{sonuc['kazanma']:.0f}%" if sonuc["tur"] else "—")

                    egri_df = pd.DataFrame({"Zaman": sonuc["zamanlar"], "Portföy değeri": sonuc["seri"]})
                    st.line_chart(egri_df.set_index("Zaman"))

                    if sonuc["islemler"]:
                        islem_df = pd.DataFrame(sonuc["islemler"]).rename(columns={
                            "zaman": "Giriş zamanı", "fiyat": "Giriş fiyatı", "yon": "Yön",
                            "cikis_zaman": "Çıkış zamanı", "cikis_fiyat": "Çıkış fiyatı",
                            "getiri_yuzde": "Getiri %",
                        })
                        st.dataframe(
                            islem_df.sort_values("Giriş zamanı", ascending=False),
                            width="stretch", hide_index=True,
                            column_config={
                                "Giriş fiyatı": st.column_config.NumberColumn(format="%.6g"),
                                "Çıkış fiyatı": st.column_config.NumberColumn(format="%.6g"),
                                "Getiri %": st.column_config.NumberColumn(format="%+.2f%%"),
                            })
                    else:
                        st.info("Seçilen dönemde bu strateji hiç işlem tetiklemedi.")


# ============================================================
#  SANAL TRADER  (coklu strateji, otomatik rotasyon)
# ============================================================
#
# BU SAYFA sanal_trader.py'yi CALISTIRMAZ -- o, uygulamadan BAGIMSIZ,
# ayri bir arka plan sureci olarak calisir (calistir_sanal_trader.bat).
# Burasi SADECE onun yazdigi dosyalari (cikti/sanal_trader/ altinda)
# okuyup gosterir.
#
# ONEMLI -- IKI YOL DA DENENDI, IKISI DE OTOMATIK YENILEMEYI BOZDU:
#   1. AYRI bir @st.fragment(run_every=20): sayfa degistirince navigasyon
#      tikandi (dosyanin basindaki "TEK CANLI PARCA" bolumundeki 1. yanlis
#      yolla ayni hata -- sayfa basina ayri bir zamanlayici, eskisiyle catisiyor).
#   2. TEK, SABIT canli_bolum() parcasina bir dal olarak eklemek (o
#      bolumun kendi "DOGRU YOL" tarifi): bu sefer de sayfa gecisi
#      TIKANDI -- WebSocket mesaj sayaci bile durdu, yani saniyede bir
#      tetiklenen bu parcaya (grafik + tablo yeniden cizimi + agdan
#      gecmis fiyat cekme gibi) agir is koymak, TUM uygulamanin saniyelik
#      dongusunu tikiyor.
# SONUC: bu sayfa BILEREK STATIK -- Analiz Botu/Haberler gibi, sadece
# navigasyonla veya asagidaki "Yenile" dugmesiyle tazelenir. "Canli"
# olan kisim, saniyede bir TETIKLENMESI degil, VERININ kendisinin
# (asagidaki _sanal_trader_egri_verisi) surekli/saatlik cozunurlukte
# olmasi ve metriklerin HER YENILEMEDE guncel canli fiyati kullanmasi.
#
# CANLI GRAFIK: asagidaki _sanal_trader_egri_verisi, islemler.csv'deki
# "her islemden SONRAKI islege kadar (nakit, coin, sembol) SABIT kaldi"
# bilgisini, o araliktaki coinin SAATLIK kapanis fiyatlariyla carpip
# SUREKLI bir deger serisine cevirir -- sadece islem anlarini birlestiren
# eski (seyrek) cizginin yerini alir. c_mumlar zaten 5 dk onbellekli
# oldugu icin bu hesap sayfa her yenilendiginde agir bir ag yuku
# getirmez.

def _pozisyon_degeri(poz, fiyat):
    """
    Bir pozisyonun (LONG ya da SHORT, spot ya da kaldiracli) o anki
    fiyatla degerini hesaplar -- sanal_trader.py'nin Portfoy.toplam_
    deger()'iyle AYNI mantik. Spot LONG icin miktar*fiyat (degismedi);
    SHORT ve/ya kaldiracli pozisyonlar icin o an kapatilsa donecek nakit
    (maliyet +/- kaldiracla buyutulmus gerceklesmemis kar/zarar,
    SIFIRIN ALTINA dusmez -- likidasyonla tutarli).
    """
    if fiyat is None:
        return 0.0
    yon = poz.get("yon", "LONG")
    kaldirac = poz.get("kaldirac", 1.0) or 1.0
    giris = poz.get("giris_fiyat") or fiyat
    maliyet = poz.get("maliyet") or (poz["miktar"] * giris / kaldirac)

    if kaldirac > 1.0:
        if yon == "SHORT":
            kar_zarar = maliyet * kaldirac * (giris - fiyat) / giris if giris else 0.0
        else:
            kar_zarar = maliyet * kaldirac * (fiyat / giris - 1) if giris else 0.0
        return max(0.0, maliyet + kar_zarar)
    if yon == "SHORT":
        kar_zarar = maliyet * (giris - fiyat) / giris if giris else 0.0
        return maliyet + kar_zarar
    return poz["miktar"] * fiyat


def _sanal_trader_egri_verisi(islemler):
    """
    islemler.csv'yi (her satir bir TAM acilis ya da TAM kapanis --
    sanal_trader.py'nin Portfoy sinifi hep tum pozisyonu acar/kapatir)
    baştan sona "oynatarak" her andaki (nakit, {sembol: pozisyon}) durumunu
    cikarir, sonra o araliktaki HER tutulan sembolun SAATLIK kapanis
    fiyatiyla degerini (_pozisyon_degeri -- LONG/SHORT'a gore) toplayarak
    SUREKLI, COKLU-POZISYONU DOGRU YANSITAN bir portfoy degeri serisi
    uretir.
    """
    if islemler is None or islemler.empty:
        return None
    df = islemler.copy()
    df["tarih"] = pd.to_datetime(df["tarih"]).dt.tz_localize("UTC")
    df = df.sort_values("tarih").reset_index(drop=True)

    semboller = sorted(df["sembol"].unique())
    fiyat_serileri = {}
    simdi = pd.Timestamp.now(tz="UTC")
    for sembol in semboller:
        gun_farki = max((simdi - df["tarih"].min()).days + 2, 5)
        adet = min(24 * gun_farki, 990)
        mumlar = c_mumlar(sembol, "1h", int(adet))
        if mumlar is not None and len(mumlar):
            fiyat_serileri[sembol] = mumlar.set_index("zaman")["kapanis"]

    def _fiyat_bul(sembol, zaman):
        seri = fiyat_serileri.get(sembol)
        if seri is None:
            return None
        alt_kume = seri[seri.index <= zaman]
        return float(alt_kume.iloc[-1]) if len(alt_kume) else None

    zamanlar, degerler = [], []
    pozisyonlar = {}  # sembol -> {"miktar","yon","giris_fiyat","maliyet"} (bu satirdan itibaren gecerli)

    for i in range(len(df)):
        baslangic = df["tarih"].iloc[i]
        bitis = df["tarih"].iloc[i + 1] if i + 1 < len(df) else simdi
        satir = df.iloc[i]
        nakit = float(satir["nakit"])

        kaldirac_deger = float(satir["kaldirac"]) if "kaldirac" in satir and pd.notna(satir.get("kaldirac")) else 1.0
        if satir["islem"] == "AL":
            pozisyonlar[satir["sembol"]] = {"miktar": float(satir["miktar"]), "yon": "LONG",
                                            "giris_fiyat": float(satir["fiyat"]), "maliyet": float(satir["tutar"]),
                                            "kaldirac": kaldirac_deger}
        elif satir["islem"] == "KISA_AC":
            pozisyonlar[satir["sembol"]] = {"miktar": float(satir["miktar"]), "yon": "SHORT",
                                            "giris_fiyat": float(satir["fiyat"]), "maliyet": float(satir["tutar"]),
                                            "kaldirac": kaldirac_deger}
        elif str(satir["islem"]) in ("SAT", "KISA_KAPAT", "LIKIDASYON"):
            pozisyonlar.pop(satir["sembol"], None)

        if not pozisyonlar:
            zamanlar += [baslangic, bitis]
            degerler += [nakit, nakit]
            continue

        # bu segmentte tutulan butun sembollerin fiyat zaman noktalarini birlestir
        segment_zamanlari = set()
        for sembol in pozisyonlar:
            seri = fiyat_serileri.get(sembol)
            if seri is None:
                continue
            dilim = seri[(seri.index >= baslangic) & (seri.index <= bitis)]
            segment_zamanlari.update(dilim.index)

        if not segment_zamanlari:
            deger = nakit
            for sembol, poz in pozisyonlar.items():
                fiyat = (float(satir["fiyat"]) if sembol == satir["sembol"]
                        else _fiyat_bul(sembol, baslangic))
                deger += _pozisyon_degeri(poz, fiyat)
            zamanlar.append(baslangic)
            degerler.append(deger)
            continue

        for zaman in sorted(segment_zamanlari):
            deger = nakit
            for sembol, poz in pozisyonlar.items():
                fiyat = _fiyat_bul(sembol, zaman)
                deger += _pozisyon_degeri(poz, fiyat)
            zamanlar.append(zaman)
            degerler.append(deger)

    return pd.DataFrame({"zaman": zamanlar, "deger": degerler}).sort_values("zaman")


def _sanal_trader_bulut_ile_senkronize_et():
    """
    GitHub Actions BULUTTA (bilgisayarınız kapalıyken de) çalışıp
    sonuçları `git commit` ile depoya yazıyor -- ama bu YEREL kopya
    o değişiklikleri kendiliğinden GÖRMEZ, "git pull" çalıştırılması
    gerekir. Kullanıcının yaşadığı "bilgisayarı kapatınca işlemler
    gidiyor" hissi aslında budur: işlemler kaybolmuyor, sadece bulutta
    -- yerel panel onlardan habersiz kalıyor. Bu düğme o boşluğu kapatır.
    """
    try:
        sonuc = subprocess.run(
            ["git", "pull", "--ff-only"], cwd=strd.KLASOR,
            capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        st.error("Git bulunamadı -- bu bilgisayarda git kurulu olmayabilir.")
        return
    except Exception as e:
        st.error(f"Senkronize edilemedi: {e}")
        return

    if sonuc.returncode == 0:
        # BILEREK st.rerun() YOK: bu fonksiyon _sanal_trader_icerik'in
        # EN BASINDA cagriliyor, dosyalar disk uzerinde zaten guncellendi
        # -- fonksiyonun devami (asagidaki okumalar) AYNI calisma
        # icinde zaten TAZE veriyi okuyacak. st.rerun() cagirmak, bu
        # basari mesajini goruntulenmeden hemen silerdi.
        cikti = sonuc.stdout.strip()
        if "Already up to date" in cikti or "zaten güncel" in cikti.lower():
            st.success("Zaten güncel — bulutta yeni bir şey yok.")
        else:
            st.success("Bulutla senkronize edildi, en güncel sonuçlar aşağıda.")
    else:
        st.error(
            "Senkronize edilemedi -- muhtemelen bu klasör GitHub'a "
            "bağlı bir git deposu değil, ya da yerel değişiklikler "
            "çakışıyor.\n\n" + (sonuc.stderr.strip() or ""))


def _sanal_trader_ilk_calisma_durumu():
    """
    DURUM_DOSYASI henuz yokken gosterilir. Ilk rotasyon (40 coin x 19
    strateji taramasi) birkac dakika surer -- bu sure boyunca eskiden
    burada duz bir "henuz calismadi" yazisi vardi, kullanici bot.py'yi
    baslatip birkac dakika bekledikten sonra bile ayni yaziyi gorunce
    "calismiyor" saniyordu. Simdi sanal_trader.py'nin yazdigi GECICI
    calisma_durumu.json'u okuyup GERCEK ilerlemeyi gosteriyoruz.
    """
    if not strd.CALISMA_DOSYASI.exists():
        st.info(
            "Sanal trader henüz çalışmadı. Başlatmak için klasördeki "
            "**calistir_sanal_trader.bat** dosyasına çift tıklayın — "
            "bilgisayar açıkken arka planda 7/24 çalışır, bu sayfa onun "
            "kararlarını gösterir.")
        return

    try:
        calisma = json.loads(strd.CALISMA_DOSYASI.read_text(encoding="utf-8"))
        guncelleme = datetime.fromisoformat(calisma["guncelleme"])
        eskilik_saniye = (datetime.now(timezone.utc) - guncelleme).total_seconds()
    except Exception:
        st.info("Sanal trader başlatılıyor, birazdan burada görünecek…")
        return

    if eskilik_saniye > 600:
        st.warning(
            "Bir tarama başlamıştı ama 10 dakikadan uzun süredir "
            "ilerlemiyor — süreç yarıda kesilmiş olabilir (bilgisayar "
            "uykuya geçti, konsol kapatıldı vb.). **calistir_sanal_"
            "trader.bat**'ı tekrar çalıştırmayı deneyin.")
        return

    ilerleme, toplam = calisma.get("ilerleme", 0), calisma.get("toplam", 1)
    st.info(
        f"**İlk tarama sürüyor** — {ilerleme}/{toplam} coin test edildi. "
        "Bu, evrendeki her coin için tüm stratejileri geçmiş veriyle "
        "ölçtüğü için birkaç dakika sürer (tek seferlik bir bekleme — "
        "sonraki rotasyonlar bu kadar sürmez, aynı anda sadece o an açık "
        "olan pozisyonlar kontrol edilir). Bu sayfayı birkaç dakika sonra "
        "yeniden açın ya da aşağıdaki düğmeyle şimdi kontrol edin.")
    st.progress(ilerleme / toplam if toplam else 0.0)
    if st.button("Yenile", key="sanal_trader_ilk_yenile"):
        st.rerun()


def _sanal_trader_icerik(depo):
    """
    Statik routing'den cagirilir (bkz. dosyanin yukarisindaki uzun not --
    saniyede bir tetiklenen bir parcaya konunca navigasyonu tikiyordu).
    _yavas_yenile burada artik navigasyon icin degil, "Yenile" dugmesine
    art arda basilirsa gereksiz agir hesap tekrarlanmasin diye kaldi.
    """
    st.markdown('<div class="bolum-basligi">Sanal Trader</div>', unsafe_allow_html=True)
    st.warning(
        "**Bu bot da tavsiye vermez, gerçek para kullanmaz.** Likit bir "
        "coin evreninde (BTC/ETH dahil, altcoinler de dahil — en az "
        "$5M 24s hacimli en likit 40 coin, `sanal_trader.py` AYARLAR'dan "
        "değiştirilebilir) AYNI ANDA birden fazla pozisyon tutabilir "
        "(en fazla 8) — her coin kendi 'en iyi' stratejisiyle (16 klasik "
        "+ SFP/Order Block/Fair Value Gap/Destek-Direnç kırılması) "
        "SAATLİK mumlarla izlenir, TAMAMEN SANAL bir portföyle işlem "
        "yapılır. **Dürüstlük notu:** yeni desenlerin hiçbiri (SFP, "
        "Order Block, Fair Value Gap, Destek/Direnç kırılması), mevcut "
        "16 stratejide olduğu gibi, rastgele kontrol grubunu istatistiksel "
        "olarak geçemedi — bu test GÜNLÜK mumlarla yapıldı (bkz. "
        "README.md); saatlik mumlarla ayrıca doğrulanmadı, bu bilinen bir "
        "sınırlamadır. 'En iyi performans gösteren'in seçilmesi, o "
        "stratejinin gelecekte de iyi gideceğinin garantisi DEĞİLDİR — "
        "yakın geçmişte iyi gideni kovalama riski taşır. Bu bir kâr aracı "
        "değil, şeffaf bir gözlem aracıdır.  \n\n"
        "**Kaldıraç (2026-09-12):** YENİ açılan pozisyonlar artık spot değil, "
        "**5x-10x arası dinamik kaldıraçlı** — kaldıraç, ATR'a (oynaklığa) "
        "göre otomatik belirlenir (dar/öngörülen stop → yüksek kaldıraç, "
        "geniş/öngörülen stop → düşük kaldıraç, her zaman bu aralığa "
        "sıkıştırılır). **LİKİDASYON gerçek gibi modellenir**: marjinin "
        "tamamı bir pozisyonda kaybedilebilir (o pozisyon için en fazla "
        "kaybedilen tutar, ona ayrılan marjinle sınırlıdır — negatif bakiye "
        "olmaz). Değişikliğin öncesinde açılmış pozisyonlar spot kalmaya "
        "devam eder, doğal kapanışlarını bekler.")

    ust = st.columns([5, 2])
    with ust[0]:
        st.caption(
            "🌐 **7/24 çalışan asıl sistem GitHub Actions'ta** (bilgisayarınız "
            "kapalıyken de saatte bir çalışır). Bu panel ise **yerel bir "
            "kopyayı** gösterir — bulutta olanları görmek için sağdaki "
            "düğmeyle senkronize edin. `calistir_sanal_trader.bat`'ı AYRICA "
            "çalıştırırsanız bu, buluttakinden **bağımsız, ayrı bir "
            "portföy** oluşturur — ikisini birden çalıştırmayın, karışır.")
    with ust[1]:
        if st.button("☁️ Bulutla senkronize et", key="sanal_trader_senkronize",
                     width="stretch"):
            _sanal_trader_bulut_ile_senkronize_et()

    if not strd.DURUM_DOSYASI.exists():
        _sanal_trader_ilk_calisma_durumu()
        return

    try:
        durum = json.loads(strd.DURUM_DOSYASI.read_text(encoding="utf-8"))
    except Exception:
        st.warning("Durum dosyası okunamadı — sanal trader bir sonraki turda düzeltecektir.")
        return

    portfoy_verisi = None
    if strd.PORTFOY_DOSYASI.exists():
        try:
            portfoy_verisi = json.loads(strd.PORTFOY_DOSYASI.read_text(encoding="utf-8"))
        except Exception:
            pass

    pozisyonlar = {}
    if strd.POZISYON_DOSYASI.exists():
        try:
            pozisyonlar = json.loads(strd.POZISYON_DOSYASI.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Her acik pozisyon icin GUNCEL (canli, bu uygulamanin kendi WebSocket
    # baglantisindan) fiyati topla -- sanal_trader.py'nin kendi surecinden
    # BAGIMSIZ, o yuzden burasi "gerceten canli" kalir.
    guncel_fiyatlar = {s: al(depo.coin(s), "fiyat") for s in pozisyonlar}

    toplam_deger = kar_yuzde = None
    if portfoy_verisi:
        toplam_deger = portfoy_verisi["nakit"]
        for sembol, poz in pozisyonlar.items():
            # _pozisyon_degeri: LONG/SHORT + spot/kaldiracli HEPSINI kapsar,
            # sanal_trader.py'nin Portfoy.toplam_deger()'iyle AYNI mantik.
            toplam_deger += _pozisyon_degeri(poz, guncel_fiyatlar.get(sembol))
        if portfoy_verisi.get("baslangic"):
            kar_yuzde = (toplam_deger / portfoy_verisi["baslangic"] - 1) * 100

    st.markdown(canli_gosterge(depo), unsafe_allow_html=True)
    s = st.columns(5)
    with s[0]:
        st.metric("Açık pozisyon", f"{len(pozisyonlar)}")
    with s[1]:
        st.metric("İzlenen coin (evren)", f"{len(durum.get('pozisyon_stratejileri', {}))}")
    with s[2]:
        st.metric("Toplam portföy değeri",
                  fiyat_yaz(toplam_deger) if toplam_deger is not None else "—",
                  yuzde(kar_yuzde) if kar_yuzde is not None else None)
    with s[3]:
        st.metric("Nakit", fiyat_yaz(portfoy_verisi["nakit"]) if portfoy_verisi else "—")
    with s[4]:
        try:
            son_rotasyon = datetime.fromisoformat(durum["son_rotasyon"])
            st.metric("Son rotasyon", f"{son_rotasyon:%d.%m %H:%M}")
        except Exception:
            st.metric("Son rotasyon", "—")

    # --- Acik pozisyonlar tablosu ------------------------------
    if pozisyonlar:
        st.markdown('<div class="bolum-basligi" style="margin-top:14px;">'
                    'Şu an açık pozisyonlar</div>', unsafe_allow_html=True)
        satirlar = []
        for sembol, poz in pozisyonlar.items():
            guncel = guncel_fiyatlar.get(sembol)
            yon = poz.get("yon", "LONG")
            kaldirac = poz.get("kaldirac", 1.0) or 1.0
            if guncel and poz.get("giris_fiyat"):
                # SHORT'ta kar/zarar YONU ters -- fiyat DUSTUKCE kazanc.
                # Kaldiracli pozisyonlarda fiyat hareketi kaldirac KATI buyutulur.
                temel = ((poz["giris_fiyat"] / guncel - 1) * 100) if yon == "SHORT" \
                    else ((guncel / poz["giris_fiyat"] - 1) * 100)
                kar = max(-100.0, temel * kaldirac)  # likidasyonda -%100'un altina inmez
            else:
                kar = None
            satirlar.append({
                "Coin": sembol.split("/")[0], "Yön": "🔴 SHORT" if yon == "SHORT" else "🟢 LONG",
                "Kaldıraç": "Spot" if kaldirac <= 1.0 else f"{kaldirac:.1f}x",
                "Strateji": poz["strateji"],
                "Giriş fiyatı": poz["giris_fiyat"], "Güncel fiyat": guncel,
                "Kâr/zarar %": kar, "Miktar": poz["miktar"],
                "Giriş zamanı": poz["giris_zamani"][:16].replace("T", " "),
            })
        pozisyon_df = pd.DataFrame(satirlar).sort_values("Kâr/zarar %", ascending=False)
        st.dataframe(pozisyon_df, width="stretch", hide_index=True,
                    column_config={
                        "Giriş fiyatı": st.column_config.NumberColumn(format="%.6g"),
                        "Güncel fiyat": st.column_config.NumberColumn(format="%.6g"),
                        "Kâr/zarar %": st.column_config.NumberColumn(format="%+.2f%%"),
                        "Miktar": st.column_config.NumberColumn(format="%.6g"),
                    })
    else:
        st.info("Şu an açık pozisyon yok — atanmış stratejilerin sinyal vermesi bekleniyor.")

    islemler = pd.read_csv(strd.ISLEM_DOSYASI) if strd.ISLEM_DOSYASI.exists() else pd.DataFrame()

    if not islemler.empty:
        st.markdown('<div class="bolum-basligi" style="margin-top:14px;">'
                    'Portföy değeri (canlı, sürekli)</div>', unsafe_allow_html=True)
        egri = _yavas_yenile("sanal_trader_egri", lambda: _sanal_trader_egri_verisi(islemler),
                             saniye=15)
        f = gr.sanal_trader_egrisi(
            egri, islemler, portfoy_verisi["baslangic"] if portfoy_verisi else 1000.0)
        if f:
            st.plotly_chart(f, width="stretch", config=gr.PLOTLY_AYARLARI, key="sanal_trader_pnl")
        st.caption("▲ yeşil üçgen: alım anı · ▼ kırmızı üçgen: satım anı · çizgi, AYNI ANDA "
                   "tutulan TÜM pozisyonların SAATLİK fiyatlarından hesaplanan sürekli toplam "
                   "değer — mum grafiği gibi günlük değil, gerçekten sürekli bir eğridir.")

        st.markdown('<div class="bolum-basligi" style="margin-top:14px;">İşlem geçmişi</div>',
                    unsafe_allow_html=True)
        st.caption("Her satır: ne zaman, hangi stratejinin sinyaliyle, hangi coin'den "
                   "aldı/sattı, kârla mı zararla mı kapandı — hepsi burada.")
        st.dataframe(islemler.sort_values("tarih", ascending=False), width="stretch", hide_index=True,
                    column_config={
                        "kar_zarar": st.column_config.NumberColumn("Kâr/zarar $", format="%+.2f"),
                        "kar_zarar_yuzde": st.column_config.NumberColumn("Kâr/zarar %", format="%+.2f%%"),
                    })

        # --- Strateji performans ozeti (SADECE kapanan islemler) ----
        # NOT (2026-09-12 duzeltmesi): SHORT destegi eklendiginde "KISA_KAPAT"
        # (kisa pozisyon kapanisi) ve likidasyon destegi eklendiginde
        # "LIKIDASYON" da birer KAPANIS turu oldu -- sadece "SAT" (LONG
        # kapanisi) filtrelemek bu ikisini SESSIZCE ozetten dislardi.
        kapanan = islemler[islemler["islem"].astype(str).isin(["SAT", "KISA_KAPAT", "LIKIDASYON"])].copy()
        if "kar_zarar" in kapanan.columns:
            kapanan["kar_zarar"] = pd.to_numeric(kapanan["kar_zarar"], errors="coerce")
            kapanan["kar_zarar_yuzde"] = pd.to_numeric(kapanan.get("kar_zarar_yuzde"), errors="coerce")
            kapanan = kapanan.dropna(subset=["kar_zarar"])
        else:
            kapanan = kapanan.iloc[0:0]  # eski (kar_zarar sutunu olmayan) islem gecmisi -- gosterilecek bir sey yok

        if not kapanan.empty:
            st.markdown('<div class="bolum-basligi" style="margin-top:14px;">'
                        'Strateji performansı (kapanan işlemler)</div>', unsafe_allow_html=True)
            st.caption(
                "Her stratejinin ŞİMDİYE KADAR KAPATTIĞI işlemlerin özeti — hangisi ne "
                "sıklıkla kârla/zararla kapanmış, ortalama getirisi ne. **Az sayıda işlemle "
                "(1-2 gibi) çıkan bir sonuç güvenilir değildir** — birkaç işlemlik bir "
                "örneklem şans eseri de olabilir, tıpkı `tarama.py`'de anlattığımız gibi.")
            ozet = (kapanan.groupby("strateji")
                   .agg(kapanan_islem=("kar_zarar", "count"),
                        kazanan=("kar_zarar", lambda s: int((s > 0).sum())),
                        ortalama_yuzde=("kar_zarar_yuzde", "mean"),
                        toplam=("kar_zarar", "sum"))
                   .reset_index())
            ozet["kazanma_orani"] = ozet["kazanan"] / ozet["kapanan_islem"] * 100
            ozet = ozet.sort_values("toplam", ascending=False)
            ozet = ozet.rename(columns={
                "strateji": "Strateji", "kapanan_islem": "Kapanan işlem",
                "kazanan": "Kazanan", "kazanma_orani": "Kazanma oranı %",
                "ortalama_yuzde": "Ort. getiri %", "toplam": "Toplam kâr/zarar $",
            })
            st.dataframe(
                ozet[["Strateji", "Kapanan işlem", "Kazanan", "Kazanma oranı %",
                     "Ort. getiri %", "Toplam kâr/zarar $"]],
                width="stretch", hide_index=True,
                column_config={
                    "Kazanma oranı %": st.column_config.NumberColumn(format="%.0f%%"),
                    "Ort. getiri %": st.column_config.NumberColumn(format="%+.2f%%"),
                    "Toplam kâr/zarar $": st.column_config.NumberColumn(format="%+.2f"),
                })
    else:
        st.info("Henüz hiç sanal işlem yapılmadı — atanmış stratejilerin sinyal vermesi bekleniyor.")

    if strd.ROTASYON_DOSYASI.exists():
        rotasyonlar = pd.read_csv(strd.ROTASYON_DOSYASI)
        if not rotasyonlar.empty:
            st.markdown('<div class="bolum-basligi" style="margin-top:14px;">Rotasyon geçmişi</div>',
                        unsafe_allow_html=True)
            st.caption("Her rotasyonda HER coin için test edilen en iyi 5 strateji ve "
                       "neden seçildiği — şeffaflık için, hangi kararın neden verildiği "
                       "her zaman görünür.")
            st.dataframe(rotasyonlar.sort_values("tarih", ascending=False), width="stretch",
                        hide_index=True)

    if st.button("Yenile", key="sanal_trader_yenile",
                 help="Dosyaları ve güncel fiyatları yeniden okur."):
        st.rerun()


# ============================================================
#  KENAR CUBUGU VE YONLENDIRME
# ============================================================

if "sayfa" not in st.session_state:
    st.session_state.sayfa = "Piyasa"
if "secili_coin" not in st.session_state:
    st.session_state.secili_coin = "BTC/USDT"
if "anlik" not in st.session_state:
    st.session_state.anlik = True
if "aralik" not in st.session_state:
    st.session_state.aralik = 1

depo = canli()

with st.sidebar:
    st.markdown(
        '<div class="kt-brand" style="margin-bottom:2px;">'
        '<i class="ti ti-chart-candle"></i> kaan-trade'
        '<span class="kt-brand-sub">Ayarlar</span></div>',
        unsafe_allow_html=True)
    st.markdown("")

    # --- Coin secici: her sayfadan erisilebilir olsun ---
    st.markdown('<div class="kt-side-label"><i class="ti ti-search"></i> '
               'Coin ara ve seç</div>', unsafe_allow_html=True)
    _semboller = depo.semboller(0)
    if _semboller:
        _secili = st.session_state.secili_coin
        if _secili not in _semboller:
            _semboller = sorted(set(_semboller + [_secili]))
        st.session_state.secili_coin = st.selectbox(
            "Coin ara ve seç", _semboller, index=_semboller.index(_secili),
            key="coin_secici", label_visibility="collapsed",
            help="Yazmaya başlayın, liste süzülür. Seçtiğiniz coin "
                 "'Coin analizi' sayfasında gösterilir.")
    else:
        st.caption("Coin listesi yükleniyor…")

    st.markdown("---")
    st.markdown('<div class="kt-side-label"><i class="ti ti-bolt"></i> '
               'Canlılık ve süzgeç</div>', unsafe_allow_html=True)
    st.session_state.anlik = st.toggle(
        "Anlık güncelleme", value=st.session_state.anlik,
        help="Açıkken ekran sürekli kendini yeniler. Veri hafızadan "
             "okunur (WebSocket ile geliyor), internete tekrar gidilmez.")
    st.session_state.aralik = st.select_slider(
        "Yenileme aralığı", options=[1, 2, 3, 5], value=st.session_state.aralik,
        format_func=lambda x: f"{x} saniye",
        help="1 saniye en canlı görünümü verir ama bilgisayarı en çok "
             "yorar. Yavaş bir bilgisayarda 2-3 saniye daha akıcı olur.")

    hacim_secim = st.select_slider(
        "En az 24s hacim",
        options=["Süzgeç yok", "100 B $", "1 M $", "10 M $", "100 M $"],
        value="1 M $",
        help="Düşük hacimli coinlerde fiyat güvenilmezdir: tek bir küçük "
             "emir fiyatı %50 oynatabilir. Bu süzgeç onları listeden çıkarır.")
    en_az_hacim = {"Süzgeç yok": 0, "100 B $": 1e5, "1 M $": 1e6,
                   "10 M $": 1e7, "100 M $": 1e8}[hacim_secim]

    st.markdown("---")
    o = depo.ozet()
    st.markdown('<div class="kt-side-label"><i class="ti ti-plug-connected"></i> '
               'Bağlantı durumu</div>', unsafe_allow_html=True)
    st.caption(
        f"Kaynak: {o.get('kaynak') or '—'}\n\n"
        f"Alınan mesaj: {o.get('mesaj_sayisi', 0):,}\n\n"
        f"İzlenen coin: {o.get('sembol_sayisi', 0):,}")
    if o.get("hata"):
        st.caption(f"⚠️ {o['hata']}")

    st.markdown("---")
    st.markdown('<div class="kt-side-label"><i class="ti ti-database"></i> '
               'Veri kaynakları</div>', unsafe_allow_html=True)
    st.caption("• Binance WebSocket — anlık fiyat (saniyede bir)\n\n"
               "• Binance REST — mum verisi, emir defteri\n\n"
               "• Binance vadeli — fonlama, açık pozisyon\n\n"
               "• CoinGecko — piyasa değeri, hakimiyet (2 dk)\n\n"
               "• alternative.me — Korku endeksi (günlük)\n\n"
               "Hepsi ücretsiz, API anahtarı gerekmez.")

    st.markdown("---")
    st.markdown('<div class="kt-side-label"><i class="ti ti-info-circle"></i> '
               'Bu panel ne yapmaz</div>', unsafe_allow_html=True)
    st.caption("Fiyatın nereye gideceğini söylemez, al/sat tavsiyesi vermez. "
               "Test ettiğimiz 16 standart göstergenin hiçbiri geleceği "
               "bilemedi — ayrıntısı README.md içinde.")


# ============================================================
#  UST NAVBAR  (marka + sayfa sekmeleri + canli rozet)
# ============================================================
#
# Sayfa secimi BILEREK asagidaki canli parcanin (fragment) DISINDA.
# Daha once bunu kenar cubugunda da, ana alanda da denedik; onemli
# olan konumu degil, fragment'in disinda kalmasi -- aksi halde
# otomatik yenileme ile sayfa tiklamasi yarisiyor (bkz. asagidaki not).

nav = st.columns([2, 5, 2], vertical_alignment="center")
with nav[0]:
    st.markdown('<div class="kt-brand"><i class="ti ti-chart-candle"></i>kaan-trade</div>',
               unsafe_allow_html=True)
with nav[1]:
    SAYFALAR = ["Piyasa", "Coin analizi", "Analiz Botu", "Sanal Trader",
               "Karşılaştırma", "Haberler", "Trade Ajanı"]
    st.session_state.sayfa = st.radio(
        "Sayfa", SAYFALAR, index=SAYFALAR.index(st.session_state.sayfa),
        label_visibility="collapsed", horizontal=True)
with nav[2]:
    st.markdown(f'<div style="text-align:right; padding-top:6px">'
               f'{canli_gosterge(depo)}</div>', unsafe_allow_html=True)
st.markdown('<div style="border-bottom:1px solid var(--kt-border); margin:8px 0 4px 0;"></div>',
           unsafe_allow_html=True)


# ============================================================
#  TEK CANLI PARCA
# ============================================================
#
# BURAYA NASIL GELDIK (uc yanlis yol denedik):
#
#   1. Sayfa basina ayri "kendini yenileyen parca" (fragment).
#      Sorun: sayfa degistirilince eski parcanin zamanlayicisi calismaya
#      devam edip kendini yeniden ciziyordu -- iki sayfa ust uste bindi.
#
#   2. time.sleep + st.rerun -- sonsuz dongu.
#      Sorun: Streamlit ekrandaki eski ogeleri ANCAK betik duzgun
#      bittiginde temizliyor. Dongu betigi hic bitirmedigi icin ayni
#      kalinti sorunu surdu.
#
#   3. streamlit-autorefresh ile TUM SAYFAYI yeniden calistirmak.
#      Sorun: otomatik yenileme, kenar cubugundaki sayfa/coin secimiyle
#      YARISTI -- bazen tikladiginiz sayfa aninda eski sayfaya geri
#      donuyordu, cunku ayni anda iki farkli "yeniden calistir" istegi
#      sunucuya gidiyordu.
#
#   4. DOGRU YOL: TEK, SABIT bir parca -- @st.fragment ile bir kez
#      TANIMLANIR (satir icinde sarmalanmaz) ve HER SAYFADA COKAGILIR.
#      Icerigi hangi sayfada oldugumuza gore degisir ama parcanin
#      KENDISI hep aynidir, o yuzden "sahipsiz kalan eski parca" sorunu
#      olusmaz. Kenar cubugundaki sayfa/coin secimi bu parcanin
#      DISINDA oldugu icin normal (tam) bir yeniden calistirma yapar
#      ve yarisma ihtimali kalmaz.
#
#   Ayrica: agir kisimlar (mum grafigi, korelasyon haritasi, CoinGecko
#   sorgulari) BILEREK bu parcanin DISINDA tutuluyor. Onlar saniyede
#   bir yeniden cizilmeye ihtiyac duymaz -- gunluk mumdan hesaplanan
#   RSI saniyede degismez. Sadece siz bir sey degistirdiginizde
#   (coin, zaman dilimi...) yenilenirler. Boylece "anlik" olmasi
#   gereken sadece fiyat/ozet kisimlari saniyede bir yenilenir, agir
#   grafikler gereksiz yere tekrar tekrar gonderilmez.

_yenileme = st.session_state.aralik if st.session_state.anlik else None


@st.fragment(run_every=_yenileme)
def canli_bolum():
    ticker_serit(depo)
    sayfa = st.session_state.sayfa
    if sayfa == "Piyasa":
        sayfa_piyasa_canli(depo, en_az_hacim)
    elif sayfa == "Coin analizi":
        canli_fiyat_basligi(depo, st.session_state.secili_coin)
        # Grafik HER ZAMAN burada (saniyede bir yenilenen bolumde)
        # cizilir. "Canli tut" anahtari KAPALIYKEN bile boyle -- ama
        # o zaman grafik_kontrolleri() canli_fiyat=None geciyor, boylece
        # ayni ayarlarla uretilen figur HER SEFERINDE AYNI oluyor ve
        # Streamlit onu tekrar tekrar gondermiyor (bkz. grafik_kontrolleri
        # icindeki not). Sonuc: ekranda cizim yaptiginiz sekiller kalir.
        coin_grafik_bolumu(depo, st.session_state.secili_coin)
    elif sayfa == "Karşılaştırma":
        kars_canli_serit(depo)
    # Haberler ve Analiz Botu sayfalarinin canli/saniyelik bir kismi yok --
    # haberler 5 dakikada, analiz botu gunluk mumlarla calisir, saniyede
    # bir yenilemenin anlami olmaz. SANAL TRADER de AYNI sebeple burada
    # DEGIL -- ONCE denedik ama saniyede bir tetiklenen bu fragment'e
    # agir isi (grafik + tablo yeniden cizimi) koyunca sayfa gecisi
    # TIKANDI, dosyanin en basindaki "yanlis yol 1" ornegindeki gibi
    # (bkz. asagidaki _sanal_trader_icerik'in basindaki not). Bunun
    # yerine Analiz Botu/Haberler gibi statik kaldi, elle "Yenile"
    # dugmesiyle tazeleniyor.


canli_bolum()

# --- Yavas degisen kisimlar: parcanin DISINDA, sadece etkilesimle yenilenir
# (arama kutusu, korelasyon, haberler -- hicbiri saniyede bir yeniden
# cizilmeye ihtiyac duymuyor, bkz. yukaridaki notlar. Mum grafigi ARTIK
# BURADA DEGIL, canli_bolum icinde -- bkz. yukaridaki not.)
if st.session_state.sayfa == "Piyasa":
    sayfa_piyasa_tablo(depo, en_az_hacim)
elif st.session_state.sayfa == "Coin analizi":
    coin_statik(depo, st.session_state.secili_coin)
elif st.session_state.sayfa == "Analiz Botu":
    sayfa_analiz_botu(depo, st.session_state.secili_coin, en_az_hacim)
elif st.session_state.sayfa == "Sanal Trader":
    _sanal_trader_icerik(depo)
elif st.session_state.sayfa == "Karşılaştırma":
    sayfa_karsilastirma(depo, en_az_hacim)
elif st.session_state.sayfa == "Trade Ajanı":
    sayfa_trade_ajani(st.session_state.secili_coin)
else:
    sayfa_haberler()

st.markdown("---")
if st.session_state.sayfa == "Haberler":
    st.caption("Haberler ücretsiz RSS kaynaklarından toplanır, 5 dakikada bir "
               "tazelenir. Kaan-trade bu haberleri yazmaz, seçmez ya da "
               "yorumlamaz — kaynağında ne yayınlanmışsa onu gösterir.")
elif st.session_state.sayfa == "Analiz Botu":
    st.caption("Gözlemler günlük mumlardan, fonlama oranından ve emir "
               "defterinden hesaplanır; coin değiştirince yenilenir. · Bu "
               "liste bir tavsiye değildir, tahmin de içermez — piyasada "
               "yaygın izlenen durumları ham haliyle bildirir.")
elif st.session_state.sayfa == "Sanal Trader":
    st.caption("Sanal Trader, bilgisayarınızda ayrı çalışan bir arka plan "
               "süreci (sanal_trader.py) — bu sayfa sadece onun yazdığı "
               "dosyaları okur; \"Yenile\" düğmesiyle ya da sayfa/coin "
               "değiştirdiğinizde tazelenir. Tamamen sanal para kullanır, "
               "gerçek emir göndermez.")
elif st.session_state.sayfa == "Trade Ajanı":
    st.caption("Bu stratejiler ayrı bir projeden (Trade-ajanı) aktarıldı ve "
               "canlı Sanal Trader botunu etkilemez. · 1 saatlik mumlarla "
               "hesaplanır, coin değiştirince yenilenir. · Tavsiye değildir.")
elif st.session_state.anlik:
    st.caption(f"Fiyat ve özet sayılar {st.session_state.aralik} saniyede "
               "bir canlı veriden yenileniyor. Grafikler ve tablolar siz "
               "bir şey değiştirdiğinizde güncellenir. Yakınlaştırdığınız "
               "bölge korunur. · Bu ekran piyasanın **şu anki durumunu** "
               "gösterir; tahmin içermez, yatırım tavsiyesi değildir.")
else:
    st.caption("Anlık güncelleme kapalı — sayılar yalnızca bir şey "
               "değiştirdiğinizde yenilenir. · Bu ekran piyasanın **şu anki "
               "durumunu** gösterir; tahmin içermez, yatırım tavsiyesi değildir.")
