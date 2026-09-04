"""Telegram bot ile bildirim gonderme.

Kurulum (bir defalik):
  1) Telegram'da @BotFather'a yaz, /newbot ile bot olustur, token'i al.
  2) Botuna Telegram'dan bir mesaj at (herhangi bir sey).
  3) https://api.telegram.org/bot<TOKEN>/getUpdates adresini tarayicida ac,
     donen JSON icindeki "chat":{"id": ...} degerini not et.
  4) .env dosyasina TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID olarak yaz.
"""

from __future__ import annotations

import os

import requests

from core.tz import format_istanbul

_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str, parse_mode: str = "Markdown") -> bool:
        if not self.configured:
            print("[telegram] TOKEN/CHAT_ID ayarli degil, mesaj gonderilmedi:\n" + text)
            return False
        url = _API.format(token=self.token)
        try:
            r = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode},
                timeout=15,
            )
            if r.status_code != 200:
                print(f"[telegram] gonderim basarisiz ({r.status_code}): {r.text[:300]}")
                return False
            return True
        except requests.RequestException as exc:
            print(f"[telegram] istek hatasi: {exc}")
            return False


def format_signal_message(*, provider: str, symbol: str, timeframe: str, strategy: str,
                           side: str, price: float, bar_time) -> str:
    arrow = {"LONG": "\U0001F7E2 LONG", "SHORT": "\U0001F534 SHORT", "FLAT": "⚪ FLAT (kapat)"}[side]
    return (
        f"*{arrow}*  `{symbol}` ({provider}, {timeframe})\n"
        f"Strateji: `{strategy}`\n"
        f"Fiyat: `{price:.6g}`\n"
        f"Mum zamani: `{format_istanbul(bar_time)}`\n"
        f"_Bu otomatik bir sinyaldir, yatirim tavsiyesi degildir._"
    )
