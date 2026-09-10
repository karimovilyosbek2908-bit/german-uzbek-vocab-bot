# Oracle Cloud "Always Free" da botni ishga tushirish

Bot polling rejimida ishlaydi — faqat **chiquvchi** internet kerak.
Port ochish, domen, HTTPS — hech biri kerak emas.

## 0. Nima bepul
- **Always Free** (doim, sinov muddati emas): kichik VM'lar
  - AMD `VM.Standard.E2.1.Micro` — 1 GB RAM, 1/8 CPU (bu bot uchun yetarli, olish oson)
  - yoki ARM `Ampere A1` — 4 vCPU / 24 GB gacha (kuchliroq, lekin ba'zi
    regionlarda "out of capacity" chiqadi)
- 10 TB/oy chiquvchi trafik, 200 GB disk
- Ro'yxatdan o'tishda **bank kartasi** identifikatsiya uchun so'raladi
  (kichik vaqtinchalik ushlab turish, pul yechilmaydi)

> ⚠️ Oracle 7 kun davomida CPU < 10% bo'lgan Always Free instansiyalarni
> qaytarib olishi mumkin. Bu bot juda kam yuk beradi — ehtiyot bo'lish uchun
> instansiya sozlamalarida bu xatti-harakatni o'chirib qo'ying yoki
> vaqti-vaqti bilan kirib turing.

## 1. VM yaratish
1. cloud.oracle.com → **Compute → Instances → Create instance**
2. Image: **Canonical Ubuntu 22.04** (yoki 24.04)
3. Shape: **Always Free-eligible** belgisi borini tanlang (E2.1.Micro)
4. **SSH kalit**: kompyuteringizdagi ochiq kalitni qo'ying
   (`~/.ssh/id_ed25519.pub`; bo'lmasa: `ssh-keygen -t ed25519`)
5. Create → bir-ikki daqiqada **Public IP** paydo bo'ladi

## 2. Ulanish
```bash
ssh ubuntu@<PUBLIC_IP>
```

## 3. Muhitni tayyorlash
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git
```

## 4. Kodni ko'chirish
GitHub'da bo'lsa:
```bash
git clone <repo-url> ~/german-uzbek-vocab-bot
```
yoki lokaldan:
```bash
scp -r german-uzbek-vocab-bot ubuntu@<PUBLIC_IP>:~/
```

## 5. O'rnatish
```bash
cd ~/german-uzbek-vocab-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env        # BOT_TOKEN ni yozing
```

Tez tekshiruv:
```bash
.venv/bin/python bot.py     # "Bot ishga tushdi (polling)" -> Ctrl+C
```

## 6. systemd xizmati (avtorestart + reboot'da avtostart)
```bash
sudo cp deploy/vocab-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/vocab-bot.service
#   - venv ishlatgan bo'lsangiz ExecStart qatorini .venv variantiga o'zgartiring
#   - User / WorkingDirectory / yo'llarni tekshiring

sudo systemctl daemon-reload
sudo systemctl enable --now vocab-bot
```

## 7. Boshqaruv
```bash
systemctl status vocab-bot           # holati
journalctl -u vocab-bot -f           # jonli log
sudo systemctl restart vocab-bot     # qayta ishga tushirish
sudo systemctl stop vocab-bot        # to'xtatish
```

## Yangilash
```bash
cd ~/german-uzbek-vocab-bot
git pull                             # yoki yangi fayllarni scp bilan
.venv/bin/pip install -r requirements.txt
sudo systemctl restart vocab-bot
```

`vocab.db` (foydalanuvchi progressi) `WorkingDirectory` ichida saqlanadi —
yangilashda o'chib ketmaydi. Zaxira: shu faylni vaqti-vaqti bilan nusxalang.
