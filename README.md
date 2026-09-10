# german-uzbek-vocab-bot

Nemis–o'zbek so'z boyligini oshirish uchun Telegram bot. ~4370 ta nemis so'zini
(«100 kun qoidasi» kursidan olingan, A1–B1) kartochka (flashcard) va test
o'yinlari orqali, Leitner (spaced repetition) tizimi asosida takrorlash bilan
o'rgatadi.

## Texnik stack

- Python 3.10+
- [python-telegram-bot](https://docs.python-telegram-bot.org/) v20 (async)
- SQLite (fayl asosida, alohida server kerak emas)
- python-dotenv

Termux'da ishlashga moslangan — og'ir kutubxonalar ishlatilmaydi.

## Loyiha tuzilmasi

```
german-uzbek-vocab-bot/
├── bot.py            # asosiy fayl, handler'lar
├── database.py       # SQLite funksiyalari
├── srs.py            # Leitner algoritmi
├── data/words.json   # so'zlar bazasi
├── .env              # BOT_TOKEN (gitignore'da)
├── requirements.txt
└── README.md
```

## O'rnatish va ishga tushirish

### 1. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

Termux'da: `pkg install python` dan keyin yuqoridagi buyruq. Faqat `httpx`
kabi sof-Python paketlar tortiladi, C-kompilyatsiya shart emas.

### 2. Bot tokenini olish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing.
2. `/newbot` → nom va username bering.
3. Berilgan tokenni nusxalang (`123456789:ABC...` ko'rinishida).

### 3. `.env` faylini sozlash

```bash
cp .env.example .env
```

`.env` ichida `BOT_TOKEN` qiymatini o'z tokeningizga almashtiring. Ixtiyoriy —
`DB_PATH` orqali baza fayli nomini o'zgartirish mumkin (standart: `vocab.db`).

### 4. Bazani tekshirish (ixtiyoriy)

```bash
python database.py     # jadvallarni yaratadi, words.json'dan 100 so'z yuklaydi
python srs.py          # Leitner algoritmi namoyishi
```

### 5. Botni ishga tushirish

Oldi rejimda (test uchun):

```bash
python bot.py
```

Fon rejimida (terminal yopilsa ham ishlaydi):

```bash
./run.sh      # ishga tushiradi, log -> bot.log, PID -> bot.pid
./stop.sh     # to'xtatadi
tail -f bot.log
```

Konsolda `Bot ishga tushdi (polling)` chiqsa — tayyor. Telegram'da botingizga
`/start` yuboring.

### 6. Telefon o'chib yonganda avtomatik ishga tushishi (ixtiyoriy)

**Termux:Boot** ilovasini o'rnating (F-Droid). So'ng Termux'da:

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/vocab-bot <<'SH'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
proot-distro login <distro-nomi> -- bash -lc 'cd ~/vocab-bot/german-uzbek-vocab-bot && ./run.sh'
SH
chmod +x ~/.termux/boot/vocab-bot
```

`<distro-nomi>` — `proot-distro list` dagi o'rnatilgan distro (masalan `debian`).
proot-distro ishlatmasangiz, `proot-distro login ...` qatorini olib tashlab,
to'g'ridan-to'g'ri `cd ... && ./run.sh` yozing.

> Android (ayniqsa HONOR/Huawei) Termux'ni fonda o'ldiradi. Barqaror ishlashi
> uchun: Termux'da `termux-wake-lock`, batareya optimizatsiyasini o'chirish,
> "App launch" da qo'lda ruxsat berish. To'liq ishonchli yechim — botni
> serverga ko'chirish.

### Serverga joylashtirish (tavsiya etiladi)

Bot toza Python + SQLite, polling rejimida — faqat chiquvchi internet kerak.
Har qanday doim yoniq mashinada ishlaydi. Oracle Cloud "Always Free" (bepul,
24/7) uchun bosqichma-bosqich yo'riqnoma: [`deploy/oracle-cloud.md`](deploy/oracle-cloud.md).
systemd xizmati: [`deploy/vocab-bot.service`](deploy/vocab-bot.service).

## Buyruqlar

| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Ro'yxatdan o'tish + yordam |
| `/flashcard` | Kartochka sessiyasi: so'zni ko'r → javobni och → «Bildim / Bilmadim» |
| `/test` | Variantli test: 4 ta javobdan to'g'risini tanlash |
| `/takror` | Bugun takrorlanadigan so'zlar soni + kartochka sessiyasi |
| `/stats` | Box taqsimoti, o'zlashtirilgan so'zlar, aniqlik foizi |
| `/help` | Buyruqlar ro'yxati |

Har sessiyada 10 tagacha so'z beriladi (`bot.py` → `SESSION_SIZE`).

## Leitner (SRS) tizimi

Har bir so'z 1–5 «box»da bo'ladi. Box oraliqlari: 1→1 kun, 2→2, 3→4, 4→7,
5→15 kun. To'g'ri javob so'zni bir box yuqoriga ko'taradi, xato javob 1-boxga
qaytaradi. `get_due_words` avval umuman o'rganilmagan so'zlarni, so'ng muddati
kelganlarini (box'i pasti oldin) beradi.

## So'zlar bazasi

`data/words.json` — «100 kun qoidasi.pdf» dan avtomatik ajratib olingan
(~4370 so'z, 100 kun, kirill tarjimalar lotinga o'girilgan). Har yozuv:
`id`, `de` (artikl bilan), `uz`, `pos`, `day`, `example_de/uz` (kunlik dialog,
faqat har kunning birinchi so'zida). `example_de/uz` bo'sh bo'lishi mumkin.

Yangi so'z qo'shish: `words` massiviga obyekt qo'shing (`id` ketma-ket).
Keyingi ishga tushirishda `load_words` uni bazaga upsert qiladi.

> ⚠️ `id` qiymatlarini o'zgartirmang — `progress` jadvali `word_id` orqali
> bog'langan. Tartibni buzsangiz mavjud foydalanuvchi progressi chalkashadi.

## Ishlab chiqish bosqichlari

- [x] 1. Loyiha strukturasi + requirements.txt
- [x] 2. data/words.json — dastlab 100 ta test so'zi
- [x] 3. database.py — SQLite sxema va CRUD
- [x] 4. srs.py — Leitner box logikasi
- [x] 5. bot.py — /start, /flashcard, /test, /takror, /stats handlerlari
- [x] 6. Test qilish yo'riqnomasi
- [x] 7. data/words.json — «100 kun qoidasi» dan ~4370 so'z
- [~] 8. Tarjimalarni ko'rib chiqish
      - [x] OCR/format tozalash: 167 yozuv (probel-apostrof `bo 'lmoq`→`bo'lmoq`,
        bo'lingan so'zlar, nemis qo'shtirnoq `„…"`→`«…»`, ruscha transliteratsiya
        qoldiqlari olib tashlandi, ko'p ma'noli izohlar `1) … ; 2) …` ko'rinishiga
        keltirildi)
      - [ ] Mazmuniy tekshiruv: de↔uz mosligini qo'lda ko'rish (namuna asosida)
