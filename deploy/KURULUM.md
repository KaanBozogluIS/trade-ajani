# 7/24 Sunucu Kurulumu

## Neden?

Botlar şu an GitHub Actions'ın zamanlayıcısıyla çalışıyor. Ölçümler, GitHub'ın bu işleri ciddi şekilde geciktirdiğini gösteriyor:

| İş | Ayar | Gerçekte |
|---|---|---|
| Telegram sinyal taraması | 5 dakikada bir | ortalama ~50 dakikada bir, 7 saate varan boşluklar |
| Sanal Trader | saatte bir | ortalama ~1.5 saatte bir, 8 saate varan boşluklar |

Sürekli açık bir makinede `scripts/sunucu_7x24.py` bu işleri **gerçekten** 5 dakikada bir ve saatte bir çalıştırır.

**Geçiş güvenli.** Sunucu çalıştığı sürece GitHub iş akışları kendilerini otomatik olarak atlar. Sunucu durursa 20 dakika içinde GitHub yedek olarak devreye girer. Hiçbir şeyi kapatıp açman gerekmez.

## Adım 1: Bir makine seç

Herhangi biri yeterli (1 GB RAM ve Ubuntu yeter):

- **Oracle Cloud "Always Free"**: ücretsiz, ama hesap açarken kredi kartı doğrulaması ister. Bölge olarak Frankfurt/Amsterdam gibi Avrupa'da bir yer seç.
- **Ucuz VPS** (Hetzner, Contabo vb.): ayda ~4-5 €, en kolay seçenek.
- **Evde bir Raspberry Pi**: 7/24 açık kalabiliyorsa.

> Kendi bilgisayarın uygun değil, çünkü kapandığında botlar da durur.

Makineyi açınca sana bir **IP adresi** ve bir **kullanıcı adı** verilir (genelde `ubuntu`). Windows'ta PowerShell'i açıp bağlan:

```
ssh ubuntu@SUNUCU_IP_ADRESI
```

## Adım 2: Depoyu indir

Sunucuda şu iki komutu çalıştır:

```
git clone https://github.com/KaanBozogluIS/trade-ajani.git
cd trade-ajani
```

## Adım 3: Deploy key (sunucunun GitHub'a kayıt yazabilmesi için)

Sunucu her turdan sonra sonuçları GitHub'a gönderir (panel ve geçmiş bu sayede güncel kalır). Bunun için sunucuya **sadece bu depoya** yazma izni veren bir anahtar gerekir.

1. Sunucuda anahtar üret (sorulara Enter'a basarak geç):
   ```
   ssh-keygen -t ed25519 -C "trade-ajani-sunucu" -f ~/.ssh/id_ed25519
   cat ~/.ssh/id_ed25519.pub
   ```
2. Ekrana çıkan `ssh-ed25519 ...` satırını kopyala.
3. GitHub'da depoyu aç → **Settings → Deploy keys → Add deploy key**:
   - Title: `sunucu`
   - Key: kopyaladığın satır
   - **"Allow write access" kutusunu işaretle**
   - Add key
4. Sunucuda, depoyu bu anahtarla kullanacak şekilde ayarla ve GitHub'a bir kez bağlan:
   ```
   cd ~/trade-ajani
   git remote set-url origin git@github.com:KaanBozogluIS/trade-ajani.git
   ssh -T git@github.com
   ```
   `Are you sure you want to continue connecting?` sorusuna `yes` yaz. "Hi KaanBozogluIS/trade-ajani! You've successfully authenticated" görürsen tamam.

## Adım 4: Kurulumu çalıştır

```
cd ~/trade-ajani
bash deploy/kurulum.sh
```

Betik kütüphaneleri kurar ve Telegram bilgilerini sorar. Bunlar, GitHub'daki `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` secret'larıyla aynı değerlerdir; bilgisayarındaki `Trade-ajanı\.env` dosyasında da yazıyorlar. Son olarak botu, sunucu her açıldığında otomatik başlayacak şekilde kurar.

## Adım 5: Çalıştığını kontrol et

```
sudo systemctl status trade-ajani      # "active (running)" yazmalı
journalctl -u trade-ajani -f           # canlı kayıtlar (çıkmak için Ctrl+C)
```

GitHub'da **Actions** sekmesinde, sonraki çalışmaların "Sunucu çalışıyor mu?" adımında `sunucu calisiyor, GitHub bu turu ATLIYOR` yazmalı.

## Günlük kullanım

| Ne yapmak istiyorsun | Komut |
|---|---|
| Durdur (GitHub ~20 dk içinde devralır) | `sudo systemctl stop trade-ajani` |
| Yeniden başlat | `sudo systemctl restart trade-ajani` |
| Son 100 satır kayıt | `journalctl -u trade-ajani -n 100` |

Kod güncellemeleri sunucuya **otomatik** gelir: her tur başında `git pull` yapılır. Tek istisna `scripts/sunucu_7x24.py` dosyasının kendisi; o değişirse servisi `sudo systemctl restart trade-ajani` ile yeniden başlat.
