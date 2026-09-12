r"""
CANLI VERI KATMANI  (WebSocket)
===============================

Bu dosya panelin "anlik" olmasini saglar.

ESKI YOL (60 saniyede bir):
    Panel borsaya "fiyat kac?" diye soruyordu, cevabi aliyordu, 60 saniye
    bekliyordu, tekrar soruyordu. Arada olan her sey kaciyordu.

YENI YOL (surekli acik hat):
    Borsayla bir kez WebSocket baglantisi kuruyoruz ve hat acik kaliyor.
    Borsa her fiyat degisimini KENDISI bize gonderiyor. Biz sormuyoruz,
    o soyluyor. Gecikme yaklasik 1 saniye.

NASIL CALISIR?
    1. Ilk acilista tek bir REST cagrisiyla butun coinlerin 24 saatlik
       ozeti alinir (712 USDT cifti, ~4 saniye). Tablo aninda dolar.
    2. Arka planda bir is parcacigi (thread) Binance'in
       "!miniTicker@arr" yayinina baglanir. Bu yayin saniyede bir,
       o saniye ISLEM GOREN butun coinlerin son fiyatini gonderir.
    3. Gelen her veri hafizadaki depoya yazilir.
    4. Ekran bu depodan okur -- internete hic gitmez, o yuzden saniyede
       bir yenilenmesi bedava.

ONEMLI NOT: Islem gormeyen bir coinin fiyati da degismez. Yani "3 dakika
once guncellendi" yazan bir coin bozuk degil, sadece 3 dakikadir kimse
onu alip satmamis demektir.
"""

import asyncio
import json
import threading
import time
from datetime import datetime, timezone

import ccxt
import pandas as pd
import websockets

YAYIN_ADRESI = "wss://stream.binance.com:9443/ws/!miniTicker@arr"
YEDEK_ADRES = "wss://data-stream.binance.vision/ws/!miniTicker@arr"


class CanliPiyasa:
    """
    Butun coinlerin anlik fiyatlarini hafizada tutan depo.

    Tek bir ornegi olusturulur ve butun panel onu kullanir.
    """

    def __init__(self, kote="USDT"):
        self.kote = kote
        self._veri = {}                  # sembol -> olculer
        self._kilit = threading.Lock()   # thread'ler ayni anda yazmasin
        self._parcacik = None
        self._dur = threading.Event()
        self.durum = {
            "baglandi": False,
            "mesaj_sayisi": 0,
            "son_mesaj": None,
            "ilk_dolum": False,
            "sembol_sayisi": 0,
            "hata": None,
            "baslangic": None,
            "kaynak": None,
        }

    # ========================================================
    #  BASLATMA
    # ========================================================

    def baslat(self):
        """Arka plan baglantisini kurar. Iki kez cagrilsa da bir kez calisir."""
        if self._parcacik and self._parcacik.is_alive():
            return self
        self.durum["baslangic"] = datetime.now(timezone.utc)
        self._ilk_dolumu_yap()
        self._dur.clear()
        # daemon=True: uygulama kapaninca bu parcacik da kapanir
        self._parcacik = threading.Thread(target=self._dongu, daemon=True,
                                          name="canli-piyasa")
        self._parcacik.start()
        return self

    def durdur(self):
        self._dur.set()

    def _ilk_dolumu_yap(self):
        """
        Tek REST cagrisiyla butun coinleri bir kerede al. Boylece tablo
        WebSocket'ten veri gelmeye baslamadan once de dolu gorunur.
        """
        try:
            borsa = ccxt.binance({"enableRateLimit": True, "timeout": 30000})
            hepsi = borsa.fetch_tickers()
        except Exception as e:
            self.durum["hata"] = f"Ilk dolum basarisiz: {str(e)[:120]}"
            return

        simdi = time.time()
        yeni = {}
        for sembol, t in hepsi.items():
            if not sembol.endswith("/" + self.kote):
                continue
            fiyat = t.get("last")
            if not fiyat:
                continue
            yeni[sembol] = {
                "sembol": sembol,
                "kod": sembol.split("/")[0],
                "fiyat": fiyat,
                "onceki_fiyat": fiyat,
                "acilis": t.get("open"),
                "yuksek": t.get("high"),
                "dusuk": t.get("low"),
                "degisim": t.get("percentage"),
                "hacim": t.get("quoteVolume"),
                "temel_hacim": t.get("baseVolume"),
                "guncelleme": simdi,
            }
        with self._kilit:
            self._veri.update(yeni)
            self.durum["ilk_dolum"] = True
            self.durum["sembol_sayisi"] = len(self._veri)

    # ========================================================
    #  ARKA PLAN DONGUSU
    # ========================================================

    def _dongu(self):
        """Kendi asyncio dongusunu kuran arka plan parcacigi."""
        dongu = asyncio.new_event_loop()
        asyncio.set_event_loop(dongu)
        try:
            dongu.run_until_complete(self._dinle())
        except Exception as e:
            self.durum["hata"] = f"{type(e).__name__}: {str(e)[:120]}"
        finally:
            dongu.close()

    async def _dinle(self):
        """
        Yayina baglanir ve dinler. Baglanti koparsa artan bekleme
        sureleriyle tekrar dener (1, 2, 4, 8... en fazla 30 saniye).
        """
        bekleme = 1
        adresler = [YAYIN_ADRESI, YEDEK_ADRES]
        sira = 0

        while not self._dur.is_set():
            adres = adresler[sira % len(adresler)]
            try:
                async with websockets.connect(adres, ping_interval=20,
                                              close_timeout=5,
                                              max_queue=64) as ws:
                    self.durum["baglandi"] = True
                    self.durum["hata"] = None
                    self.durum["kaynak"] = adres.split("/")[2]
                    bekleme = 1

                    while not self._dur.is_set():
                        try:
                            ham = await asyncio.wait_for(ws.recv(), timeout=45)
                        except asyncio.TimeoutError:
                            break            # 45 sn sessizlik -> yeniden bagla
                        self._isle(ham)

            except Exception as e:
                self.durum["hata"] = f"{type(e).__name__}: {str(e)[:100]}"
                sira += 1                    # yedek adrese gec

            self.durum["baglandi"] = False
            if self._dur.is_set():
                break
            await asyncio.sleep(bekleme)
            bekleme = min(bekleme * 2, 30)

    def _isle(self, ham):
        """Gelen mesaji depoya yazar."""
        try:
            kayitlar = json.loads(ham)
        except Exception:
            return
        if not isinstance(kayitlar, list):
            return

        simdi = time.time()
        son = "/" + self.kote
        with self._kilit:
            for k in kayitlar:
                ham_sembol = k.get("s", "")
                if not ham_sembol.endswith(self.kote):
                    continue
                kod = ham_sembol[:-len(self.kote)]
                sembol = kod + son
                try:
                    fiyat = float(k["c"])
                    acilis = float(k["o"])
                except (KeyError, TypeError, ValueError):
                    continue

                eski = self._veri.get(sembol)
                self._veri[sembol] = {
                    "sembol": sembol,
                    "kod": kod,
                    "fiyat": fiyat,
                    "onceki_fiyat": eski["fiyat"] if eski else fiyat,
                    "acilis": acilis,
                    "yuksek": float(k.get("h") or 0) or None,
                    "dusuk": float(k.get("l") or 0) or None,
                    "degisim": (fiyat / acilis - 1) * 100 if acilis else None,
                    "hacim": float(k.get("q") or 0) or None,
                    "temel_hacim": float(k.get("v") or 0) or None,
                    "guncelleme": simdi,
                }
            self.durum["mesaj_sayisi"] += 1
            self.durum["son_mesaj"] = simdi
            self.durum["sembol_sayisi"] = len(self._veri)

    # ========================================================
    #  OKUMA
    # ========================================================

    def coin(self, sembol):
        """Tek bir coinin son durumu."""
        with self._kilit:
            k = self._veri.get(sembol)
            return dict(k) if k else None

    def tablo(self, en_az_hacim=0):
        """
        Butun coinleri tablo (DataFrame) olarak dondurur.

        en_az_hacim : bu dolar hacminin altindaki coinleri gizler.
                      Cok kucuk hacimli coinlerde fiyat guvenilmez olur.
        """
        with self._kilit:
            kayitlar = [dict(v) for v in self._veri.values()]
        if not kayitlar:
            return pd.DataFrame()

        df = pd.DataFrame(kayitlar)
        simdi = time.time()
        df["yas_saniye"] = (simdi - df["guncelleme"]).round(0)
        if en_az_hacim:
            df = df[df["hacim"].fillna(0) >= en_az_hacim]
        return df.sort_values("hacim", ascending=False,
                              na_position="last").reset_index(drop=True)

    def semboller(self, en_az_hacim=0):
        """Arama cubugu icin sembol listesi (hacme gore sirali)."""
        df = self.tablo(en_az_hacim)
        return [] if df.empty else df["sembol"].tolist()

    def ozet(self):
        """Baglanti durumu ve piyasa geneli sayilar."""
        df = self.tablo()
        d = dict(self.durum)
        if df.empty:
            return d

        gecerli = df[df["degisim"].notna()]
        d["toplam_coin"] = len(df)
        d["yukselen"] = int((gecerli["degisim"] > 0).sum())
        d["dusen"] = int((gecerli["degisim"] < 0).sum())
        d["sabit"] = int((gecerli["degisim"] == 0).sum())
        d["ortalama_degisim"] = float(gecerli["degisim"].mean()) if len(gecerli) else None
        d["medyan_degisim"] = float(gecerli["degisim"].median()) if len(gecerli) else None
        d["toplam_hacim"] = float(df["hacim"].fillna(0).sum())
        if d["son_mesaj"]:
            d["gecikme"] = round(time.time() - d["son_mesaj"], 1)
        return d


# ============================================================
#  TEK ORNEK  (singleton)
# ============================================================

_ornek = None
_ornek_kilidi = threading.Lock()


def piyasa():
    """
    Uygulamanin her yerinden ayni depoya erisim saglar.
    Ilk cagrida baglantiyi kurar, sonrakilerde ayni ornegi dondurur.
    """
    global _ornek
    with _ornek_kilidi:
        if _ornek is None:
            _ornek = CanliPiyasa().baslat()
    return _ornek


if __name__ == "__main__":
    # Tek basina calistirilirsa kisa bir kendini test etme
    p = piyasa()
    print("Ilk dolum bekleniyor...")
    for i in range(15):
        time.sleep(2)
        o = p.ozet()
        print(f"{i*2:3}sn  baglandi={o['baglandi']}  mesaj={o['mesaj_sayisi']:3}  "
              f"coin={o.get('toplam_coin', 0):4}  "
              f"yukselen={o.get('yukselen', 0):4} dusen={o.get('dusen', 0):4}  "
              f"gecikme={o.get('gecikme', '-')}")
        b = p.coin("BTC/USDT")
        if b:
            print(f"      BTC/USDT = {b['fiyat']:,.2f}  ({b['degisim']:+.2f}%)  "
                  f"yas={time.time()-b['guncelleme']:.1f}sn")
