"""GitHub Actions icin: 7/24 sunucu (scripts/sunucu_7x24.py) calisiyor mu?

data/state/sunucu_nabiz.json son ESIK_DAKIKA icinde guncellendiyse sunucu
calisiyor demektir -> GITHUB_OUTPUT'a atla=true yazilir ve is akisi kendini
atlar (ayni portfoyu/sinyal durumunu iki yer ayni anda degistirmesin).
Nabiz yoksa ya da eskiyse atla=false -> GitHub yedek olarak calisir.
Sadece standart kutuphane kullanir (pip kurulumundan ONCE calisir).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ESIK_DAKIKA = 20
NABIZ = Path(__file__).resolve().parents[1] / "data" / "state" / "sunucu_nabiz.json"

atla = False
try:
    veri = json.loads(NABIZ.read_text(encoding="utf-8"))
    dakika = (datetime.now(timezone.utc) - datetime.fromisoformat(veri["zaman"])).total_seconds() / 60
    atla = dakika < ESIK_DAKIKA
    print(f"Sunucu nabzi: {dakika:.0f} dk once ({veri.get('makine')}) -> "
          f"{'sunucu calisiyor, GitHub bu turu ATLIYOR' if atla else 'eski, GitHub yedek olarak calisiyor'}")
except FileNotFoundError:
    print("Sunucu nabzi yok -> GitHub calistiriyor")
except Exception as e:
    print(f"Nabiz okunamadi ({e}) -> GitHub calistiriyor")

cikti = os.environ.get("GITHUB_OUTPUT")
if cikti:
    with open(cikti, "a", encoding="utf-8") as f:
        f.write(f"atla={'true' if atla else 'false'}\n")
