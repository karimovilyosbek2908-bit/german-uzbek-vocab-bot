"""Leitner (spaced repetition) algoritmi.

Box 1..5. Har bir box'ning takrorlash oralig'i (kunlarda):

    box 1 -> 1 kun
    box 2 -> 2 kun
    box 3 -> 4 kun
    box 4 -> 7 kun
    box 5 -> 15 kun

To'g'ri javob  -> box bir pog'ona ko'tariladi (maksimum 5).
Noto'g'ri javob -> box 1'ga qaytadi.
next_review    -> bugundan + yangi box oralig'i.

Modul faqat sof hisob-kitob qiladi (bazaga bog'liq emas), shuning uchun
oson test qilinadi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MIN_BOX = 1
MAX_BOX = 5

# box -> keyingi takrorlashgacha kun
INTERVALS: dict[int, int] = {
    1: 1,
    2: 2,
    3: 4,
    4: 7,
    5: 15,
}


@dataclass
class ReviewResult:
    """Bitta javobdan keyingi yangi Leitner holati."""

    box: int
    correct_count: int
    wrong_count: int
    next_review: str  # ISO sana, "YYYY-MM-DD"
    last_review: str  # ISO sana

    def as_dict(self) -> dict[str, object]:
        return {
            "box": self.box,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "next_review": self.next_review,
            "last_review": self.last_review,
        }


def interval_days(box: int) -> int:
    """Berilgan box uchun takrorlash oralig'i (kun)."""
    box = max(MIN_BOX, min(MAX_BOX, box))
    return INTERVALS[box]


def next_review_date(box: int, today: date | None = None) -> date:
    """Berilgan box uchun keyingi takrorlash sanasi."""
    today = today or date.today()
    return today + timedelta(days=interval_days(box))


def review(
    correct: bool,
    box: int = 0,
    correct_count: int = 0,
    wrong_count: int = 0,
    today: date | None = None,
) -> ReviewResult:
    """Javobni qayta ishlab, yangi holatni qaytaradi.

    Args:
        correct:       javob to'g'rimi
        box:           joriy box (0 = so'z hali o'rganilmagan)
        correct_count: shu paytgacha to'g'ri javoblar soni
        wrong_count:   shu paytgacha noto'g'ri javoblar soni
        today:         "bugun" sanasi (test uchun almashtiriladi)
    """
    today = today or date.today()
    current = max(0, min(MAX_BOX, box))

    if correct:
        new_box = min(MAX_BOX, max(MIN_BOX, current + 1))
        correct_count += 1
    else:
        new_box = MIN_BOX
        wrong_count += 1

    return ReviewResult(
        box=new_box,
        correct_count=correct_count,
        wrong_count=wrong_count,
        next_review=next_review_date(new_box, today).isoformat(),
        last_review=today.isoformat(),
    )


def is_due(next_review: str | None, today: date | None = None) -> bool:
    """So'z takrorlashga tayyormi (muddati kelgan yoki hali boshlanmagan)."""
    if not next_review:
        return True
    today = today or date.today()
    return next_review <= today.isoformat()


if __name__ == "__main__":
    # Qisqa namoyish: yangi so'zni 3 marta to'g'ri, keyin 1 marta xato
    from datetime import date as _date

    d = _date(2026, 1, 1)
    state = review(correct=True, today=d)
    print("1-to'g'ri:", state.as_dict())
    state = review(True, state.box, state.correct_count, state.wrong_count, today=d)
    print("2-to'g'ri:", state.as_dict())
    state = review(True, state.box, state.correct_count, state.wrong_count, today=d)
    print("3-to'g'ri:", state.as_dict())
    state = review(False, state.box, state.correct_count, state.wrong_count, today=d)
    print("4-xato:   ", state.as_dict())
