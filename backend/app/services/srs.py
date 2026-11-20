"""Spaced-repetition scheduling — the SuperMemo-2 algorithm (Wozniak, 1990).

ORAYA's four review buttons map onto SM-2's 0-5 grade scale:
    0 Again -> 1 (lapse)    1 Hard -> 3    2 Good -> 4    3 Easy -> 5

Pure functions only, so the scheduler is unit-testable without a database.
"""
from __future__ import annotations

from dataclasses import dataclass

GRADE = {0: 1, 1: 3, 2: 4, 3: 5}
MIN_EASE = 1.3
MAX_INTERVAL_DAYS = 365.0
RELEARN_MINUTES = 10


@dataclass(frozen=True)
class Schedule:
    reps: int
    ease: float
    interval_days: float  # 0 means "relearn in RELEARN_MINUTES"
    lapsed: bool


def next_schedule(reps: int, ease: float, interval_days: float, quality: int) -> Schedule:
    if quality not in GRADE:
        raise ValueError("quality must be 0, 1, 2 or 3")
    q = GRADE[quality]
    new_ease = max(MIN_EASE, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if q < 3:  # failed recall: start the repetition sequence again
        return Schedule(reps=0, ease=new_ease, interval_days=0.0, lapsed=True)
    new_reps = reps + 1
    if new_reps == 1:
        interval = 1.0
    elif new_reps == 2:
        interval = 6.0
    else:
        interval = max(interval_days, 1.0) * new_ease
    return Schedule(new_reps, new_ease, min(round(interval, 2), MAX_INTERVAL_DAYS), False)


def maturity(reps: int, interval_days: float) -> str:
    """Card stage used by revision analytics."""
    if reps == 0 and interval_days == 0:
        return "new"
    if interval_days < 7:
        return "learning"
    if interval_days < 21:
        return "young"
    return "mature"
