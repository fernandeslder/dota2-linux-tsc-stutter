"""Dota 2 stutter detector.

  detector/collect/   runs the collectors on ONE clock, writes the run-dir
  detector/analyze/   turns a run-dir into hitches, periodicity, correlation, a verdict
  bin/stutter         single entry point
  runs/<run-id>/      per-trial data (run-dir contract in docs/SPEC-detector.md)
"""

__all__ = ["collect", "analyze"]
