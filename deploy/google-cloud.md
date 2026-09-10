# Google Cloud "Always Free" da botni ishga tushirish

Bot polling rejimida — faqat **chiquvchi** internet kerak. Port, domen, HTTPS
kerak emas.

## 0. Nima bepul (Always Free, sinov emas — doimiy)

- **1 ta `e2-micro` VM** har oy, quyidagi regionlardan birida:
  `us-west1` (Oregon), `us-central1` (Iowa), `us-east1` (South Carolina)
- 30 GB standart disk (SSD emas), 1 GB/oy Shimoliy Amerikadan chiquvchi trafik
  (bu bot oyiga bir necha MB ishlatadi)
- Ro'yxatdan o'tishda **bank kartasi** kerak. Yangi akkaunt $300 / 90 kun
  bonus oladi, lekin `e2-micro` bonus tugagach ham bepul qoladi.

> ⚠️ Kutilmagan to'lovdan saqlanish uchun **Budget alert** ($1) qo'ying
> (3-qadam). `e2-micro` + 30 GB standart disk doirasida hisob $0 bo'ladi.

## 1. Akkaunt va billing (brauzerda, bir marta)

1. <https://console.cloud.google.com> — Google akkaunt bilan kiring.
2. **Billing → Create account** → karta qo'shing.
3. **Billing → Budgets & alerts → Create budget** → miqdor `1`, 50/90/100%
   xabarnoma. (Ixtiyoriy, lekin tavsiya.)
4. Loyiha: yuqoridagi "My First Project" yetadi, yoki
   **Create project** (masalan `vocab-bot`).

## 2. `gcloud` bilan kirish (shu sessiyada)

Claude Code sessiyasida:

```
! gcloud auth login --no-launch-browser
```

Chiqqan havolani telefon/kompyuter brauzerida oching → ruxsat bering →
kodni terminaldagi so'rovга qaytaring. So'ng:

```
gcloud config set project <PROJECT_ID>
gcloud services enable compute.googleapis.com
```

Qolganini Claude bajaradi (3–6 qadamlar avtomatlashtirilgan).

## 3. VM yaratish

```bash
gcloud compute instances create vocab-bot \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard
```

## 4. Kodni ko'chirish

Telefon o'chsa ham progress yo'qolmasligi uchun **`vocab.db` ni ham** yuboramiz.
Avval telefondagi botni to'xtating (`./stop.sh`) — bitta token bilan ikki
instansiya polling qilsa Telegram `Conflict` beradi.

```bash
gcloud compute scp --recurse --zone=us-central1-a \
  ./german-uzbek-vocab-bot vocab-bot:~/
```

## 5. O'rnatish (VM ichida)

```bash
gcloud compute ssh vocab-bot --zone=us-central1-a
```

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv
cd ~/german-uzbek-vocab-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# .env allaqachon ko'chirilgan (BOT_TOKEN ichida). Tekshiring: cat .env
.venv/bin/python bot.py     # "Bot ishga tushdi (polling)" -> Ctrl+C
```

## 6. systemd xizmati (avtorestart + reboot'da avtostart)

```bash
sudo cp deploy/vocab-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/vocab-bot.service
#   User=<sizning-login>   (gcloud SSH login, `whoami`)
#   WorkingDirectory=/home/<login>/german-uzbek-vocab-bot
#   EnvironmentFile=/home/<login>/german-uzbek-vocab-bot/.env
#   ExecStart=/home/<login>/german-uzbek-vocab-bot/.venv/bin/python bot.py

sudo systemctl daemon-reload
sudo systemctl enable --now vocab-bot
systemctl status vocab-bot
journalctl -u vocab-bot -f
```

## 7. Yangilash

```bash
gcloud compute scp --recurse --zone=us-central1-a \
  ./german-uzbek-vocab-bot/bot.py ./german-uzbek-vocab-bot/data \
  vocab-bot:~/german-uzbek-vocab-bot/
gcloud compute ssh vocab-bot --zone=us-central1-a --command \
  'sudo systemctl restart vocab-bot'
```

`vocab.db` VM'da `WorkingDirectory` ichida — yangilashda tegmang. Zaxira:

```bash
gcloud compute scp --zone=us-central1-a \
  vocab-bot:~/german-uzbek-vocab-bot/vocab.db ./vocab.db.backup
```

## VM boshqaruvi

```bash
gcloud compute instances stop vocab-bot  --zone=us-central1-a   # to'xtatish
gcloud compute instances start vocab-bot --zone=us-central1-a   # yoqish
gcloud compute instances delete vocab-bot --zone=us-central1-a  # o'chirish
```
