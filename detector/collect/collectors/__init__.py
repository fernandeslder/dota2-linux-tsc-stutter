"""Signal collectors.

Every sampler implements the tiny `Sampler` protocol: `columns`, `interval`,
`prepare()`, `sample(t)` and optional `teardown()`.  The supervisor owns the
threads and the CSV files; samplers only produce rows for their own header.

Rates come from detector.collect.profiles.
"""

from __future__ import annotations

from typing import List, Optional

from .. import util


class Sampler:
    name = "sampler"
    columns: List[str] = []
    interval: float = 1.0

    def prepare(self) -> None:  # noqa: D401
        """Called once, in the sampler's own thread, before the first sample."""

    def sample(self, t: float) -> Optional[list]:  # noqa: D401
        return None

    def teardown(self) -> None:
        pass


def default_cpu_columns(ncpu: int = 0) -> List[str]:
    if not ncpu:
        ncpu = len(util.all_cpus())
    cols = [f"cpu{i}_util" for i in range(ncpu)]
    cols.append("cpu_util_avg")
    return cols
