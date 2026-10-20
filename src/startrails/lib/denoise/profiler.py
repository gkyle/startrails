"""Lightweight latency profiler for pipeline stages and operations."""

from __future__ import annotations
from contextlib import contextmanager
import logging
import time
from typing import Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class PipelineProfiler:
    """Measures and aggregates execution latency across pipeline operations."""

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.counts: Dict[str, int] = {}
        self.start_time: float = time.perf_counter()

    @contextmanager
    def measure(self, name: str) -> Generator[None, None, None]:
        """Context manager to measure latency of an operation block."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self.timings[name] = self.timings.get(name, 0.0) + elapsed
            self.counts[name] = self.counts.get(name, 0) + 1
            logger.debug(f"[LATENCY] {name}: {elapsed:.4f}s")

    def format_summary(self, total_elapsed: Optional[float] = None) -> str:
        """Generate a formatted multi-line table breakdown of latencies."""
        names = list(self.timings.keys())
        col_w = max([len(n) for n in names] + [len("Total Elapsed"), 32]) + 2
        sep_len = col_w + 35
        total = total_elapsed if total_elapsed is not None else (time.perf_counter() - self.start_time)

        lines: List[str] = ["\n===== Denoise Performance Latency Breakdown ====="]

        for name, dur in self.timings.items():
            pct = (dur / total * 100.0) if total > 0 else 0.0
            count = self.counts.get(name, 1)
            name_padded = f"{name:<{col_w}}"
            if count > 1:
                avg_ms = (dur / count) * 1000.0
                lines.append(f"  {name_padded}: {dur:6.2f}s ({pct:4.1f}%) | {count}x, avg {avg_ms:5.1f}ms")
            else:
                lines.append(f"  {name_padded}: {dur:6.2f}s ({pct:4.1f}%)")

        lines.append("-" * sep_len)
        total_padded = f"{'Total Elapsed':<{col_w}}"
        lines.append(f"  {total_padded}: {total:6.2f}s")
        lines.append("=" * sep_len)
        return "\n".join(lines)
