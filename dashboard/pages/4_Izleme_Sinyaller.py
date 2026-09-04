"""Izleme listesi (config/watchlist.yaml) ve son sinyal durumu (data/state/last_signal.json).

Panelden manuel olarak 'taramayi simdi calistir' da tetiklenebilir - bu,
scripts/live_scan.py ile aynı mantigi calistirir ve degisen sinyalde
Telegram'a bildirim gonderir (dry-run degilse).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

from core.tz import format_istanbul

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="İzleme & Sinyaller", page_icon="🔔", layout="wide")
st.title("🔔 İzleme Listesi & Sinyaller")

import os
telegram_ok = bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(os.getenv("TELEGRAM_CHAT_ID"))
st.info("✅ Telegram bildirimleri yapılandırılmış." if telegram_ok
        else "⚠️ Telegram henüz yapılandırılmamış — `.env` dosyasına "
             "TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID girin (kurulum adımları README'de).")

WATCHLIST_PATH = ROOT / "config" / "watchlist.yaml"
STATE_PATH = ROOT / "data" / "state" / "last_signal.json"

if not WATCHLIST_PATH.exists():
    st.warning("`config/watchlist.yaml` yok. Örnek dosyayı kopyalayıp doldurun: "
               "`config/watchlist.yaml.example` → `config/watchlist.yaml`")
    st.stop()

watchlist = yaml.safe_load(WATCHLIST_PATH.read_text(encoding="utf-8")) or []
state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}

st.subheader("İzlenen kombinasyonlar")
rows = []
for e in watchlist:
    key = f"{e['provider']}:{e['symbol']}:{e['timeframe']}:{e['strategy']}"
    s = state.get(key, {})
    rows.append({
        "Kaynak": e["provider"], "Sembol": e["symbol"], "Zaman Dilimi": e["timeframe"],
        "Strateji": e["strategy"], "Son Sinyal": {1: "🟢 LONG", -1: "🔴 SHORT", 0: "⚪ FLAT", None: "—"}.get(s.get("signal")),
        "Son Fiyat": s.get("price"),
        "Son Mum (TR saati)": format_istanbul(s["time"]) if s.get("time") else "—",
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()
col1, col2 = st.columns([1, 3])
with col1:
    dry_run = st.checkbox("Dry-run (Telegram'a gönderme, sadece göster)", value=True)
    if st.button("▶ Taramayı şimdi çalıştır"):
        cmd = [sys.executable, str(ROOT / "scripts" / "live_scan.py")]
        if dry_run:
            cmd.append("--dry-run")
        with st.spinner("Kontrol ediliyor..."):
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        with col2:
            st.code(proc.stdout or proc.stderr, language="text")
        st.rerun()

st.divider()
st.caption(
    "🌐 Sürekli tarama artık **GitHub Actions**'ta çalışıyor (`.github/workflows/live_scan.yml`, "
    "her 30 dakikada bir) — laptop kapalıyken de sinyaller gelmeye devam eder. "
    "GitHub'daki *Actions* sekmesinden çalışma geçmişini görebilirsin."
)
