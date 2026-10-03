# FPV Still Decoder Porting Report

Date: 2026-05-14

This report freezes the current integration boundary before live RF/baseband work. The Mayhem app remains UI-only for this step; the only embedded code added is a fixed 160x120 grayscale framebuffer module that can later receive decoded frames.

## Current PC Decoder Pipeline

The working PC decoder is split across small Python modules:

1. IQ sample loading and format conversion
   - `capture_hackrf.py`
   - Reads either `complex64` IQ or HackRF `u8` interleaved I/Q.
   - HackRF `u8` conversion maps bytes centered near 127.5 into float complex samples.

2. FM video demodulation
   - `fm_demod.py`
   - Uses phase difference: `angle(iq[n] * conj(iq[n-1]))`.
   - Optional demod gain or FM-deviation scaling is applied in `main.py`.
   - Optional moving-average smoothing is available.

3. Video normalization and polarity handling
   - `fm_demod.remove_dc_and_normalize()`
   - Median DC removal, sigma clipping, peak normalization to roughly `[-1, 1]`.
   - Sync polarity can be auto/negative/positive.
   - Final luma can be inverted if needed.

4. Sync pulse detection
   - `composite_sync.py`
   - Uses NTSC/PAL line-rate assumptions.
   - Detects high-score threshold crossings after optional polarity inversion.
   - Clusters candidate sync edges and scores spacing quality.

5. Samples-per-line estimation
   - `composite_sync.estimate_line_length()`
   - Uses median spacing of plausible sync-to-sync intervals near the nominal line period.
   - At 10 MS/s, NTSC nominal line length is about 636 samples; PAL is about 640 samples.

6. Frame-start and vertical alignment
   - `composite_sync.estimate_frame_start()`
   - Current heuristic looks for short/irregular sync gaps, otherwise falls back to first plausible sync modulo a frame span.
   - This is still one of the weakest areas and explains the remaining top sync corruption.

7. Line reconstruction
   - `frame_extract.py`
   - Chooses a stable run of sync starts.
   - Uses one field by default to avoid stacked interlaced frames: 240 NTSC lines or 288 PAL lines.
   - Crops active video from each line using standard-dependent fractional windows.

8. Crop/scale to display target
   - `frame_extract.resize_frame()`
   - Current protected PortaPack output is 160x120.
   - 320x240 remains experimental and should not change the core reconstruction path.

9. Brightness/contrast adjustment
   - `frame_extract.apply_brightness_contrast()`
   - Simple post-normalization brightness offset and contrast multiplier.
   - Defaults preserve the known-good 160x120 baseline.

## PC-Only Code

Do not port these directly to Mayhem:

- File I/O for IQ and composite waveform loading.
- Python CLI parsing and batch test commands.
- NumPy vectorized arrays, percentiles, convolution, and complex types.
- Matplotlib debug plots.
- PNG output and Pillow resizing.
- Contact sheets and `.npy` debug dumps.
- Live `hackrf_transfer` subprocess capture helpers.

These stay in the PC project as tuning and validation tools.

## Portable Decoder Core To Port

The eventual C/C++ decoder should port only the numerical core:

- HackRF sample format conversion, if the baseband path provides interleaved I/Q instead of demodulated video.
- Wideband FM video demodulation.
- Lightweight DC removal / AGC / normalization.
- Sync thresholding and pulse clustering.
- Samples-per-line estimation.
- Frame/field start selection with `ALIGN` nudge support.
- Active-video line slicing.
- 160x120 grayscale framebuffer generation.
- Simple brightness and contrast adjustment.

The current C++ stub is intentionally limited to:

- `reset()`
- `configure(channel, fine_offset, gain_preset, align, brightness, contrast)`
- `process_samples(...)`
- `has_frame()`
- `get_framebuffer_160x120()`
- `generate_test_frame()` for the UI-only display-path milestone.

`process_samples(...)` is a no-op until RF/baseband integration is designed.

## RAM Estimate

Protected display target:

- 160x120 grayscale framebuffer: `160 * 120 = 19,200 bytes`.
- One RGB565-ish render line for display conversion: about `160 * 2 = 320 bytes`, depending on `ui::Color`.

Timing at 10 MS/s:

- NTSC line period: `10,000,000 / 15,734 ~= 636 samples`.
- PAL line period: `10,000,000 / 15,625 = 640 samples`.
- NTSC frame period: about `333,667 complex samples` per 29.97 Hz frame.
- PAL frame period: about `400,000 complex samples` per 25 Hz frame.

Raw buffering implications:

- A full NTSC frame of interleaved signed 8-bit I/Q would be about `333,667 * 2 ~= 667 KB`.
- A full NTSC frame of int16 demodulated video would be about `333,667 * 2 ~= 667 KB`.
- These full-frame raw buffers are too large to treat casually inside the PortaPack app.

Preferred embedded direction:

- Use a line/ring-buffer approach.
- Keep only a small demod window, sync state, line accumulator, and the final 19.2 KB framebuffer.
- A 2 to 4 line int16 ring buffer at about 640 samples/line is roughly 2.5 KB to 5 KB.
- If an intermediate active-video buffer is needed, keep it near the final 160x120 target.

## CPU Risk Areas

The PC decoder currently leans on floating point and vectorized NumPy. The risky pieces for the embedded port are:

- FM demodulation via `np.angle(...)`, which implies `atan2`.
- Percentile-based normalization.
- Floating-point clipping and scaling.
- Sync detection over large sample arrays.
- PIL bilinear resizing.

Embedded-friendly replacements to evaluate:

- Quadrature discriminator approximation using `I*dQ - Q*dI`, with fixed-point scaling.
- Simple IIR DC removal instead of median subtraction.
- Running min/max or clipped AGC over active-video regions rather than percentiles.
- Integer thresholding for sync pulses.
- Integer line resampling directly into 160 pixels.
- Avoid full-frame raw sample storage.

## Floating Point Status

The PC implementation currently uses floating point heavily:

- `complex64` IQ arrays.
- `float32` demodulated waveform.
- `np.angle` phase-difference FM demod.
- Median/std/percentile normalization.
- Floating crop fractions and contrast math.

For Mayhem, the first serious decoder pass should be written to allow fixed-point operation. Small amounts of float may compile, but relying on float for the hot path is a CPU and power risk.

## Chunk Size Needed For One Frame

One video frame at 10 MS/s is roughly:

- NTSC: 333k complex samples.
- PAL: 400k complex samples.

For robust sync acquisition, expect to inspect more than one frame at first:

- Initial PC-equivalent acquisition target: 0.1 to 0.25 seconds of samples.
- Embedded streaming target: continuous chunks of a few lines to a few dozen lines, maintaining sync state across calls.

The final app should not allocate one giant raw frame buffer if it can avoid it. The practical target is streaming line recovery into a 160x120 framebuffer.

## Expected Update Rate

The display workload for 160x120 grayscale is modest. The DSP path is the real risk.

Realistic staged target:

1. UI-only generated framebuffer: immediate.
2. File/offline-derived C test vectors on PC: next.
3. PortaPack baseband chunk input with sync debug counters: later.
4. Stable embedded low-FPS preview: about 1 frame per second.

Do not target full-rate video or color decoding.

## Current Integration Boundary

Implemented now:

- Mayhem UI skeleton remains unchanged in layout/menu/theme behavior.
- Added `fpv_decoder.hpp` and `fpv_decoder.cpp`.
- Added a fixed 160x120 grayscale framebuffer owned by the decoder stub.
- App preview can render that framebuffer.
- Existing direct placeholder test-pattern renderer remains available as a fallback.

Not implemented yet:

- RF tuning.
- HackRF gain control.
- Receiver or baseband image selection.
- Live IQ/audio/video sample access.
- Actual embedded FM demodulation.
- Actual embedded sync recovery.
- Any large buffers or decode loop.

## Next Safe Milestone

Before touching live RF/baseband, create a small C/C++ host-side test harness that feeds known PC decoder intermediate data or a short test vector into the portable decoder logic. Confirm that it can fill a 160x120 framebuffer without NumPy or PNG dependencies.

Only after that should the Mayhem baseband path be selected.
