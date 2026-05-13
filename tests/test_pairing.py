from datetime import datetime, timedelta

from cd_archivist.pairing.timestamp_pairing import TimedThing, best_timestamp_pair


def test_best_timestamp_pair_returns_none_without_match() -> None:
    left = [TimedThing("capture_1", datetime(2026, 1, 1, 12, 0, 0))]
    right = [TimedThing("rip_1", datetime(2026, 1, 1, 13, 0, 0))]

    result = best_timestamp_pair(
        left,
        right,
        max_delta_seconds=60,
        ambiguous_delta_seconds=10,
    )

    assert result is None


def test_best_timestamp_pair_high_confidence() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0)
    left = [TimedThing("capture_1", base)]
    right = [TimedThing("rip_1", base + timedelta(seconds=30))]

    result = best_timestamp_pair(
        left,
        right,
        max_delta_seconds=120,
        ambiguous_delta_seconds=10,
    )

    assert result is not None
    assert result.left_id == "capture_1"
    assert result.right_id == "rip_1"
    assert result.confidence == "high"


def test_best_timestamp_pair_low_confidence_when_ambiguous() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0)
    left = [TimedThing("capture_1", base)]
    right = [
        TimedThing("rip_1", base + timedelta(seconds=30)),
        TimedThing("rip_2", base + timedelta(seconds=35)),
    ]

    result = best_timestamp_pair(
        left,
        right,
        max_delta_seconds=120,
        ambiguous_delta_seconds=10,
    )

    assert result is not None
    assert result.confidence == "low"
