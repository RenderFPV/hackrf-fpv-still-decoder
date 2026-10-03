"""HackRF capture and IQ file helpers.

The first milestone is offline decoding from files. Live capture helpers stay
small and explicit so the decoder can be used without HackRF libraries present.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np


def read_complex64_iq(path: str | Path, max_samples: int | None = None) -> np.ndarray:
    """Read interleaved complex64 IQ samples from a file."""
    count = -1 if max_samples is None else max_samples
    samples = np.fromfile(Path(path), dtype=np.complex64, count=count)
    if samples.size == 0:
        raise ValueError(f"No complex64 IQ samples found in {path}")
    return samples


def read_hackrf_u8_iq(path: str | Path, max_samples: int | None = None) -> np.ndarray:
    """Read hackrf_transfer unsigned 8-bit interleaved IQ as complex64.

    hackrf_transfer writes I,Q bytes centered near 127.5. This helper is useful
    for recordings made directly by HackRF tools, even though complex64 remains
    the primary initial format.
    """
    byte_count = -1 if max_samples is None else max_samples * 2
    raw = np.fromfile(Path(path), dtype=np.uint8, count=byte_count)
    if raw.size < 2:
        raise ValueError(f"No uint8 IQ samples found in {path}")
    if raw.size % 2:
        raw = raw[:-1]
    iq = raw.astype(np.float32).reshape(-1, 2)
    iq = (iq - 127.5) / 127.5
    return iq[:, 0].astype(np.float32) + 1j * iq[:, 1].astype(np.float32)


def hackrf_transfer_available() -> bool:
    """Return True when hackrf_transfer is on PATH."""
    return shutil.which("hackrf_transfer") is not None


def capture_with_hackrf_transfer(
    output_path: str | Path,
    frequency_hz: int,
    sample_rate_hz: int,
    seconds: float,
    lna_gain: int = 32,
    vga_gain: int = 24,
    amp_enable: bool = False,
) -> Path:
    """Capture unsigned 8-bit interleaved IQ with hackrf_transfer.

    The returned file should be decoded with --sample-format hackrf_u8.
    """
    if not hackrf_transfer_available():
        raise RuntimeError("hackrf_transfer was not found on PATH")

    sample_count = int(sample_rate_hz * seconds)
    output = Path(output_path)
    cmd = [
        "hackrf_transfer",
        "-r",
        str(output),
        "-f",
        str(frequency_hz),
        "-s",
        str(sample_rate_hz),
        "-n",
        str(sample_count),
        "-l",
        str(lna_gain),
        "-g",
        str(vga_gain),
    ]
    if amp_enable:
        cmd.extend(["-a", "1"])

    subprocess.run(cmd, check=True)
    return output


def capture_with_soapy(*_args: object, **_kwargs: object) -> np.ndarray:
    """Placeholder for a future SoapySDR live capture backend."""
    raise NotImplementedError(
        "SoapySDR live capture is planned. Use offline IQ files or hackrf_transfer first."
    )
