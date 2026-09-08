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

from core.risk import suggest_leverage
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
                           side: str, price: float, bar_time,
                           stop_loss: float | None = None, take_profit: float | None = None,
                           risk_per_trade_pct: float = 1.5, max_leverage: float = 10.0) -> str:
    arrow = {"LONG": "\U0001F7E2 LONG", "SHORT": "\U0001F534 SHORT", "FLAT": "⚪ FLAT (kapat)"}[side]
    lines = [
        f"*{arrow}*  `{symbol}` ({provider}, {timeframe})",
        f"Strateji: `{strategy}`",
        f"Giris (guncel fiyat): `{price:.6g}`",
    ]

    # FLAT (pozisyon kapatma) sinyalinde giris/stop/kaldirac anlamsiz -
    # sadece kapat bilgisi yeterli.
    if side != "FLAT":
        if stop_loss is not None:
            lines.append(f"Stop: `{stop_loss:.6g}`")
            sizing = suggest_leverage(price, stop_loss, risk_per_trade_pct, max_leverage)
            if sizing is not None:
                lines.append(
                    f"Onerilen kaldirac: `{sizing.suggested_leverage:.1f}x` "
                    f"(stop mesafesi %{sizing.stop_distance_pct:.2f}, "
                    f"islem basi risk %{sizing.risk_per_trade_pct:g})"
                )
        else:
            lines.append("Stop: _bu strateji sabit stop kullanmiyor (iz suren/dinamik) - panelden takip et_")
        if take_profit is not None:
            lines.append(f"Hedef: `{take_profit:.6g}`")

    lines.append(f"Mum zamani: `{format_istanbul(bar_time)}`")
    lines.append("_Bu otomatik bir sinyaldir, yatirim tavsiyesi degildir. "
                  "Kaldirac onerisi sadece stop mesafesine gore pozisyon buyuklugu hesabidir, "
                  "garanti degildir._")
    return "\n".join(lines)
