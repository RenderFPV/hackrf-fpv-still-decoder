# FPV Still Embedded Decoder Core Scaffold

Date: 2026-05-14

This revision keeps FPV Still harmless and UI-only while shaping the embedded decoder around the PC pipeline. The app still renders a 160x120 grayscale framebuffer, but the framebuffer now comes through `FPVDecoder::process_samples(...)` and staged decoder methods instead of only a direct placeholder drawing routine.

## Python Stages Mapped Into `fpv_decoder.cpp`

- IQ/sample ingestion:
  - Python: `capture_hackrf.py`
  - C++ scaffold: `ingest_samples_stage(...)`
  - Current behavior: accepts the API shape, ignores real input, and advances synthetic sample counters.

- FM video demodulation:
  - Python: `fm_demod.quadrature_demod()`
  - C++ scaffold: `fm_video_demod_stage()`
  - Current behavior: TODO-only placeholder. Future embedded implementation should avoid `atan2` and use a fixed-point quadrature discriminator.

- Video normalization:
  - Python: `remove_dc_and_normalize()`
  - C++ scaffold: `normalize_video_stage()`
  - Current behavior: TODO-only placeholder. Future version should use integer DC removal and active-video AGC.

- Sync pulse detection:
  - Python: `detect_sync_pulses()`
  - C++ scaffold: `detect_sync_stage()`
  - Current behavior: synthetic NTSC-like sync count.

- Samples-per-line estimation:
  - Python: `estimate_line_length()`
  - C++ scaffold: `estimate_line_timing_stage()`
  - Current behavior: fixed NTSC-at-10MS/s estimate of about 636 samples/line.

- Frame reconstruction:
  - Python: `extract_luma_frame()`
  - C++ scaffold: `reconstruct_frame_stage()`
  - Current behavior: generates a synthetic active-video image into the protected 160x120 framebuffer.

- Brightness/contrast:
  - Python: `apply_brightness_contrast()`
  - C++ scaffold: `apply_display_adjust()`
  - Current behavior: integer-only brightness and contrast adjustment for the generated framebuffer.

## Intentionally Not Ported

- NumPy arrays and vectorized processing.
- Matplotlib waveform/sync plots.
- PNG output.
- CLI parsing.
- IQ file loading.
- `.npy` debug outputs.
- Contact sheets.
- `hackrf_transfer` subprocess helpers.
- Any live HackRF tuning or receive path.
- Any M4/baseband changes.

These remain PC-side tools until the decoder math is stable enough to port.

## Memory Buffers

Current embedded buffers:

- 160x120 grayscale framebuffer: 19,200 bytes.
- One UI render line in `ui_fpv_still.cpp`: about 160 pixels.
- Small decoder status/config structs.

Avoided for now:

- Full raw IQ frame buffers.
- Full demodulated composite frame buffers.
- Large sync index arrays.
- Multi-frame enhancement buffers.

Future live decoding should use a streaming line/ring-buffer design, not a full-frame sample buffer. At 10 MS/s, one NTSC frame is roughly 333k complex samples, which is too large for this app path.

## Fixed-Point / Optimization Risk

The likely hot spots are:

- FM demodulation.
- DC removal and gain normalization.
- Sync thresholding.
- Line-length estimation.
- Resampling active video into 160 pixels.

The PC decoder uses floats, percentiles, and `np.angle`; those are not suitable as-is. The embedded path should favor integer accumulators, fixed-point scaling, and direct line-to-framebuffer reconstruction.

## Next Step For Real Samples

The next safe milestone is not live RF yet. First, feed controlled test vectors into `FPVDecoder::process_samples(...)`, ideally from PC-derived intermediate data converted to small C arrays. Once that works, choose the Mayhem receive/baseband strategy and connect short chunks into `ingest_samples_stage(...)`.

The app should remain 160x120-first, approximately 1 FPS, luminance-only, and Raceband R1-R8 only.
