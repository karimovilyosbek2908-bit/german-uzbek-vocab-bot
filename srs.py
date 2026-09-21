"""FSRS (Free Spaced Repetition Scheduler) integratsiyasi.

`py-fsrs` kutubxonasidagi rasmiy algoritmni ishlatadi: har bir so'z uchun
stability (barqarorlik) va difficulty (qiyinlik) hisoblab, keyingi
takrorlash sanasini "eslab qolish ehtimoli ~90%" nuqtasiga moslab beradi.

Bot bir kunlik sessiyalar bilan ishlaydi (real vaqtli push yo'q), shuning
uchun FSRS'ning daqiqalik learning/relearning bosqichlari o'chirilgan —
har javob to'g'ridan-to'g'ri kunlik Review holatiga o'tadi.

Baholash (Rating):
    1 Again (qayta) — butunlay unutilgan, ertaga qaytadan ko'rsatiladi
    2 Hard  (qiyin) — to'g'ri, lekin qiynalib
    3 Good  (yaxshi) — to'g'ri, normal
    4 Easy  (oson)  — to'g'ri, juda oson

Modul faqat sof hisob-kitob qiladi (bazaga bog'liq emas), shuning uchun
oson test qilinadi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from fsrs import Card, Rating, Scheduler, State

__all__ = ["Rating", "State", "ReviewResult", "review", "is_due"]

_scheduler = Scheduler(
    desired_retention=0.9,
    learning_steps=(),
    relearning_steps=(),
    enable_fuzzing=True,
)


@dataclass
class ReviewResult:
    """Bitta javobdan keyingi yangi FSRS holati."""

    state: int
    step: int | None
    stability: float
    difficulty: float
    next_review: str  # ISO sana, "YYYY-MM-DD"
    last_review: str  # ISO sana

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "step": self.step,
            "stability": self.stability,
            "difficulty": self.difficulty,
            "next_review": self.next_review,
            "last_review": self.last_review,
        }


def _to_utc_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def review(
    rating: Rating,
    state: int | None = None,
    step: int | None = None,
    stability: float | None = None,
    difficulty: float | None = None,
    last_review: str | None = None,
    today: date | None = None,
) -> ReviewResult:
    """Javobni qayta ishlab, yangi FSRS holatini qaytaradi.

    Args:
        rating:        baho (fsrs.Rating: Again/Hard/Good/Easy)
        state:         joriy FSRS holati (None = so'z hali ko'rilmagan)
        step:          joriy learning/relearning bosqichi
        stability:     joriy barqarorlik parametri
        difficulty:    joriy qiyinlik parametri
        last_review:   oxirgi ko'rilgan sana (ISO, "YYYY-MM-DD")
        today:         "bugun" sanasi (test uchun almashtiriladi)
    """
    today = today or date.today()
    now = _to_utc_midnight(today)

    if state is None:
        card = Card()
    else:
        card = Card(
            state=State(state),
            step=step,
            stability=stability,
            difficulty=difficulty,
            due=now,
            last_review=_to_utc_midnight(date.fromisoformat(last_review)) if last_review else None,
        )

    card, _log = _scheduler.review_card(card, rating, review_datetime=now)

    return ReviewResult(
        state=int(card.state),
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        next_review=card.due.date().isoformat(),
        last_review=today.isoformat(),
    )


def is_due(next_review: str | None, today: date | None = None) -> bool:
    """So'z takrorlashga tayyormi (muddati kelgan yoki hali boshlanmagan)."""
    if not next_review:
        return True
    today = today or date.today()
    return next_review <= today.isoformat()


if __name__ == "__main__":
    # Qisqa namoyish: yangi so'zni "Good" bilan 3 marta, keyin "Again" bilan
    d = date(2026, 1, 1)
    state = review(Rating.Good, today=d)
    print("1-Good: ", state.as_dict())
    state = review(Rating.Good, state.state, state.step, state.stability, state.difficulty, state.last_review, today=d)
    print("2-Good: ", state.as_dict())
    state = review(Rating.Easy, state.state, state.step, state.stability, state.difficulty, state.last_review, today=d)
    print("3-Easy: ", state.as_dict())
    state = review(Rating.Again, state.state, state.step, state.stability, state.difficulty, state.last_review, today=d)
    print("4-Again:", state.as_dict())
