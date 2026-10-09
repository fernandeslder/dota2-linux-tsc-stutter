"""Tests for the e2e harness scenario schedules (no live capture)."""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.e2e_validate import mixed_schedule  # noqa: E402


def test_mixed_schedule_is_decoupled_and_records_real_durations():
    rng = random.Random(21)
    sched = mixed_schedule(600.0, 4.0, 45.0, 22.5, 40.0, 80.0, rng)
    assert sched, "schedule must not be empty"
    kinds = {k for k, _, _ in sched}
    assert kinds == {"periodic", "sparse"}, kinds
    # all durations are real (the old bug wrote 0)
    assert all(40.0 <= d <= 80.0 for _, _, d in sched)
    # sparse cadence ~45 s
    sp = [t for k, t, _ in sched if k == "sparse"]
    assert len(sp) >= 10
    assert all(40.0 <= b - a <= 50.0 for a, b in zip(sp, sp[1:]))
    # a sparse tick is never adjacent to a periodic beat (>= guard)
    per = [t for k, t, _ in sched if k == "periodic"]
    for s in sp:
        assert min(abs(s - p) for p in per) >= 0.6
    # time-ordered
    assert sched == sorted(sched, key=lambda e: e[1])


def test_mixed_schedule_short_window():
    rng = random.Random(0)
    sched = mixed_schedule(60.0, 4.0, 45.0, 22.5, 40.0, 80.0, rng)
    sp = [t for k, t, _ in sched if k == "sparse"]
    assert len(sp) == 1  # 22.5 s only
