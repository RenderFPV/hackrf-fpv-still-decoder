"""Output and debug rendering utilities."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def save_png(frame_u8: np.ndarray, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(frame_u8.astype(np.uint8), mode="L").save(output)
    return output


def save_contact_sheet(
    frames: list[np.ndarray],
    path: str | Path,
    columns: int = 3,
    padding: int = 6,
) -> Path:
    """Save a simple tiled contact sheet for candidate frame comparison."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not frames:
        raise ValueError("No frames supplied for contact sheet")

    images = [Image.fromarray(frame.astype(np.uint8), mode="L") for frame in frames]
    width, height = images[0].size
    cols = max(1, min(columns, len(images)))
    rows = int(np.ceil(len(images) / cols))
    sheet = Image.new("L", (cols * width + (cols - 1) * padding, rows * height + (rows - 1) * padding), 32)
    for i, image in enumerate(images):
        x = (i % cols) * (width + padding)
        y = (i // cols) * (height + padding)
        sheet.paste(image, (x, y))
    sheet.save(output)
    return output


def save_debug_artifacts(
    debug_dir: str | Path,
    waveform: np.ndarray,
    sync_indices: np.ndarray,
    raw_frame: np.ndarray,
    final_frame: np.ndarray,
    sample_rate_hz: float,
    save_demod_waveform: bool = False,
    filtered_waveform: np.ndarray | None = None,
    assembled_lines: np.ndarray | None = None,
    estimated_line_length: int | None = None,
    sync_threshold: float | None = None,
    first_line_index: int | None = None,
    max_plot_samples: int = 200_000,
) -> None:
    """Write PNG/NPY debug artifacts.

    matplotlib is optional at runtime; if it is installed, plots are produced.
    Raw numeric data is always written as .npy files.
    """
    out = Path(debug_dir)
    out.mkdir(parents=True, exist_ok=True)
    if save_demod_waveform:
        np.save(out / "demod_waveform.npy", waveform.astype(np.float32))
    if filtered_waveform is not None:
        np.save(out / "filtered_waveform.npy", filtered_waveform.astype(np.float32))
    np.save(out / "sync_indices.npy", sync_indices.astype(np.int64))
    if sync_indices.size > 1:
        np.save(out / "sync_intervals.npy", np.diff(sync_indices).astype(np.int64))
    save_png(raw_frame, out / "raw_frame.png")
    save_png(final_frame, out / "frame.png")
    if assembled_lines is not None:
        save_png(assembled_lines, out / "assembled_lines.png")
    _write_sync_report(
        out / "sync_report.txt",
        sync_indices,
        estimated_line_length,
        sync_threshold,
        first_line_index,
    )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    n = min(max_plot_samples, waveform.size)
    t_ms = np.arange(n, dtype=np.float32) / float(sample_rate_hz) * 1000.0

    plt.figure(figsize=(14, 5))
    plt.plot(t_ms, waveform[:n], linewidth=0.6)
    in_view = sync_indices[sync_indices < n]
    if in_view.size:
        plt.scatter(
            in_view / float(sample_rate_hz) * 1000.0,
            waveform[in_view],
            s=8,
            c="red",
            label="sync",
        )
        plt.legend(loc="upper right")
    plt.title("Demodulated composite waveform with detected sync")
    plt.xlabel("time (ms)")
    plt.ylabel("normalized amplitude")
    plt.tight_layout()
    plt.savefig(out / "waveform_sync.png", dpi=140)
    plt.close()

    if sync_indices.size > 1:
        intervals = np.diff(sync_indices)
        upper = estimated_line_length * 3 if estimated_line_length else np.percentile(intervals, 99)
        plotted = intervals[intervals <= upper]
        plt.figure(figsize=(12, 5))
        plt.hist(plotted, bins=160)
        if estimated_line_length:
            plt.axvline(estimated_line_length, color="red", label=f"line {estimated_line_length}")
            plt.legend(loc="upper right")
        plt.title("Detected sync interval histogram")
        plt.xlabel("samples between sync pulses")
        plt.ylabel("count")
        plt.tight_layout()
        plt.savefig(out / "sync_interval_histogram.png", dpi=140)
        plt.close()


def _write_sync_report(
    path: Path,
    sync_indices: np.ndarray,
    estimated_line_length: int | None,
    sync_threshold: float | None,
    first_line_index: int | None,
) -> None:
    intervals = np.diff(sync_indices) if sync_indices.size > 1 else np.asarray([], dtype=np.int64)
    lines = [
        f"detected_sync_pulses={sync_indices.size}",
        f"estimated_samples_per_line={estimated_line_length if estimated_line_length is not None else 'unknown'}",
        f"sync_threshold={sync_threshold if sync_threshold is not None else 'auto'}",
        f"first_line_index={first_line_index if first_line_index is not None else 'unknown'}",
    ]
    if intervals.size:
        lines.extend(
            [
                f"interval_median={float(np.median(intervals)):.3f}",
                f"interval_p05={float(np.percentile(intervals, 5)):.3f}",
                f"interval_p95={float(np.percentile(intervals, 95)):.3f}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
