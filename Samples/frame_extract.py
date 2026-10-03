"""Extract low-resolution luminance frames from demodulated composite video."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from composite_sync import SyncDetection, VideoStandard


@dataclass
class FrameResult:
    raw_frame: np.ndarray
    resized_frame: np.ndarray
    assembled_lines: np.ndarray
    lines_used: int
    active_start_samples: int
    active_width_samples: int
    first_line_index: int


def extract_luma_frame(
    waveform: np.ndarray,
    sync: SyncDetection,
    standard: VideoStandard,
    output_size: tuple[int, int] = (160, 120),
    invert_luma: bool = False,
    crop_start: float | None = None,
    crop_end: float | None = None,
    frame_lines: int | None = None,
    line_tolerance: float = 0.15,
    skip_lines: int = 0,
) -> FrameResult:
    """Build a grayscale still frame from detected sync-to-sync line slices."""
    x = np.asarray(waveform, dtype=np.float32)
    line_len = sync.line_length_samples
    desired_lines = frame_lines or default_field_lines(standard)
    start_fraction = standard.active_start_fraction if crop_start is None else float(crop_start)
    end_fraction = (
        standard.active_start_fraction + standard.active_width_fraction
        if crop_end is None
        else float(crop_end)
    )
    start_fraction = min(max(start_fraction, 0.0), 0.98)
    end_fraction = min(max(end_fraction, start_fraction + 0.01), 1.0)
    active_start = int(line_len * start_fraction)
    active_width = max(8, int(line_len * (end_fraction - start_fraction)))
    line_starts, first_line_index = select_stable_line_starts(
        sync.sync_indices,
        line_len,
        desired_lines,
        line_tolerance,
        minimum_sample=sync.frame_start_index,
        skip_lines=skip_lines,
    )

    full_rows: list[np.ndarray] = []
    cropped_rows: list[np.ndarray] = []
    for line_start in line_starts:
        full_start = int(line_start)
        full_end = full_start + line_len
        start = full_start + active_start
        end = start + active_width
        if full_start < 0 or full_end > x.size:
            break
        if start < 0 or end > x.size:
            break
        full_rows.append(x[full_start:full_end])
        cropped_rows.append(x[start:end])

    if not cropped_rows:
        raise ValueError("Could not extract any complete video lines from the waveform")

    assembled = normalize_luma(np.vstack(full_rows), invert=invert_luma)
    raw = np.vstack(cropped_rows)
    raw_u8 = normalize_luma(raw, invert=invert_luma)
    resized = resize_frame(raw_u8, output_size)
    return FrameResult(
        raw_u8,
        resized,
        assembled,
        len(cropped_rows),
        active_start,
        active_width,
        first_line_index,
    )


def default_field_lines(standard: VideoStandard) -> int:
    """Use one field by default to avoid stacked interlaced frames."""
    if standard.name == "pal":
        return 288
    return 240


def select_stable_line_starts(
    sync_indices: np.ndarray,
    line_length_samples: int,
    desired_lines: int,
    line_tolerance: float,
    minimum_sample: int = 0,
    skip_lines: int = 0,
) -> tuple[np.ndarray, int]:
    """Choose a contiguous run of syncs whose intervals match the measured line."""
    if sync_indices.size < 2:
        start = int(sync_indices[0]) if sync_indices.size else 0
        return start + np.arange(desired_lines, dtype=np.int64) * line_length_samples, 0

    first_allowed = int(np.searchsorted(sync_indices, max(0, int(minimum_sample))))
    skip = max(0, int(skip_lines))
    tolerance = max(0.01, float(line_tolerance))
    diffs = np.diff(sync_indices)
    stable = np.abs(diffs - line_length_samples) <= line_length_samples * tolerance
    best_start = 0
    best_len = 0
    run_start = 0
    run_len = 0
    for i, ok in enumerate(stable):
        if ok:
            if run_len == 0:
                run_start = i
            run_len += 1
        else:
            if run_len > best_len:
                best_start, best_len = run_start, run_len
            run_len = 0
    if run_len > best_len:
        best_start, best_len = run_start, run_len

    if best_len >= max(2, desired_lines - 1):
        first = max(best_start, first_allowed) + skip
        if first + desired_lines <= sync_indices.size:
            return sync_indices[first : first + desired_lines], first
        first = best_start
        return sync_indices[first : first + desired_lines], first

    first = first_allowed + skip
    starts = sync_indices[first : first + desired_lines]
    if starts.size >= desired_lines:
        return starts, first

    fallback_start = int(sync_indices[0])
    return fallback_start + np.arange(desired_lines, dtype=np.int64) * line_length_samples, 0


def normalize_luma(frame: np.ndarray, invert: bool = False) -> np.ndarray:
    """Robustly map arbitrary waveform levels to 8-bit grayscale."""
    lo, hi = np.percentile(frame, [2.0, 98.0])
    if hi <= lo:
        hi = float(np.max(frame))
        lo = float(np.min(frame))
    if hi <= lo:
        return np.zeros(frame.shape, dtype=np.uint8)
    y = np.clip((frame - lo) / (hi - lo), 0.0, 1.0)
    if invert:
        y = 1.0 - y
    return (y * 255.0).astype(np.uint8)


def resize_frame(frame_u8: np.ndarray, output_size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(frame_u8, mode="L")
    resampling = getattr(Image, "Resampling", Image).BILINEAR
    return np.asarray(image.resize(output_size, resampling))
