"""
Layers 13–15 — Observation History Window Tests:
Verifies rolling deque bounds, chronological ordering, and model/observed pair tracking.
"""

import pytest
from fusion.history import SensorHistoryTracker


def test_history_tracker_rolling_window():
    """Verifies that history respects max_history_steps and maintains chronological order."""
    tracker = SensorHistoryTracker(max_history_steps=3)

    tracker.record_observation("S1", 10, 15.0, 18.0, 3.0)
    tracker.record_observation("S1", 20, 15.0, 19.0, 4.0)
    tracker.record_observation("S1", 30, 15.0, 20.0, 5.0)
    assert tracker.get_history_count("S1") == 3

    # Add 4th record -> oldest dropped
    tracker.record_observation("S1", 40, 15.0, 21.0, 6.0)
    history = tracker.get_history("S1")
    assert len(history) == 3
    assert history[0].timestamp_seconds == 20
    assert history[1].timestamp_seconds == 30
    assert history[2].timestamp_seconds == 40
    assert history[2].residual_cm == pytest.approx(6.0)
