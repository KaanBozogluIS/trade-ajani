r"""
MASAUSTU UYGULAMASI
===================

Paneli tarayicida degil, KENDI PENCERESINDE acar. Adres cubugu,
sekmeler ya da tarayici menuleri gorunmez -- normal bir Windows
uygulamasi gibi davranir.

NASIL CALISIR?
    1. Streamlit sunucusunu arka planda, GORUNMEZ olarak baslatir
       (siyah komut penceresi acilmaz).
    2. Sunucunun hazir olmasini bekler.
    3. pywebview ile bir masaustu penceresi acar ve paneli icine yukler.
    4. Pencereyi kapattiginizda arka plandaki sunucuyu da kapatir.

Baslatmak icin:  KaanTrade.vbs dosyasina cift tiklayin
                 (ya da masaustundeki kisayola)
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

import webview

KLASOR = Path(__file__).parent
PORT = 8501
ADRES = f"http://127.0.0.1:{PORT}"
BEKLEME_SANIYE = 90


def port_dinliyor_mu(port):
    """O portta calisan bir sunucu var mi?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def streamlit_baslat():
    """
    Streamlit'i gorunmez bir surec olarak baslatir.
    Zaten calisiyorsa yenisini baslatmaz.
    """
    if port_dinliyor_mu(PORT):
        print("Sunucu zaten calisiyor, ona baglaniyorum.")
        return None

    streamlit = KLASOR / ".venv" / "Scripts" / "streamlit.exe"
    if not streamlit.exists():
        # Sanal ortam yoksa mevcut Python ile dene
        komut = [sys.executable, "-m", "streamlit", "run", "uygulama.py"]
    else:
        komut = [str(streamlit), "run", "uygulama.py"]

    komut += ["--server.port", str(PORT),
              "--server.address", "127.0.0.1",
              "--server.headless", "true",
              "--browser.gatherUsageStats", "false"]

    # CREATE_NO_WINDOW: siyah komut penceresi acilmasin
    gizle = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

    return subprocess.Popen(
        komut, cwd=str(KLASOR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=gizle,
    )


def sunucuyu_bekle(saniye=BEKLEME_SANIYE):
    """Sunucu ayaga kalkana kadar bekler."""
    basla = time.time()
    while time.time() - basla < saniye:
        if port_dinliyor_mu(PORT):
            time.sleep(1.2)      # ilk sayfanin hazirlanmasi icin kisa pay
            return True
        time.sleep(0.4)
    return False


def main():
    surec = streamlit_baslat()

    if not sunucuyu_bekle():
        webview.create_window(
            "kaan-trade — hata",
            html="<body style='font-family:sans-serif;padding:40px;"
                 "background:#0e1117;color:#e6e6e6'>"
                 "<h2>Panel başlatılamadı</h2>"
                 "<p>Sunucu beklenen sürede açılmadı.</p>"
                 "<p>Bunu deneyin: klasördeki <b>uygulamayi_baslat.bat</b> "
                 "dosyasına çift tıklayın. Açılan siyah pencerede bir hata "
                 "mesajı görürseniz, o mesaj sorunun ne olduğunu söyler.</p>"
                 "</body>",
            width=620, height=380)
        webview.start()
        return

    pencere = webview.create_window(
        "kaan-trade paneli",
        ADRES,
        width=1560, height=980,
        min_size=(1100, 700),
        background_color="#0e1117",
        text_select=True,
    )

    # Gorev cubugunda kendi ikonumuz gorunsun. Bazi Windows
    # kurulumlarinda desteklenmez; o zaman ikonsuz devam ederiz.
    ikon = KLASOR / "kaantrade.ico"
    try:
        if ikon.exists():
            webview.start(private_mode=False, icon=str(ikon))
        else:
            webview.start(private_mode=False)
    except TypeError:
        webview.start(private_mode=False)
    finally:
        # Pencere kapandi -- arka plandaki sunucuyu da kapat
        if surec is not None:
            surec.terminate()
            try:
                surec.wait(timeout=8)
            except Exception:
                surec.kill()


if __name__ == "__main__":
    main()
