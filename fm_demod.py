"""Wideband FM demodulation helpers for analog FPV composite video."""

from __future__ import annotations

import numpy as np


def quadrature_demod(iq: np.ndarray) -> np.ndarray:
    """FM-demodulate complex IQ using phase difference.

    Output is arbitrary-amplitude float32 video/baseband. A later calibration
    step may need to invert or scale it depending on receiver tuning and VTX.
    """
    if iq.ndim != 1:
        raise ValueError("IQ input must be a one-dimensional complex array")
    if iq.size < 2:
        raise ValueError("Need at least two IQ samples to demodulate")

    iq64 = iq.astype(np.complex64, copy=False)
    phase_delta = np.angle(iq64[1:] * np.conj(iq64[:-1]))
    return phase_delta.astype(np.float32)


def remove_dc_and_normalize(waveform: np.ndarray, clip_sigma: float = 4.0) -> np.ndarray:
    """Remove DC, gently clip outliers, and normalize to roughly [-1, 1]."""
    x = np.asarray(waveform, dtype=np.float32)
    x = x - np.median(x)
    sigma = float(np.std(x))
    if sigma > 0:
        limit = clip_sigma * sigma
        x = np.clip(x, -limit, limit)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak > 0:
        x = x / peak
    return x.astype(np.float32)


def moving_average_lowpass(waveform: np.ndarray, taps: int) -> np.ndarray:
    """Simple FIR smoother used only when requested by the CLI."""
    if taps <= 1:
        return np.asarray(waveform, dtype=np.float32)
    kernel = np.ones(int(taps), dtype=np.float32) / float(taps)
    return np.convolve(waveform, kernel, mode="same").astype(np.float32)
