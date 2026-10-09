#!/usr/bin/env bash
# Trade-ajani 7/24 sunucu kurulumu (Ubuntu 22.04/24.04 - Oracle Cloud, VPS, Raspberry Pi OS).
# Ayrintili anlatim: deploy/KURULUM.md
#
# Kullanim (depo ZATEN klonlanmis olmali, depo kokunden):
#   bash deploy/kurulum.sh
set -euo pipefail

DEPO="$(cd "$(dirname "$0")/.." && pwd)"
KULLANICI="$(whoami)"
cd "$DEPO"

echo ">> Sistem paketleri kuruluyor (python3-venv, git)..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip git

echo ">> Sanal ortam (.venv) olusturuluyor ve kutuphaneler kuruluyor..."
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt -r kaan_trade_panel/requirements-sanal-trader.txt

if [ ! -f .env ]; then
  echo ">> .env olusturuluyor - Telegram bilgilerini simdi gir (bos birakirsan mesaj gitmez):"
  read -r -p "TELEGRAM_BOT_TOKEN: " TOKEN
  read -r -p "TELEGRAM_CHAT_ID: " CHAT
  printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$TOKEN" "$CHAT" > .env
  chmod 600 .env
fi

echo ">> git kimligi ayarlaniyor (sadece bu depo icin)..."
git config user.name "trade-ajani-sunucu"
git config user.email "sunucu@users.noreply.github.com"

echo ">> Push yetkisi deneniyor..."
if ! git push --dry-run -q origin main 2>/dev/null; then
  echo "!! git push yetkisi YOK. deploy/KURULUM.md -> 'Adim 3: Deploy key' bolumunu (4. madde dahil) uygula, sonra bu betigi tekrar calistir."
  exit 1
fi

echo ">> systemd servisi kuruluyor (acilista otomatik baslar, cokerse yeniden baslar)..."
sed -e "s#__DEPO__#$DEPO#g" -e "s#__KULLANICI__#$KULLANICI#g" deploy/trade-ajani.service \
  | sudo tee /etc/systemd/system/trade-ajani.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now trade-ajani.service

echo
echo "TAMAM. Durum:   sudo systemctl status trade-ajani"
echo "      Kayitlar: journalctl -u trade-ajani -f"
