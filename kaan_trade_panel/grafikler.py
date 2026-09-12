r"""
GRAFIKLER
=========

Panelin butun grafiklerini bu dosya cizer.

MUM GRAFIGI NASIL OKUNUR?
    Her mum bir zaman dilimini gosterir (ornek: 1 gun).

        Ust fitil  ---  o donemde gorulen EN YUKSEK fiyat
        Govde ust  ---  acilis ya da kapanis (hangisi yuksekse)
        Govde alt  ---  acilis ya da kapanis (hangisi dusukse)
        Alt fitil  ---  o donemde gorulen EN DUSUK fiyat

        YESIL mum  ---  kapanis acilistan YUKSEK (o donem yukseldi)
        KIRMIZI mum---  kapanis acilistan DUSUK  (o donem dustu)

    Uzun fitiller "fiyat oraya gitti ama tutunamadi" demektir.
    Govdenin buyuklugu o donemki hareketin gucunu gosterir.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import gostergeler as gost
from stratejiler import rsi as rsi_hesapla


def mini_sparkline_svg(kapanislar, genislik=132, yukseklik=38):
    """
    Kucuk, hafif bir cizgi grafigi -- Coin analizi basligindaki fiyatin
    yanina konur. BILEREK Plotly DEGIL, elle yazilmis duz SVG: bu
    baslik saniyede bir yeniden ciziliyor (canli parca icinde), ve
    Plotly gibi agir bir kutuphaneyi saniyede bir yeniden calistirmak
    "akici degil, titrek" bir his verir (ayni sebeple piyasa
    sayfasindaki siralamali grafikleri de yavaslattik). Duz SVG neredeyse
    bedava.
    """
    degerler = [float(x) for x in kapanislar if x == x]  # NaN elenir
    if len(degerler) < 2:
        return ""

    en_dusuk, en_yuksek = min(degerler), max(degerler)
    aralik = (en_yuksek - en_dusuk) or 1.0
    n = len(degerler)
    renk = "#26a69a" if degerler[-1] >= degerler[0] else "#ef5350"

    noktalar = []
    for i, v in enumerate(degerler):
        x = i / (n - 1) * genislik
        y = yukseklik - (v - en_dusuk) / aralik * yukseklik
        noktalar.append(f"{x:.1f},{y:.1f}")
    cizgi = " ".join(noktalar)

    # Cizginin altini hafif bir gradyanla doldurmak icin kapali bir yol
    dolgu = f"0,{yukseklik} {cizgi} {genislik},{yukseklik}"

    return (
        f'<svg width="{genislik}" height="{yukseklik}" '
        f'viewBox="0 0 {genislik} {yukseklik}" '
        f'style="display:block" preserveAspectRatio="none">'
        f'<polygon points="{dolgu}" fill="{renk}" opacity="0.10"/>'
        f'<polyline points="{cizgi}" fill="none" stroke="{renk}" '
        f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )

# uygulama.py'deki --kt-* CSS degiskenleriyle AYNI palet -- grafikler
# panelin geri kalaniyla ayni "sistemin parcasi" gibi hissettirsin diye.
YUKSELIS = "#26a69a"
DUSUS = "#ef5350"
NOTR = "#868993"
ORTALAMA_RENKLERI = {9: "#80cbc4", 20: "#42a5f5", 50: "#ffa726",
                     100: "#ec407a", 200: "#ab47bc"}
IZGARA = "rgba(255,255,255,0.08)"
METIN = "#d1d4dc"
YAZI_TIPI = "Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"
YAZI_TIPI_RAKAM = "'JetBrains Mono', ui-monospace, 'Cascadia Code', monospace"

ZAMAN_DILIMLERI = {
    "1 dakika": "1m",
    "5 dakika": "5m",
    "15 dakika": "15m",
    "1 saat": "1h",
    "4 saat": "4h",
    "1 gün": "1d",
    "1 hafta": "1w",
}

PLOTLY_AYARLARI = {
    "scrollZoom": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "displayModeBar": True,
}

# Mum grafigi icin: TradingView'deki gibi cizim araclari (kalem/cizgi/
# dikdortgen/serbest cizim/silgi). Bunlar Plotly'nin KENDI hazir
# ozelligi -- ayrica bir cizim kutuphanesi eklemedik. Arac cubugundaki
# kalem simgelerine tiklayip grafigin uzerine cizebilir, silgi ile de
# tek tek silebilirsiniz. Cizimler TARAYICI TARAFINDA tutulur.
MUM_PLOTLY_AYARLARI = {
    **PLOTLY_AYARLARI,
    "modeBarButtonsToAdd": [
        "drawline", "drawopenpath", "drawrect", "drawcircle", "eraseshape",
    ],
}


def _duzen(figur, baslik, yukseklik, gosterge=True, kimlik="sabit"):
    """
    Butun grafiklerde ayni gorunumu kullanmak icin ortak ayarlar.

    uirevision NEDEN ONEMLI: Grafik yeniden cizildiginde normalde
    yakinlastirmaniz sifirlanir. uirevision degeri ayni kaldigi surece
    plotly kullanicinin yakinlastirma/kaydirma durumunu KORUR. Boylece
    ekran kendini yenilerken incelediginiz bolge kaybolmaz.
    """
    figur.update_layout(
        title=dict(text=baslik, x=0.01, font=dict(size=15, family=YAZI_TIPI, color=METIN)),
        height=yukseklik,
        margin=dict(l=8, r=8, t=44, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=YAZI_TIPI, color=METIN, size=11),
        hovermode="x unified",
        hoverlabel=dict(font=dict(family=YAZI_TIPI_RAKAM, size=11),
                        bgcolor="#1a1e2a", bordercolor=IZGARA),
        dragmode="pan",
        showlegend=gosterge,
        uirevision=kimlik,
        transition=dict(duration=250, easing="cubic-in-out"),
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1, font=dict(size=11, family=YAZI_TIPI)),
    )
    figur.update_xaxes(gridcolor=IZGARA, tickfont=dict(family=YAZI_TIPI_RAKAM, size=10))
    figur.update_yaxes(gridcolor=IZGARA, tickfont=dict(family=YAZI_TIPI_RAKAM, size=10))
    return figur


# ============================================================
#  1) MUM GRAFIGI
# ============================================================

def _fiyat_etiket(v):
    """
    Canli fiyat cizgisinin etiketi icin: uygulama.py'deki fiyat_yaz ile
    AYNI mantik (tam hassasiyet, bilimsel gosterim yok), ama dolar
    isareti olmadan -- grafigin fiyat ekseni zaten USDT cinsinden.
    """
    a = abs(v)
    if a >= 1:
        return f"{v:,.2f}"
    if a >= 0.01:
        return f"{v:,.4f}"
    return f"{v:,.8f}".rstrip("0")


def _canli_mum_ekle(df, canli_fiyat):
    """
    Gecmis mum verisinin sonuna, SU AN olusmakta olan mum icin tek bir
    satir ekler.

    NEDEN GEREKLI: veri_kaynaklari/veri_indir, henuz KAPANMAMIS son mumu
    bilerek atar (yaniltici olmasin diye -- bkz. mum_verisi()). Bu dogru
    bir karardir ama sonucu, grafigin her zaman bir donem GERIDEN
    gorunmesidir. Burada o boslugu, WebSocket'ten gelen canli fiyatla
    dolduruyoruz.

    Eklenen mumun acilisi, bir onceki (kapanmis) mumun kapanisidir.
    Yuksek/dusuk sadece "acilistan bu yana canli fiyat nereye gitti"yi
    yansitir -- donem icinde ARADA gorulen zirve/dip bilinmiyor (onu
    bilmek icin surekli calisan ayri bir biriktirici gerekir), o yuzden
    bu mum digerlerine gore biraz daha "sade" gorunebilir. Yine de
    yoktan iyidir: grafik artik gecmiste degil, su anda duruyor.
    """
    son = df.iloc[-1]
    onceki_kapanis = float(son["kapanis"])
    yeni_zaman = pd.Timestamp.now(tz="UTC")

    yeni_satir = pd.DataFrame([{
        "zaman": yeni_zaman,
        "acilis": onceki_kapanis,
        "yuksek": max(onceki_kapanis, canli_fiyat),
        "dusuk": min(onceki_kapanis, canli_fiyat),
        "kapanis": canli_fiyat,
        "hacim": 0.0,
    }])
    return pd.concat([df, yeni_satir], ignore_index=True)


def mum_grafigi(df, baslik="", ortalamalar=(20, 50, 200), ortalama_tipi="SMA",
                rsi_periyot=None, bollinger=False, hacim=True, yukseklik=None,
                macd_panel=False, stokastik_panel=False, vwap_cizgisi=False,
                parabolik_sar=False, fibonacci=False, canli_fiyat=None):
    """
    Mum grafigi. Istege gore ustune ve altina TradingView'de yaygin
    olan gostergeler eklenir.

    USTE (ayni panelde, fiyatla birlikte):
        ortalamalar, bollinger, vwap_cizgisi, parabolik_sar, fibonacci
    ALTA (ayri panel acar):
        hacim, rsi_periyot, macd_panel, stokastik_panel

    ortalama_tipi : "SMA" (basit) ya da "EMA" (ustel, fiyata daha hizli tepki verir)

    canli_fiyat : su anki (WebSocket'ten gelen) fiyat verilirse iki sey
        olur:
          1. Grafigin SAGINA, henuz tamamlanmamis "su an olusan mum" i
             icin ekstra bir cubuk eklenir (acilis = bir onceki kapanmis
             mumun kapanisi, kapanis = canli fiyat). Boylece grafik az
             once biten mumda degil, TAM SU ANDA duruyormus gibi gorunur.
          2. Fiyatin uzerine, o an nerede oldugunu gosteren yatay,
             kesikli bir "canli fiyat" cizgisi ve etiketi eklenir.
        Veri onbellekten (birkaç dakikada bir) geldigi icin gecmis
        mumlar YENIDEN INDIRILMEZ -- sadece bu son, canli parca eklenir.
        Boylece grafik hem hafif kalir hem de anlik hisseder.
    """
    if df is None or len(df) < 2:
        return None

    if canli_fiyat:
        df = _canli_mum_ekle(df, canli_fiyat)

    # --- Alt panellerin listesini olustur -------------------
    # Her biri (etiket, yukseklik_orani, cizim_fonksiyonu) ucluleri.
    alt_paneller = []
    if hacim:
        alt_paneller.append("hacim")
    if rsi_periyot:
        alt_paneller.append("rsi")
    if macd_panel:
        alt_paneller.append("macd")
    if stokastik_panel:
        alt_paneller.append("stokastik")

    n_alt = len(alt_paneller)
    if n_alt == 0:
        oranlar = [1.0]
    else:
        ust_oran = 0.60 if n_alt >= 2 else 0.72
        alt_oran = (1 - ust_oran) / n_alt
        oranlar = [ust_oran] + [alt_oran] * n_alt

    if yukseklik is None:
        yukseklik = 420 + 105 * n_alt

    figur = make_subplots(rows=1 + n_alt, cols=1, shared_xaxes=True,
                          vertical_spacing=0.03, row_heights=oranlar)

    # --- 1) Mumlar -------------------------------------------
    # line.width varsayilani (1px) inceydi; mumlar sikisik durunca
    # bulanik/belirsiz gorunuyordu. 1.6'ya cikarinca kenarlar netlesiyor,
    # govde dolgusu zaten tam opak oldugu icin renkler daha "sert" ayrisiyor.
    figur.add_trace(go.Candlestick(
        x=df["zaman"], open=df["acilis"], high=df["yuksek"],
        low=df["dusuk"], close=df["kapanis"], name="Fiyat",
        increasing=dict(line=dict(color=YUKSELIS, width=1.6), fillcolor=YUKSELIS),
        decreasing=dict(line=dict(color=DUSUS, width=1.6), fillcolor=DUSUS),
        whiskerwidth=0.85,
        hoverlabel=dict(namelength=0),
    ), row=1, col=1)

    # --- 2) Ustteki gostergeler (fiyatla ayni panelde) -------
    for periyot in ortalamalar:
        if len(df) < periyot:
            continue
        seri = (gost.ema(df["kapanis"], periyot) if ortalama_tipi == "EMA"
                else df["kapanis"].rolling(periyot).mean())
        figur.add_trace(go.Scatter(
            x=df["zaman"], y=seri, name=f"{ortalama_tipi} {periyot}",
            line=dict(width=1.3, color=ORTALAMA_RENKLERI.get(periyot, NOTR)),
            hovertemplate="%{y:,.4f}<extra></extra>",
        ), row=1, col=1)

    if bollinger and len(df) >= 20:
        orta = df["kapanis"].rolling(20).mean()
        sapma = df["kapanis"].rolling(20).std()
        for ad, seri, kesik in (("Bollinger üst", orta + 2 * sapma, "dot"),
                                ("Bollinger alt", orta - 2 * sapma, "dot")):
            figur.add_trace(go.Scatter(
                x=df["zaman"], y=seri, name=ad,
                line=dict(width=1, color="#90a4ae", dash=kesik),
                hovertemplate="%{y:,.4f}<extra></extra>",
            ), row=1, col=1)

    if vwap_cizgisi:
        figur.add_trace(go.Scatter(
            x=df["zaman"], y=gost.vwap(df), name="VWAP",
            line=dict(width=1.4, color="#7e57c2", dash="dash"),
            hovertemplate="VWAP: %{y:,.4f}<extra></extra>",
        ), row=1, col=1)

    if parabolik_sar and len(df) >= 5:
        sar = gost.parabolik_sar(df)
        figur.add_trace(go.Scatter(
            x=df["zaman"], y=sar, name="Parabolic SAR", mode="markers",
            marker=dict(size=3.5, color="#fdd835"),
            hovertemplate="SAR: %{y:,.4f}<extra></extra>",
        ), row=1, col=1)

    if fibonacci:
        for oran, fiyat in gost.fibonacci_seviyeleri(df):
            renk = "#ffca28" if oran in (0.382, 0.618) else "#546e7a"
            figur.add_hline(
                y=fiyat, row=1, col=1,
                line=dict(color=renk, width=1, dash="dot"),
                annotation_text=f"%{oran*100:.1f}", annotation_position="right",
                annotation_font=dict(size=10, color=renk))

    if canli_fiyat:
        # Her seyin en ustune, "su an burada" diyen kesikli bir cizgi.
        # Bir onceki kapanisa gore renk degisir -- yon aninda okunur.
        onceki_kapanis = float(df["kapanis"].iloc[-2]) if len(df) >= 2 else canli_fiyat
        renk = YUKSELIS if canli_fiyat >= onceki_kapanis else DUSUS
        figur.add_hline(
            y=canli_fiyat, row=1, col=1,
            line=dict(color=renk, width=1.2, dash="dash"),
            annotation_text=f" {_fiyat_etiket(canli_fiyat)} ", annotation_position="right",
            annotation_font=dict(size=11, color="#0b0e14", family=YAZI_TIPI),
            annotation_bgcolor=renk, annotation_bordercolor=renk,
            annotation_borderwidth=0, annotation_borderpad=3)

    # --- 3) Alt paneller --------------------------------------
    satir = 2
    for ad in alt_paneller:
        if ad == "hacim":
            renkler = [YUKSELIS if k >= a else DUSUS
                       for a, k in zip(df["acilis"], df["kapanis"])]
            figur.add_trace(go.Bar(
                x=df["zaman"], y=df["hacim"], name="Hacim",
                marker=dict(color=renkler, line=dict(width=0)), opacity=0.55,
                hovertemplate="hacim: %{y:,.0f}<extra></extra>",
            ), row=satir, col=1)
            figur.update_yaxes(title_text="Hacim", row=satir, col=1,
                               side="right", showgrid=False)

        elif ad == "rsi":
            r = rsi_hesapla(df["kapanis"], rsi_periyot)
            figur.add_trace(go.Scatter(
                x=df["zaman"], y=r, name=f"RSI {rsi_periyot}",
                line=dict(width=1.4, color="#ffca28"),
                hovertemplate="RSI: %{y:.1f}<extra></extra>",
            ), row=satir, col=1)
            for seviye, renk in ((70, DUSUS), (30, YUKSELIS)):
                figur.add_hline(y=seviye, line=dict(color=renk, width=1, dash="dot"),
                                row=satir, col=1)
            figur.update_yaxes(title_text="RSI", range=[0, 100], row=satir, col=1,
                               side="right", showgrid=False)

        elif ad == "macd":
            m, s, h = gost.macd(df["kapanis"])
            renkler = [YUKSELIS if v >= 0 else DUSUS for v in h.fillna(0)]
            figur.add_trace(go.Bar(
                x=df["zaman"], y=h, name="MACD histogram",
                marker=dict(color=renkler, line=dict(width=0)), opacity=0.6,
                hovertemplate="%{y:.2f}<extra></extra>",
            ), row=satir, col=1)
            figur.add_trace(go.Scatter(
                x=df["zaman"], y=m, name="MACD",
                line=dict(width=1.3, color="#42a5f5"),
                hovertemplate="MACD: %{y:.2f}<extra></extra>",
            ), row=satir, col=1)
            figur.add_trace(go.Scatter(
                x=df["zaman"], y=s, name="Sinyal",
                line=dict(width=1.1, color="#ff7043"),
                hovertemplate="Sinyal: %{y:.2f}<extra></extra>",
            ), row=satir, col=1)
            figur.update_yaxes(title_text="MACD", row=satir, col=1,
                               side="right", showgrid=False)

        elif ad == "stokastik":
            k, d = gost.stokastik(df)
            figur.add_trace(go.Scatter(
                x=df["zaman"], y=k, name="%K",
                line=dict(width=1.3, color="#42a5f5"),
                hovertemplate="%%K: %{y:.1f}<extra></extra>",
            ), row=satir, col=1)
            figur.add_trace(go.Scatter(
                x=df["zaman"], y=d, name="%D",
                line=dict(width=1.1, color="#ff7043"),
                hovertemplate="%%D: %{y:.1f}<extra></extra>",
            ), row=satir, col=1)
            for seviye, renk in ((80, DUSUS), (20, YUKSELIS)):
                figur.add_hline(y=seviye, line=dict(color=renk, width=1, dash="dot"),
                                row=satir, col=1)
            figur.update_yaxes(title_text="Stokastik", range=[0, 100], row=satir, col=1,
                               side="right", showgrid=False)

        satir += 1

    figur.update_xaxes(showspikes=True, spikemode="across", spikethickness=1,
                       spikedash="dot", spikecolor="#888888")
    figur.update_yaxes(title_text="Fiyat (USDT)", row=1, col=1, side="right")
    figur.update_layout(
        xaxis_rangeslider_visible=False,
        # Kalemle yeni cizilen sekillerin varsayilan gorunumu (renk,
        # kalinlik). Cizdikten sonra da rengini/kalinligini degistirmek
        # isterseniz sekle sag tiklayip duzenleyebilirsiniz.
        newshape=dict(line=dict(color="#ffca28", width=2), opacity=0.9,
                     fillcolor="rgba(255,202,40,0.12)"),
        # Bir sekli secince (silmeden once) nasil vurgulanacagi.
        activeshape=dict(fillcolor="#ffca28", opacity=0.25),
    )
    # Kimlik basliktan turetiliyor: ayni coin/dilim icin yakinlastirma
    # (ve -- uirevision Plotly'de sekilleri de kapsadigi icin -- CIZIMLER
    # DE) korunur; coin ya da zaman dilimi degisince sifirlanir (dogru
    # olan bu, cunku farkli bir coine gecince eski cizimin orada durmasi
    # anlamsiz olurdu).
    return _duzen(figur, baslik, yukseklik, kimlik=f"mum::{baslik}")


# ============================================================
#  2) KARSILASTIRMA
# ============================================================

def karsilastirma(veriler, baslik="Karşılaştırma", yukseklik=440):
    """
    Birkac coini ayni grafikte karsilastirir.

    Fiyatlar cok farkli oldugu icin (BTC 64.000, DOGE 0,20) hepsini
    baslangicta 100'e esitliyoruz. Boylece "hangisi yuzde kac degisti"
    sorusu gorsel olarak cevaplanabilir hale gelir.

    veriler : {"BTC/USDT": DataFrame, "ETH/USDT": DataFrame, ...}
    """
    if not veriler:
        return None

    figur = go.Figure()
    renkler = ["#42a5f5", "#26a69a", "#ffa726", "#ec407a", "#ab47bc",
               "#ffca28", "#8d6e63", "#78909c"]

    for i, (sembol, df) in enumerate(veriler.items()):
        if df is None or len(df) < 2:
            continue
        ilk = df["kapanis"].iloc[0]
        if not ilk:
            continue
        figur.add_trace(go.Scatter(
            x=df["zaman"], y=df["kapanis"] / ilk * 100,
            name=sembol.replace("/USDT", ""),
            line=dict(width=1.8, color=renkler[i % len(renkler)]),
            hovertemplate="%{y:.1f}<extra></extra>",
        ))

    figur.add_hline(y=100, line=dict(color=NOTR, width=1, dash="dot"))
    figur.update_yaxes(title_text="Başlangıç = 100", side="right")
    return _duzen(figur, baslik, yukseklik)


def korelasyon_haritasi(veriler, baslik="Birlikte hareket etme (korelasyon)",
                        yukseklik=None):
    """
    Coinlerin gunluk getirileri ne kadar birlikte hareket ediyor?

      +1'e yakin -> neredeyse ayni anda ayni yone gidiyorlar
       0'a yakin -> birbirinden bagimsiz hareket ediyorlar
      -1'e yakin -> ters yone gidiyorlar

    NEDEN ONEMLI: Hepsi +0,9 korelasyonlu 10 coin almak, aslinda tek bir
    coinden 10 kat almak gibidir. Risk dagitmis olmazsiniz.
    """
    if not veriler or len(veriler) < 2:
        return None

    getiriler = {}
    for sembol, df in veriler.items():
        if df is None or len(df) < 10:
            continue
        s = pd.Series(df["kapanis"].pct_change().values,
                      index=pd.to_datetime(df["zaman"].values))
        getiriler[sembol.replace("/USDT", "")] = s

    if len(getiriler) < 2:
        return None

    tablo = pd.DataFrame(getiriler).dropna()
    if len(tablo) < 5:
        return None
    korelasyon = tablo.corr()

    if yukseklik is None:
        yukseklik = max(320, 68 * len(korelasyon))

    figur = go.Figure(go.Heatmap(
        z=korelasyon.values,
        x=korelasyon.columns, y=korelasyon.index,
        zmin=-1, zmax=1,
        colorscale=[[0.0, DUSUS], [0.5, "#263238"], [1.0, YUKSELIS]],
        text=np.round(korelasyon.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=11),
        hovertemplate="%{y} ↔ %{x}: %{z:.2f}<extra></extra>",
        colorbar=dict(thickness=12, len=0.85),
    ))
    figur.update_layout(
        title=dict(text=baslik, x=0.01, font=dict(size=15, family=YAZI_TIPI, color=METIN)),
        height=yukseklik, margin=dict(l=8, r=8, t=44, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=YAZI_TIPI, color=METIN, size=11),
        hovermode="closest", showlegend=False,
    )
    figur.update_yaxes(autorange="reversed")
    return figur


# ============================================================
#  3) PIYASA GENELI CUBUK GRAFIKLERI
# ============================================================

def degisim_cubuklari(df, baslik="", adet=15, yukseklik=None, artan=True):
    """
    En cok yukselen (ya da en cok dusen) coinleri yatay cubuk olarak cizer.
    """
    if df is None or df.empty:
        return None

    gecerli = df[df["degisim"].notna()].copy()
    if gecerli.empty:
        return None

    secim = (gecerli.nlargest(adet, "degisim") if artan
             else gecerli.nsmallest(adet, "degisim"))
    secim = secim.sort_values("degisim")

    if yukseklik is None:
        yukseklik = max(280, 30 * len(secim) + 90)

    figur = go.Figure(go.Bar(
        x=secim["degisim"], y=secim["kod"], orientation="h",
        marker=dict(color=[YUKSELIS if d >= 0 else DUSUS for d in secim["degisim"]],
                    line=dict(width=0)),
        text=[f"{d:+.1f}%" for d in secim["degisim"]],
        textposition="outside", textfont=dict(size=11),
        hovertemplate="%{y}: %{x:+.2f}%<extra></extra>",
    ))
    figur.update_layout(
        title=dict(text=baslik, x=0.01, font=dict(size=15, family=YAZI_TIPI, color=METIN)),
        height=yukseklik, margin=dict(l=8, r=48, t=44, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=YAZI_TIPI, color=METIN, size=11),
        showlegend=False, hovermode="closest",
    )
    figur.update_xaxes(title_text="24 saatlik değişim (%)", gridcolor=IZGARA)
    figur.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return figur


def hacim_cubuklari(df, baslik="En yüksek hacimli coinler", adet=15,
                    yukseklik=None):
    """Islem hacmi en yuksek coinler. Hacim = o coine olan gercek ilgi."""
    if df is None or df.empty:
        return None
    secim = df.nlargest(adet, "hacim").sort_values("hacim")
    if secim.empty:
        return None
    if yukseklik is None:
        yukseklik = max(280, 30 * len(secim) + 90)

    figur = go.Figure(go.Bar(
        x=secim["hacim"] / 1e6, y=secim["kod"], orientation="h",
        marker=dict(color="#42a5f5", line=dict(width=0)),
        text=[f"{h/1e6:,.0f}M" for h in secim["hacim"]],
        textposition="outside", textfont=dict(size=11),
        hovertemplate="%{y}: %{x:,.1f} milyon $<extra></extra>",
    ))
    figur.update_layout(
        title=dict(text=baslik, x=0.01, font=dict(size=15, family=YAZI_TIPI, color=METIN)),
        height=yukseklik, margin=dict(l=8, r=60, t=44, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=YAZI_TIPI, color=METIN, size=11),
        showlegend=False, hovermode="closest",
    )
    figur.update_xaxes(title_text="24 saatlik hacim (milyon $)", gridcolor=IZGARA)
    figur.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return figur


def piyasa_dagilimi(df, baslik="Piyasa nasıl dağılmış?", yukseklik=320):
    """
    Butun coinlerin 24 saatlik degisimlerinin dagilimi (histogram).

    Bu grafik "piyasa genel olarak ne yapiyor" sorusunu tek bakista
    cevaplar. Tepe sifirin sagindaysa cogunluk yukselmis, solundaysa
    cogunluk dusmus demektir.
    """
    if df is None or df.empty:
        return None
    gecerli = df[df["degisim"].notna()]["degisim"]
    if gecerli.empty:
        return None

    kirpilmis = gecerli.clip(-30, 30)
    figur = go.Figure(go.Histogram(
        x=kirpilmis, nbinsx=60,
        marker=dict(color="#42a5f5", line=dict(width=0)),
        hovertemplate="%{x:.0f}%: %{y} coin<extra></extra>",
    ))
    figur.add_vline(x=0, line=dict(color=NOTR, width=1.5, dash="dot"))
    ortalama = float(gecerli.median())
    figur.add_vline(x=max(-30, min(30, ortalama)),
                    line=dict(color="#ffca28", width=1.5))
    figur.update_layout(
        title=dict(text=baslik, x=0.01, font=dict(size=15, family=YAZI_TIPI, color=METIN)),
        height=yukseklik, margin=dict(l=8, r=8, t=44, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=YAZI_TIPI, color=METIN, size=11),
        showlegend=False, bargap=0.04,
    )
    figur.update_xaxes(title_text="24 saatlik değişim (%)  ·  ±30 ile sınırlandı",
                       gridcolor=IZGARA)
    figur.update_yaxes(title_text="Kaç coin", gridcolor=IZGARA)
    return figur


def sanal_trader_egrisi(egri_df, islem_df, baslangic_bakiye,
                        baslik="Sanal cüzdan değeri", yukseklik=380):
    """
    Sanal Trader sayfasi icin SUREKLI cuzdan degeri egrisi + AL/SAT
    isaretleri.

    egri_df  : uygulama.py._sanal_trader_egri_verisi()'nin urettigi
               {"zaman", "deger"} tablosu -- islem araliklarinda elde
               tutulan coinin SAATLIK fiyatiyla hesaplanmis, SUREKLI bir
               seri (eski versiyondaki gibi sadece islem anlarinda
               DEGIL).
    islem_df : sanal_trader.py'nin islemler.csv'si -- AL/SAT noktalarini
               ucgen isaretleyicilerle grafige eklemek icin.
    """
    if egri_df is None or egri_df.empty:
        return None

    figur = go.Figure()
    figur.add_trace(go.Scatter(
        x=egri_df["zaman"], y=egri_df["deger"], name="Cüzdan değeri", mode="lines",
        line=dict(width=1.8, color="#42a5f5"),
        hovertemplate="%{y:,.2f} USDT<extra></extra>",
    ))

    if islem_df is not None and not islem_df.empty:
        df = islem_df.copy()
        df["tarih"] = pd.to_datetime(df["tarih"])
        alis = df[df["islem"].astype(str).str.startswith("AL")]
        satis = df[df["islem"].astype(str).str.startswith("SAT")]
        if not alis.empty:
            figur.add_trace(go.Scatter(
                x=alis["tarih"], y=alis["portfoy_degeri"], mode="markers", name="Alım",
                marker=dict(symbol="triangle-up", size=11, color=YUKSELIS,
                           line=dict(width=1, color="#0b0e14")),
                customdata=alis["sembol"],
                hovertemplate="AL — %{customdata}<br>%{y:,.2f} USDT<extra></extra>",
            ))
        if not satis.empty:
            figur.add_trace(go.Scatter(
                x=satis["tarih"], y=satis["portfoy_degeri"], mode="markers", name="Satım",
                marker=dict(symbol="triangle-down", size=11, color=DUSUS,
                           line=dict(width=1, color="#0b0e14")),
                customdata=satis["sembol"],
                hovertemplate="SAT — %{customdata}<br>%{y:,.2f} USDT<extra></extra>",
            ))

    figur.add_hline(y=baslangic_bakiye, line=dict(color=NOTR, width=1, dash="dot"),
                    annotation_text="başlangıç", annotation_position="right",
                    annotation_font=dict(size=10, color=NOTR))
    figur.update_yaxes(title_text="USDT", side="right")
    return _duzen(figur, baslik, yukseklik, kimlik="sanal_trader_egri")


def genislik_gostergesi(yukselen, dusen, yukseklik=150):
    """
    Piyasa genisligi: kac coin yukseliyor, kac coin dusuyor.
    Tek bir yatay cubukta gosterir.
    """
    toplam = yukselen + dusen
    if not toplam:
        return None
    figur = go.Figure()
    figur.add_trace(go.Bar(
        x=[yukselen], y=["Piyasa"], orientation="h", name=f"Yükselen ({yukselen})",
        marker=dict(color=YUKSELIS, line=dict(width=0)),
        hovertemplate=f"{yukselen} coin yükseliyor<extra></extra>",
    ))
    figur.add_trace(go.Bar(
        x=[dusen], y=["Piyasa"], orientation="h", name=f"Düşen ({dusen})",
        marker=dict(color=DUSUS, line=dict(width=0)),
        hovertemplate=f"{dusen} coin düşüyor<extra></extra>",
    ))
    figur.update_layout(
        barmode="stack", height=yukseklik,
        margin=dict(l=8, r=8, t=30, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=YAZI_TIPI, color=METIN),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    font=dict(size=12, family=YAZI_TIPI)),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False),
    )
    return figur
