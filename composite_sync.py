"""Best-effort composite video sync detection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class VideoStandard:
    name: str
    line_rate_hz: float
    total_lines: int
    visible_lines: int
    active_width_fraction: float = 0.76
    active_start_fraction: float = 0.18


STANDARDS = {
    "ntsc": VideoStandard("ntsc", line_rate_hz=15_734.0, total_lines=525, visible_lines=480),
    "pal": VideoStandard("pal", line_rate_hz=15_625.0, total_lines=625, visible_lines=576),
}


@dataclass
class SyncDetection:
    sync_indices: np.ndarray
    line_length_samples: int
    frame_start_index: int
    sync_polarity: int
    threshold: float


def expected_line_samples(sample_rate_hz: float, standard: VideoStandard) -> int:
    return int(round(sample_rate_hz / standard.line_rate_hz))


def detect_sync_pulses(
    waveform: np.ndarray,
    sample_rate_hz: float,
    standard: VideoStandard,
    polarity: str = "auto",
    sync_threshold: float | None = None,
    line_tolerance: float = 0.25,
) -> SyncDetection:
    """Detect likely horizontal sync pulse starts.

    Composite sync is normally below blanking level, but after FM demod and
    arbitrary inversion it may appear high or low. Auto mode tries both.
    """
    x = np.asarray(waveform, dtype=np.float32)
    nominal_line = expected_line_samples(sample_rate_hz, standard)
    min_gap = max(4, int(nominal_line * 0.55))

    candidates: list[tuple[np.ndarray, int, float, float]] = []
    polarities = [-1, 1] if polarity == "auto" else ([-1] if polarity == "negative" else [1])
    for sign in polarities:
        score = sign * x
        threshold = float(sync_threshold) if sync_threshold is not None else float(np.percentile(score, 97.5))
        mask = score > threshold
        starts = _rising_edges(mask)
        starts = _cluster_edges(starts, min_gap)
        quality = _spacing_quality(starts, nominal_line, line_tolerance)
        candidates.append((starts, sign, threshold, quality))

    starts, sign, threshold, _quality = max(candidates, key=lambda item: item[3])
    line_len = estimate_line_length(starts, nominal_line, line_tolerance)
    frame_start = estimate_frame_start(starts, line_len, standard)
    return SyncDetection(starts, line_len, frame_start, sign, threshold)


def estimate_line_length(
    sync_indices: np.ndarray, nominal_line: int, line_tolerance: float = 0.25
) -> int:
    """Estimate samples per line from sync-to-sync spacing."""
    if sync_indices.size < 3:
        return nominal_line
    diffs = np.diff(sync_indices)
    tolerance = max(0.01, float(line_tolerance))
    lo = int(nominal_line * (1.0 - tolerance))
    hi = int(nominal_line * (1.0 + tolerance))
    plausible = diffs[(diffs >= lo) & (diffs <= hi)]
    if plausible.size == 0:
        return nominal_line
    return int(round(float(np.median(plausible))))


def estimate_frame_start(
    sync_indices: np.ndarray, line_length_samples: int, standard: VideoStandard
) -> int:
    """Return a likely frame start index.

    This proof of concept uses a conservative heuristic: look for unusually
    dense/irregular sync around vertical blanking; otherwise use the first sync.
    """
    if sync_indices.size < 10:
        return int(sync_indices[0]) if sync_indices.size else 0

    diffs = np.diff(sync_indices)
    short_gap = diffs < line_length_samples * 0.65
    if np.any(short_gap):
        return int(sync_indices[np.argmax(short_gap)])

    frame_span = line_length_samples * standard.total_lines
    modulo = sync_indices % max(frame_span, 1)
    return int(sync_indices[int(np.argmin(modulo))])


def _rising_edges(mask: np.ndarray) -> np.ndarray:
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    return np.flatnonzero(np.diff(padded.astype(np.int8)) == 1).astype(np.int64)


def _cluster_edges(indices: np.ndarray, min_gap: int) -> np.ndarray:
    if indices.size == 0:
        return indices
    chosen = [int(indices[0])]
    for idx in indices[1:]:
        if int(idx) - chosen[-1] >= min_gap:
            chosen.append(int(idx))
    return np.asarray(chosen, dtype=np.int64)


def _spacing_quality(indices: np.ndarray, nominal_line: int, line_tolerance: float) -> float:
    if indices.size < 3:
        return 0.0
    diffs = np.diff(indices)
    near = np.abs(diffs - nominal_line) < nominal_line * max(0.01, float(line_tolerance))
    return float(np.count_nonzero(near)) / float(max(1, diffs.size))
