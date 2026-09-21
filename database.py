"""SQLite sxema va CRUD funksiyalari.

Uch jadval:
  * users    — Telegram foydalanuvchilari
  * words    — so'zlar bazasi (data/words.json dan yuklanadi)
  * progress — har bir (foydalanuvchi, so'z) juftligi uchun FSRS holati

Funksiyalar sinxron (sqlite3). Shaxsiy bot uchun yuk kichik, shuning uchun
bot.py ularni to'g'ridan-to'g'ri chaqiradi. Har bir chaqiruvda yangi ulanish
ochiladi — bu asyncio event-loop bilan xavfsiz ishlaydi.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = os.getenv("DB_PATH", "vocab.db")
WORDS_JSON_PATH = BASE_DIR / "data" / "words.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY,
    de          TEXT NOT NULL,
    uz          TEXT NOT NULL,
    pos         TEXT,
    example_de  TEXT,
    example_uz  TEXT
);

CREATE TABLE IF NOT EXISTS progress (
    user_id       INTEGER NOT NULL REFERENCES users(user_id),
    word_id       INTEGER NOT NULL REFERENCES words(id),
    state         INTEGER,             -- FSRS: 1=Learning,2=Review,3=Relearning; NULL=hali ko'rilmagan
    step          INTEGER,
    stability     REAL,
    difficulty    REAL,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count   INTEGER NOT NULL DEFAULT 0,
    next_review   TEXT NOT NULL,
    last_review   TEXT,
    PRIMARY KEY (user_id, word_id)
);

CREATE INDEX IF NOT EXISTS idx_progress_due
    ON progress(user_id, next_review);
"""

# Eski (Leitner) sxemadan FSRS'ga o'tish uchun qo'shiladigan ustunlar.
# `box` ustuni saqlab qolinadi (o'chirilmaydi) — eski qatorlar shunchaki
# state=NULL bilan "hali ko'rilmagan" deb qayta boshlanadi, keyingi javobda
# FSRS ularni qaytadan initsializatsiya qiladi. Ma'lumot yo'qolmaydi, faqat
# eski box progressi FSRS statistikasiga aylanmaydi.
_PROGRESS_MIGRATION_COLUMNS = (
    ("state", "INTEGER"),
    ("step", "INTEGER"),
    ("stability", "REAL"),
    ("difficulty", "REAL"),
)


def _migrate_progress_table(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(progress)").fetchall()}
    if not cols:
        return  # jadval hali yaratilmagan (yangi baza) — SCHEMA to'g'ridan-to'g'ri to'g'ri yaratadi
    for name, coltype in _PROGRESS_MIGRATION_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE progress ADD COLUMN {name} {coltype}")


# --------------------------------------------------------------------------- #
#  Ulanish va sxema
# --------------------------------------------------------------------------- #
def get_connection(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    """Yangi SQLite ulanishini qaytaradi (row_factory = Row)."""
    path = str(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Ko'p foydalanuvchi: o'quvchilar yozuvchini bloklamaydi, qulf kutilади (xato o'rniga)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(db_path: str | os.PathLike[str] | None = None) -> None:
    """Jadvallarni yaratadi (agar mavjud bo'lmasa) va so'zlarni yuklaydi."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate_progress_table(conn)
    load_words(db_path=db_path)


# --------------------------------------------------------------------------- #
#  words.json -> words jadvali
# --------------------------------------------------------------------------- #
def load_words(
    json_path: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> int:
    """words.json faylidagi so'zlarni jadvalga upsert qiladi.

    Mavjud yozuvlar yangilanadi (tarjima tuzatilsa ham progress saqlanadi).
    Qaytaradi: bazadagi jami so'zlar soni.
    """
    path = Path(json_path or WORDS_JSON_PATH)
    data = json.loads(path.read_text(encoding="utf-8"))
    words = data["words"] if isinstance(data, dict) else data

    rows = [
        (
            w["id"],
            w["de"],
            w["uz"],
            w.get("pos"),
            w.get("example_de"),
            w.get("example_uz"),
        )
        for w in words
    ]

    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO words (id, de, uz, pos, example_de, example_uz)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                de         = excluded.de,
                uz         = excluded.uz,
                pos        = excluded.pos,
                example_de = excluded.example_de,
                example_uz = excluded.example_uz
            """,
            rows,
        )
        (count,) = conn.execute("SELECT COUNT(*) FROM words").fetchone()
    return count


# --------------------------------------------------------------------------- #
#  users
# --------------------------------------------------------------------------- #
def ensure_user(
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> None:
    """Foydalanuvchini qo'shadi yoki username/first_name'ni yangilaydi."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name),
        )


# --------------------------------------------------------------------------- #
#  words (o'qish)
# --------------------------------------------------------------------------- #
def get_word(word_id: int, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
    return dict(row) if row else None


def get_all_word_ids(db_path: str | os.PathLike[str] | None = None) -> list[int]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT id FROM words ORDER BY id").fetchall()
    return [r["id"] for r in rows]


def count_words(db_path: str | os.PathLike[str] | None = None) -> int:
    with get_connection(db_path) as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM words").fetchone()
    return count


# --------------------------------------------------------------------------- #
#  progress
# --------------------------------------------------------------------------- #
def get_progress(
    user_id: int, word_id: int, db_path: str | os.PathLike[str] | None = None
) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM progress WHERE user_id = ? AND word_id = ?",
            (user_id, word_id),
        ).fetchone()
    return dict(row) if row else None


def upsert_progress(
    user_id: int,
    word_id: int,
    state: int,
    step: int | None,
    stability: float,
    difficulty: float,
    correct_count: int,
    wrong_count: int,
    next_review: str,
    last_review: str,
    db_path: str | os.PathLike[str] | None = None,
) -> None:
    """FSRS holatini yozadi (mavjud bo'lsa yangilaydi)."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO progress
                (user_id, word_id, state, step, stability, difficulty,
                 correct_count, wrong_count, next_review, last_review)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, word_id) DO UPDATE SET
                state         = excluded.state,
                step          = excluded.step,
                stability     = excluded.stability,
                difficulty    = excluded.difficulty,
                correct_count = excluded.correct_count,
                wrong_count   = excluded.wrong_count,
                next_review   = excluded.next_review,
                last_review   = excluded.last_review
            """,
            (
                user_id,
                word_id,
                state,
                step,
                stability,
                difficulty,
                correct_count,
                wrong_count,
                next_review,
                last_review,
            ),
        )


def get_due_words(
    user_id: int,
    limit: int = 10,
    today: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Takrorlash vaqti kelgan so'zlarni qaytaradi.

    Tartib (FSRS mantig'i):
      1. AVVAL muddati kelgan takrorlar (next_review <= bugun) — eng ko'p
         kutgani (eng eski muddat) oldin.
      2. Keyin — hali o'rganilmagan yangi so'zlar (id bo'yicha).
    Shunda muddati o'tgan takrorlar minglab yangi so'z ortida ko'milib qolmaydi.
    """
    today = today or date.today().isoformat()
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT w.*,
                   p.state                       AS state,
                   p.step                        AS step,
                   p.stability                   AS stability,
                   p.difficulty                  AS difficulty,
                   p.next_review                 AS next_review,
                   p.last_review                 AS last_review,
                   COALESCE(p.correct_count, 0)  AS correct_count,
                   COALESCE(p.wrong_count, 0)    AS wrong_count
            FROM words w
            LEFT JOIN progress p
                   ON p.word_id = w.id AND p.user_id = ?
            WHERE p.word_id IS NULL
               OR p.next_review <= ?
            ORDER BY (p.word_id IS NULL),                 -- 0 = takror, 1 = yangi
                     COALESCE(p.next_review, '9999-99'),  -- eng eski muddat oldin
                     w.id
            LIMIT ?
            """,
            (user_id, today, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# FSRS State: 1=Learning, 2=Review, 3=Relearning (database.py'da state=NULL -> "yangi")
_STATE_LABELS = {1: "learning", 2: "review", 3: "relearning"}
# Review holatida shu darajadagi barqarorlik (kun) — "uzoq muddatga o'zlashtirilgan" chegarasi
MASTERED_STABILITY_DAYS = 21


def get_stats(
    user_id: int,
    today: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Foydalanuvchi statistikasi: FSRS holat taqsimoti, jami, muddati kelgan, aniqlik."""
    today = today or date.today().isoformat()
    with get_connection(db_path) as conn:
        total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]

        state_rows = conn.execute(
            "SELECT state, COUNT(*) AS n FROM progress WHERE user_id = ? GROUP BY state",
            (user_id,),
        ).fetchall()
        by_state = {"new": 0, "learning": 0, "review": 0, "relearning": 0}
        for r in state_rows:
            by_state[_STATE_LABELS.get(r["state"], "new")] += r["n"]

        started = conn.execute(
            "SELECT COUNT(*) FROM progress WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        by_state["new"] += total_words - started

        mastered = conn.execute(
            """
            SELECT COUNT(*) FROM progress
            WHERE user_id = ? AND state = 2 AND stability >= ?
            """,
            (user_id, MASTERED_STABILITY_DAYS),
        ).fetchone()[0]

        due = conn.execute(
            "SELECT COUNT(*) FROM progress WHERE user_id = ? AND next_review <= ?",
            (user_id, today),
        ).fetchone()[0]
        # o'rganilmaganlar ham "muddati kelgan" hisoblanadi
        due += total_words - started

        agg = conn.execute(
            """
            SELECT COALESCE(SUM(correct_count), 0) AS c,
                   COALESCE(SUM(wrong_count), 0)   AS w
            FROM progress WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    answered = agg["c"] + agg["w"]
    accuracy = round(agg["c"] / answered * 100) if answered else 0

    return {
        "total_words": total_words,
        "started": started,
        "not_started": total_words - started,
        "mastered": mastered,
        "due": due,
        "by_state": by_state,
        "correct": agg["c"],
        "wrong": agg["w"],
        "accuracy": accuracy,
    }


# --------------------------------------------------------------------------- #
#  CLI: `python database.py` -> bazani tayyorlab, qisqa hisobot beradi
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    init_db()
    print(f"Baza tayyor: {DEFAULT_DB_PATH}")
    print(f"So'zlar soni: {count_words()}")
