"""7/24 sunucu calistiricisi - GitHub Actions'in yerine (ya da onunla birlikte) calisir.

NEDEN: GitHub'in zamanlayicisi isleri olcumlere gore ciddi kisiyor -
"5 dakikada bir" ayarli Telegram taramasi fiilen ~50 dakikada bir, "saatte
bir" Sanal Trader fiilen ~1.5 saatte bir calisiyordu (7-8 saate varan
bosluklarla). Surekli acik bir makinede (VPS, Oracle Cloud ucretsiz sunucu,
Raspberry Pi) bu dongu GERCEKTEN 5 dakikada / saatte bir calisir.

NE YAPAR (sonsuz dongu):
  - her 5 dakikada bir: scripts/live_scan.py (Telegram sinyal taramasi)
  - her saatin 5. dakikasindan sonra bir kez: kaan_trade_panel/sanal_trader.py --once
  - her isten sonra degisen durumu git'e commit edip push eder (GitHub'daki
    panel/gecmis ayni kalir) ve data/state/sunucu_nabiz.json "nabiz"ini yazar.

GITHUB ILE BIRLIKTE: live_scan.yml ve sanal_trader.yml her calismada bu nabza
bakar - sunucu son 20 dakikada calistiysa KENDINI ATLAR (ayni portfoyu iki
yer ayni anda degistirmesin). Sunucu durursa/coker ise nabiz eskir ve GitHub
otomatik olarak yedek gorevine doner - ek bir ayar gerekmez.

Calistirmak icin (sunucuda, depo kokunden): python scripts/sunucu_7x24.py
Kurulum: deploy/KURULUM.md
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

KOK = Path(__file__).resolve().parents[1]
PANEL = KOK / "kaan_trade_panel"
NABIZ = KOK / "data" / "state" / "sunucu_nabiz.json"
NABIZ_GIT = "data/state/sunucu_nabiz.json"
TARAMA_ARALIGI_SN = 300
SANAL_TRADER_DAKIKASI = 5


def log(mesaj: str) -> None:
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {mesaj}", flush=True)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=KOK, capture_output=True, text=True)


def guncel_kodu_cek() -> None:
    sonuc = git("pull", "--rebase", "-q", "origin", "main")
    if sonuc.returncode != 0:
        git("rebase", "--abort")
        log(f"git pull basarisiz (devam ediliyor): {sonuc.stderr.strip()[:200]}")


def nabiz_yaz(is_adi: str) -> None:
    NABIZ.parent.mkdir(parents=True, exist_ok=True)
    NABIZ.write_text(json.dumps({
        "zaman": datetime.now(timezone.utc).isoformat(),
        "makine": socket.gethostname(),
        "son_is": is_adi,
    }, indent=2), encoding="utf-8")


def kaydet_ve_gonder(yollar: list[str], mesaj: str) -> None:
    git("add", *yollar)
    if git("diff", "--staged", "--quiet").returncode == 0:
        return
    git("commit", "-q", "-m", mesaj)
    for deneme in range(1, 6):
        if git("pull", "--rebase", "-q", "origin", "main").returncode == 0 \
                and git("push", "-q").returncode == 0:
            return
        git("rebase", "--abort")
        log(f"push basarisiz, tekrar deneniyor ({deneme}/5)")
        time.sleep(5 * deneme)
    log("UYARI: push 5 denemede de basarisiz - degisiklik yerelde duruyor, sonraki turda tekrar denenecek")


def calistir(komut: list[str], dizin: Path, zaman_asimi_sn: int) -> int:
    try:
        return subprocess.run(komut, cwd=dizin, timeout=zaman_asimi_sn, env=os.environ.copy()).returncode
    except subprocess.TimeoutExpired:
        log(f"ZAMAN ASIMI ({zaman_asimi_sn} sn): {' '.join(komut)}")
        return -1


def main() -> None:
    load_dotenv(KOK / ".env")  # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID -> alt sureclere aktarilir
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        log("UYARI: .env'de TELEGRAM_BOT_TOKEN yok - tarama calisir ama Telegram'a mesaj gitmez")
    log(f"7/24 calistirici basladi ({socket.gethostname()}) - tarama {TARAMA_ARALIGI_SN // 60} dk'da bir, "
        f"Sanal Trader saatte bir")
    son_trader_saati = None

    while True:
        tur_basi = time.time()
        guncel_kodu_cek()

        nabiz_yaz("live_scan")
        kod = calistir([sys.executable, "scripts/live_scan.py"], KOK, 600)
        if kod != 0:
            log(f"live_scan.py hata kodu {kod}")
        kaydet_ve_gonder(["data/state/last_signal.json", NABIZ_GIT], "sinyal durumu guncellendi [sunucu] [skip ci]")

        simdi = datetime.now(timezone.utc)
        saat_anahtari = simdi.strftime("%Y%m%d%H")
        if simdi.minute >= SANAL_TRADER_DAKIKASI and son_trader_saati != saat_anahtari:
            nabiz_yaz("sanal_trader")
            kod = calistir([sys.executable, "sanal_trader.py", "--once"], PANEL, 1800)
            if kod != 0:
                log(f"sanal_trader.py hata kodu {kod}")
            kaydet_ve_gonder(["kaan_trade_panel/cikti/sanal_trader/", NABIZ_GIT],
                             f"Sanal trader guncellemesi [sunucu] {simdi:%Y-%m-%dT%H:%M:%SZ}")
            son_trader_saati = saat_anahtari

        time.sleep(max(5, TARAMA_ARALIGI_SN - (time.time() - tur_basi)))


if __name__ == "__main__":
    main()
