from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimedThing:
    id: str
    timestamp: datetime


@dataclass(frozen=True)
class PairingCandidate:
    left_id: str
    right_id: str
    delta_seconds: float
    confidence: str


def best_timestamp_pair(
    left: list[TimedThing],
    right: list[TimedThing],
    max_delta_seconds: float,
    ambiguous_delta_seconds: float,
) -> PairingCandidate | None:
    """Find best timestamp pair.

    Returns None if no candidate is within max_delta_seconds.

    Confidence is:
    - high if clearly closest
    - medium if within max range but not clearly closest
    - low if ambiguous
    """
    candidates: list[PairingCandidate] = []

    for l_item in left:
        for r_item in right:
            delta = abs((l_item.timestamp - r_item.timestamp).total_seconds())
            if delta <= max_delta_seconds:
                candidates.append(
                    PairingCandidate(
                        left_id=l_item.id,
                        right_id=r_item.id,
                        delta_seconds=delta,
                        confidence="medium",
                    )
                )

    if not candidates:
        return None

    candidates.sort(key=lambda c: c.delta_seconds)
    best = candidates[0]

    if len(candidates) > 1:
        second = candidates[1]
        if second.delta_seconds - best.delta_seconds <= ambiguous_delta_seconds:
            return PairingCandidate(
                left_id=best.left_id,
                right_id=best.right_id,
                delta_seconds=best.delta_seconds,
                confidence="low",
            )

    return PairingCandidate(
        left_id=best.left_id,
        right_id=best.right_id,
        delta_seconds=best.delta_seconds,
        confidence="high",
    )
