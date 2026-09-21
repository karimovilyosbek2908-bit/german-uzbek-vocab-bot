"""Nemis–o'zbek so'z boyligi boti — handler'lar va ishga tushirish.

Buyruqlar:
    /start      — ro'yxatdan o'tish va yordam
    /flashcard  — kartochka (flashcard) sessiyasi
    /test       — variantli test sessiyasi
    /takror     — muddati kelgan so'zlar soni + kartochka sessiyasi
    /stats      — o'rganish statistikasi
    /help       — buyruqlar ro'yxati

Ma'lumotlar bazasi chaqiruvlari sinxron (database.py). Shaxsiy bot uchun yuk
kichik bo'lgani sababli ular event-loop'ni sezilarli bloklamaydi.
"""

from __future__ import annotations

import logging
import os
import random

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db
import srs
from srs import Rating

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("vocab-bot")

SESSION_SIZE = 10          # bitta sessiyadagi so'zlar soni
TEST_OPTIONS = 4           # testdagi javob variantlari soni

# Xabar maydoni ostidagi doimiy tugmalar paneli
BTN_FLASHCARD = "📇 Kartochka"
BTN_TEST = "🧩 Test"
BTN_STATS = "📊 Statistika"
BTN_TAKROR = "🔁 Takror"
MAIN_KB = ReplyKeyboardMarkup(
    [[BTN_FLASHCARD, BTN_TEST], [BTN_TAKROR, BTN_STATS]],
    resize_keyboard=True,
)

# Telegram buyruqlar menyusi ("/" tugmasi)
BOT_COMMANDS = [
    BotCommand("flashcard", "Kartochka sessiyasi"),
    BotCommand("test", "Variantli test"),
    BotCommand("takror", "Bugun takrorlanadigan so'zlar"),
    BotCommand("stats", "O'rganish statistikasi"),
    BotCommand("help", "Yordam"),
]


# --------------------------------------------------------------------------- #
#  Yordamchilar
# --------------------------------------------------------------------------- #
def _pos_uz(pos: str | None) -> str:
    return {
        "noun": "ot",
        "verb": "fe'l",
        "adj": "sifat",
        "adv": "ravish",
        "pron": "olmosh",
    }.get(pos or "", pos or "")


def _short_uz(uz: str, limit: int = 40) -> str:
    """Test tugmasi uchun qisqa yorliq: birinchi ma'no, kerak bo'lsa qisqartirilgan."""
    first = uz.split(";")[0].strip()
    first = first.lstrip("1) ").strip()  # "1) ma'no" -> "ma'no"
    return first if len(first) <= limit else first[: limit - 1] + "…"


def _card_text(word: dict, idx: int, total: int, revealed: bool) -> str:
    head = f"📇 Kartochka {idx}/{total}\n\n🇩🇪 <b>{word['de']}</b>"
    if not revealed:
        return head
    pos = _pos_uz(word.get("pos"))
    lines = [f"{head}  <i>{pos}</i>" if pos else head, f"🇺🇿 <b>{word['uz']}</b>"]
    if word.get("example_de"):
        lines.append(f"\n📝 {word['example_de']}")
        if word.get("example_uz"):
            lines.append(f"   <i>{word['example_uz']}</i>")
    return "\n".join(lines)


def _summary_text(session: dict) -> str:
    done = session["correct"] + session["wrong"]
    acc = round(session["correct"] / done * 100) if done else 0
    kind = "Kartochka" if session["mode"] == "flashcard" else "Test"
    return (
        f"🎉 <b>{kind} sessiyasi tugadi!</b>\n\n"
        f"✅ To'g'ri: {session['correct']}\n"
        f"❌ Xato: {session['wrong']}\n"
        f"🎯 Aniqlik: {acc}%\n\n"
        "Yana mashq qilish uchun /flashcard yoki /test.\n"
        "Umumiy holat — /stats."
    )


def _build_test_options(word: dict) -> list[dict]:
    """To'g'ri javob + 3 ta tasodifiy chalg'ituvchi variant (aralashtirilgan)."""
    pool = [w for w in db_all_words() if w["id"] != word["id"] and w["uz"] != word["uz"]]
    distractors = random.sample(pool, k=min(TEST_OPTIONS - 1, len(pool)))
    options = [word, *distractors]
    random.shuffle(options)
    return options


_ALL_WORDS_CACHE: list[dict] = []


def db_all_words() -> list[dict]:
    """words jadvalini bir marta o'qib, xotirada saqlaydi (test variantlari uchun)."""
    global _ALL_WORDS_CACHE
    if not _ALL_WORDS_CACHE:
        _ALL_WORDS_CACHE = [db.get_word(i) for i in db.get_all_word_ids()]
    return _ALL_WORDS_CACHE


# --------------------------------------------------------------------------- #
#  Sessiya boshqaruvi
# --------------------------------------------------------------------------- #
def _start_session(context: ContextTypes.DEFAULT_TYPE, user_id: int, mode: str) -> dict | None:
    due = db.get_due_words(user_id, limit=SESSION_SIZE)
    if not due:
        return None
    session = {
        "mode": mode,
        "queue": due,
        "pos": 0,
        "revealed": False,
        "correct": 0,
        "wrong": 0,
        "options": [],
    }
    context.user_data["session"] = session
    return session


def _current_word(session: dict) -> dict | None:
    if session["pos"] >= len(session["queue"]):
        return None
    return session["queue"][session["pos"]]


async def _render_current(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Joriy savolni chizadi (kartochka yoki test). Sessiya tugagan bo'lsa — xulosa."""
    session = context.user_data["session"]
    word = _current_word(session)
    total = len(session["queue"])
    idx = session["pos"] + 1

    send = _make_sender(update_or_query)

    if word is None:
        await send(_summary_text(session), reply_markup=None)
        context.user_data.pop("session", None)
        return

    if session["mode"] == "flashcard":
        text = _card_text(word, idx, total, session["revealed"])
        if session["revealed"]:
            kb = [[
                InlineKeyboardButton("🔴 Qayta", callback_data=f"ans:{int(Rating.Again)}"),
                InlineKeyboardButton("🟠 Qiyin", callback_data=f"ans:{int(Rating.Hard)}"),
                InlineKeyboardButton("🟢 Yaxshi", callback_data=f"ans:{int(Rating.Good)}"),
                InlineKeyboardButton("🔵 Oson", callback_data=f"ans:{int(Rating.Easy)}"),
            ]]
        else:
            kb = [[InlineKeyboardButton("👁 Javobni ko'rish", callback_data="reveal")]]
        await send(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    # test rejimi
    if not session["options"]:
        session["options"] = _build_test_options(word)
    text = (
        f"🧩 Test {idx}/{total}\n\n"
        f"Bu so'z nima degani?\n🇩🇪 <b>{word['de']}</b>"
    )
    kb = [
        [InlineKeyboardButton(_short_uz(opt["uz"]), callback_data=f"opt:{opt['id']}")]
        for opt in session["options"]
    ]
    await send(text, reply_markup=InlineKeyboardMarkup(kb))


def _make_sender(update_or_query):
    """Update (yangi xabar) yoki CallbackQuery (xabarni tahrirlash) uchun yagona interfeys."""
    if isinstance(update_or_query, Update):
        chat = update_or_query.effective_chat

        async def send(text, reply_markup):
            await chat.send_message(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        return send

    query = update_or_query

    async def send(text, reply_markup):
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return send


# --------------------------------------------------------------------------- #
#  Buyruq handler'lari
# --------------------------------------------------------------------------- #
HELP_TEXT = (
    "🇩🇪🇺🇿 <b>Nemis–o'zbek so'z boti</b>\n\n"
    "/flashcard — kartochka sessiyasi (so'zni ko'r, javobni tekshir)\n"
    "/test — variantli test\n"
    "/takror — bugun takrorlash kerak bo'lgan so'zlar\n"
    "/stats — o'rganish statistikasi\n"
    "/help — shu yordam\n\n"
    "Pastdagi tugmalardan ham foydalanishingiz mumkin. "
    f"Har sessiyada {SESSION_SIZE} tagacha so'z. Takrorlash FSRS algoritmi "
    "bo'yicha rejalashtiriladi — har so'z uchun aynan unutishga yaqin "
    "vaqtda eslatadi, ortiqcha takrorlarga vaqt sarflamaydi. Kartochkada "
    "javobni baholang: 🔴 Qayta / 🟠 Qiyin / 🟢 Yaxshi / 🔵 Oson."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    name = user.first_name or "do'stim"
    await update.effective_chat.send_message(
        f"Salom, {name}! 👋\n\n{HELP_TEXT}",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KB,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message(
        HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Doimiy tugmalar paneli (oddiy matn xabarlari) -> tegishli buyruq."""
    route = {
        BTN_FLASHCARD: cmd_flashcard,
        BTN_TEST: cmd_test,
        BTN_STATS: cmd_stats,
        BTN_TAKROR: cmd_takror,
    }
    handler = route.get((update.message.text or "").strip())
    if handler:
        await handler(update, context)


async def cmd_flashcard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    session = _start_session(context, user.id, "flashcard")
    if session is None:
        await update.effective_chat.send_message(
            "🎉 Hozircha takrorlash kerak bo'lgan so'z yo'q. Ertaga qaytib keling!"
        )
        return
    await _render_current(update, context)


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    session = _start_session(context, user.id, "test")
    if session is None:
        await update.effective_chat.send_message(
            "🎉 Hozircha takrorlash kerak bo'lgan so'z yo'q. Ertaga qaytib keling!"
        )
        return
    await _render_current(update, context)


async def cmd_takror(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    stats = db.get_stats(user.id)
    await update.effective_chat.send_message(
        f"📌 Bugun takrorlash uchun: <b>{stats['due']}</b> ta so'z "
        f"({stats['not_started']} yangi + {stats['due'] - stats['not_started']} takror).",
        parse_mode=ParseMode.HTML,
    )
    session = _start_session(context, user.id, "flashcard")
    if session is not None:
        await _render_current(update, context)


_STATE_UZ = {
    "new": "🆕 Yangi",
    "learning": "📖 O'rganilmoqda",
    "review": "🔁 Takrorlanmoqda",
    "relearning": "🔄 Qayta o'rganilmoqda",
}


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    s = db.get_stats(user.id)
    bars = "\n".join(
        f"  {label}: {'▮' * min(s['by_state'][key], 20) or '·'} {s['by_state'][key]}"
        for key, label in _STATE_UZ.items()
    )
    await update.effective_chat.send_message(
        f"📊 <b>Statistika</b>\n\n"
        f"So'zlar bazasi: {s['total_words']}\n"
        f"Boshlangan: {s['started']}\n"
        f"Uzoq muddatga o'zlashtirilgan: {s['mastered']}\n"
        f"Bugun takrorlash: {s['due']}\n\n"
        f"<b>FSRS holati</b>\n{bars}\n\n"
        f"Javoblar: ✅ {s['correct']} / ❌ {s['wrong']}  (aniqlik {s['accuracy']}%)",
        parse_mode=ParseMode.HTML,
    )


# --------------------------------------------------------------------------- #
#  Tugma (callback) handler'lari
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    session = context.user_data.get("session")

    if session is None:
        await query.edit_message_text("Sessiya tugagan. Yangi mashq: /flashcard yoki /test")
        return

    word = _current_word(session)
    if word is None:
        await query.edit_message_text(_summary_text(session), parse_mode=ParseMode.HTML)
        context.user_data.pop("session", None)
        return

    user_id = query.from_user.id

    if data == "reveal":
        session["revealed"] = True
        await _render_current(query, context)
        return

    if data.startswith("ans:"):
        rating = Rating(int(data.split(":", 1)[1]))
        correct = rating != Rating.Again
        _apply_answer(user_id, word, rating)
        session["correct" if correct else "wrong"] += 1
        session["pos"] += 1
        session["revealed"] = False
        await _render_current(query, context)
        return

    if data.startswith("opt:"):
        chosen_id = int(data.split(":", 1)[1])
        correct = chosen_id == word["id"]
        rating = Rating.Good if correct else Rating.Again
        _apply_answer(user_id, word, rating)
        session["correct" if correct else "wrong"] += 1
        await query.answer(
            "To'g'ri!" if correct else f"Noto'g'ri — {word['uz']}", show_alert=not correct
        )
        session["pos"] += 1
        session["options"] = []
        await _render_current(query, context)
        return


def _apply_answer(user_id: int, word: dict, rating: Rating) -> None:
    """FSRS holatini hisoblab, bazaga yozadi."""
    prev = db.get_progress(user_id, word["id"])
    correct = rating != Rating.Again
    cc = prev["correct_count"] if prev else 0
    wc = prev["wrong_count"] if prev else 0
    res = srs.review(
        rating,
        state=prev["state"] if prev else None,
        step=prev["step"] if prev else None,
        stability=prev["stability"] if prev else None,
        difficulty=prev["difficulty"] if prev else None,
        last_review=prev["last_review"] if prev else None,
    )
    db.upsert_progress(
        user_id,
        word["id"],
        state=res.state,
        step=res.step,
        stability=res.stability,
        difficulty=res.difficulty,
        correct_count=cc + (1 if correct else 0),
        wrong_count=wc + (0 if correct else 1),
        next_review=res.next_review,
        last_review=res.last_review,
    )


# --------------------------------------------------------------------------- #
#  Ishga tushirish
# --------------------------------------------------------------------------- #
async def _post_init(app: Application) -> None:
    """Bot ishga tushgach — buyruqlar menyusini ro'yxatdan o'tkazish."""
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Buyruqlar menyusi o'rnatildi (%d ta).", len(BOT_COMMANDS))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler'da ushlanmagan xatoni logga yozadi va foydalanuvchini ogohlantiradi."""
    logger.exception("Handler xatosi", exc_info=context.error)
    chat = getattr(update, "effective_chat", None) if isinstance(update, Update) else None
    if chat is None:
        return
    try:
        await chat.send_message(
            "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring — /flashcard yoki /test.",
            reply_markup=MAIN_KB,
        )
    except Exception:
        logger.exception("Xato haqida xabar yuborib bo'lmadi")


def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit(
            "BOT_TOKEN topilmadi. .env.example ni .env deb nusxalab, tokeningizni yozing."
        )

    db.init_db()
    logger.info("Baza tayyor, so'zlar: %d", db.count_words())

    app = Application.builder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("flashcard", cmd_flashcard))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("takror", cmd_takror))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    logger.info("Bot ishga tushdi (polling).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
