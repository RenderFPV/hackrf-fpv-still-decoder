# HackRF FPV Still Decoder

Proof-of-concept 1 Hz analog FPV still-frame decoder for HackRF recordings.

The goal is intentionally narrow: take a strong analog FPV transmission, FM-demodulate it into a composite-video-like waveform, extract luminance only, and save a rough black-and-white still image. This is not smooth video, not color, not audio, and not transmit.

## Target

- Hardware source: HackRF One, optionally with PortaPack H4M running Mayhem firmware later.
- Signal source: standard analog FPV VTX, likely 5.8 GHz, NTSC or PAL composite video over FM.
- First milestone: PC offline workflow, `IQ recording file -> decoded PNG still image`.
- Later milestone: Mayhem/PortaPack port once the PC decoder can produce recognizable frames.

## Assumptions

- NTSC line rate is approximately 15.734 kHz.
- PAL line rate is approximately 15.625 kHz.
- NTSC has approximately 525 total lines.
- PAL has approximately 625 total lines.
- This proof of concept uses luminance only and ignores chroma.
- Sync polarity and exact FM deviation may need calibration per capture.
- Strong signal recordings should be used first.
- HackRF recordings must be centered and wide enough to preserve the FPV FM video deviation.

## Install

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
C:\Users\Render\AppData\Local\Python\bin\python.exe -m pip install -r requirements.txt
```

## Basic Use

The default output target is the PortaPack-oriented 160x120 path. That path is the current quality baseline and should remain stable while higher-resolution PC previews are treated as experimental.

Primary path, complex64 IQ:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq sample.iq --sample-rate 10000000 --standard ntsc --out frame.png
```

HackRF `hackrf_transfer` unsigned-byte IQ:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq sample.u8 --sample-format hackrf_u8 --sample-rate 10000000 --standard ntsc --out frame.png
```

Fallback path, already-demodulated float32 composite waveform:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --composite composite.f32 --sample-rate 10000000 --standard ntsc --out frame.png
```

Useful options:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq sample.iq --sample-rate 10000000 --standard ntsc --out frame.png --debug-dir debug --invert-video --smooth 5
```

Output targets:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq r5_5802_g16.u8 --sample-format hackrf_u8 --sample-rate 10000000 --standard ntsc --out portapack_160.png --target portapack
```

`--target raw` writes the reconstructed active frame before final display scaling. `--target preview` and explicit sizes above 160x120 are blocked unless `--experimental-preview` is also supplied. The current 320x240 path is for PC inspection only; it is not considered a better reconstruction yet.

## Future PortaPack UI

The future PortaPack H4M/Mayhem app should keep the visible controls small and practical. The user-facing UI should expose only:

| Label | Control | Notes |
| --- | --- | --- |
| `CH` | Channel/band selector | Example `R5`; maps to nominal channel frequency such as 5806 MHz. |
| `FINE` | Frequency fine tune | Offset around the selected channel. Example: `R5` plus `-4.0 MHz` tunes 5806 MHz to 5802 MHz. Do not hardcode R5 to 5802 MHz. |
| `GAIN` | RF gain preset | `LOW`, `MID`, `HIGH`, and maybe `AUTO`; internally maps to HackRF gain values. Current known-good equivalent is LNA 32, VGA 16. |
| `ALIGN` | Frame alignment nudge | Small frame-start adjustment to reduce top sync corruption; should support `AUTO` later if practical. |
| `BRT` | Brightness | Simple final image brightness. |
| `CON` | Contrast | Simple final image contrast. |
| `SIZE` | Preview size | Default `160x120`; `320x240` stays experimental/PC preview for now. |

Frequency behavior:

```text
CH = R5
nominal = 5806 MHz
FINE = -4 MHz
tuned = 5802 MHz
```

The PC CLI accepts `--ch R5 --fine -4` as metadata for this future UI behavior. For offline IQ files, it does not retune the already-recorded capture.

Advanced PC/developer-only options may remain in the CLI for research, but should not be exposed as normal PortaPack UI controls:

- Explicit center frequency or capture command details.
- Separate LNA and VGA values.
- Sync threshold, line tolerance, and line length experiments.
- Crop values and raw/debug output.
- Experimental preview above 160x120.
- Sharpening, denoise, gamma, scaler choices, and full width/height entry.

The embedded target remains `160x120` first. Do not let PC preview work degrade the protected PortaPack baseline.

## Debug Outputs

The decoder writes these to `--debug-dir`:

- `waveform_sync.png`: demodulated waveform plot with detected sync positions.
- `sync_indices.npy`: detected sync pulse sample indices.
- `raw_frame.png`: extracted raw frame before resize.
- `frame.png`: final grayscale image.
- `demod_waveform.npy`: optional normalized demodulated waveform when `--save-demod-waveform` is used.

The CLI also prints detected sync pulse count, estimated line length in samples, frame start index, and active video crop.

## Capturing Test IQ With hackrf_transfer

Example for Raceband 1 at 5658 MHz, 10 Msps, 2 seconds:

```powershell
hackrf_transfer -r sample.u8 -f 5658000000 -s 10000000 -n 20000000 -l 32 -g 24
```

Then decode:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq sample.u8 --sample-format hackrf_u8 --sample-rate 10000000 --standard ntsc --out frame.png
```

Tips:

- Start with a nearby, strong VTX signal and a legal dummy-load or shielded test setup where appropriate.
- Try 10 Msps or 20 Msps. Lower rates may lose too much FM deviation or video detail.
- Adjust center frequency, LNA gain, and VGA gain if sync detection finds too few pulses.
- If the image is negative, use `--invert-video`.
- If sync is wrong, try `--sync-polarity positive` or `--sync-polarity negative`.

## Real HackRF FPV Capture Test

Start with a short capture to confirm the channel, gain, and file workflow:

```powershell
hackrf_transfer -r fpv_short.u8 -f 5658000000 -s 10000000 -n 5000000 -l 32 -g 24
```

Then make a longer sample for decoding:

```powershell
hackrf_transfer -r fpv_sample.u8 -f 5658000000 -s 10000000 -n 30000000 -l 32 -g 24
```

Decode it:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq fpv_sample.u8 --sample-format hackrf_u8 --sample-rate 10000000 --standard ntsc --out frame.png --debug-dir debug
```

The decoder writes `frame.png` plus `debug\waveform_sync.png`, `debug\raw_frame.png`, and `debug\sync_indices.npy`. Add `--save-demod-waveform` when you also want `debug\demod_waveform.npy` for offline analysis.

For the known-good Raceband R5 captures used during decoder tuning:

```powershell
hackrf_transfer -r r5_5802_g16.u8 -f 5802000000 -s 10000000 -n 20000000 -l 32 -g 16
hackrf_transfer -r r5_5802_g16_long.u8 -f 5802000000 -s 10000000 -n 60000000 -l 32 -g 16
```

Decode the short baseline:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq r5_5802_g16.u8 --sample-format hackrf_u8 --sample-rate 10000000 --standard ntsc --out frame.png --debug-dir debug
```

The current decoder estimates the line length from the capture instead of blindly assuming NTSC/PAL timing. On the R5 5802 MHz samples, it should report roughly `635-636` samples per line.

Advanced PC/developer tuning options:

```powershell
C:\Users\Render\AppData\Local\Python\bin\python.exe main.py --iq fpv_sample.u8 --sample-format hackrf_u8 --sample-rate 10000000 --standard ntsc --out frame.png --debug-dir debug --sync-threshold 0.65 --line-tolerance 0.20 --crop-start 0.18 --crop-end 0.94 --demod-gain 1.5 --save-demod-waveform
```

Troubleshooting:

- If the output is mostly noise, verify the FPV channel frequency and move the VTX closer.
- If sync is unstable, tune `--sync-threshold` and `--line-tolerance`.
- If the image is shifted or cut off, tune `--crop-start` and `--crop-end`.
- If the image is inverted black/white, try `--invert-video`.
- If the demodulated waveform looks too small or too large, tune `--demod-gain` or `--fm-deviation`.
- If 10 MS/s is not enough, try captures at 12 MS/s or 16 MS/s and pass the matching `--sample-rate`.

Additional debug files:

- `debug\assembled_lines.png`: line image before active-video crop, useful for seeing sync/blanking at line edges.
- `debug\sync_interval_histogram.png`: histogram of detected sync-to-sync sample intervals.
- `debug\sync_intervals.npy`: raw sync interval samples.
- `debug\sync_report.txt`: detected pulse count, estimated samples-per-line, threshold, and interval summary.
- `debug\filtered_waveform.npy`: written when `--smooth` is greater than 1.

## Module Layout

- `capture_hackrf.py`: offline IQ readers and a small `hackrf_transfer` capture helper.
- `fm_demod.py`: phase-difference FM demodulation and waveform normalization.
- `composite_sync.py`: rough horizontal and vertical sync detection.
- `frame_extract.py`: active-line extraction and grayscale frame resize.
- `display_frame.py`: PNG output and debug plots.
- `main.py`: command-line pipeline.

## Mayhem/PortaPack Notes

I inspected a local Mayhem checkout at:

`C:\Users\Render\Documents\Codex\2026-05-09\im-looking-to-add-digital-fpv\mayhem-firmware`

Relevant folders in the current tree:

- `firmware\application\external`: SD-card external UI apps.
- `firmware\application\external\analogtv`: existing Analog TV external app.
- `firmware\baseband`: M4 baseband processors.
- `firmware\baseband\CMakeLists.txt`: baseband image registration via `DeclareTargets`.
- `firmware\baseband\proc_am_tv.cpp`: current Analog TV baseband example, tagged `PAMT`.
- `firmware\application\baseband_api.*`: application-side control of baseband images.
- `firmware\common\message.hpp`: message types between application and baseband.

The existing `Analog TV` app is useful as a UI/display and baseband-loading example, but this project should not start there. The first milestone should prove the FM demodulation and sync extraction on a PC with saved IQ.

The current Mayhem feasibility finding is:

- A UI-only `.ppma` external app is practical for a menu entry, compact controls, and a placeholder or rendered 160x120 grayscale preview.
- Live analog FPV still decoding will likely require an external app plus a custom external M4 baseband image, because a UI-only external app does not directly receive the high-rate IQ/baseband stream needed for FM video demodulation and sync recovery.
- A full built-in firmware app should be deferred unless external app plus custom external baseband runs into size, message, or performance limits.

See the detailed report:

`docs\mayhem_external_app_feasibility.md`

A copy-ready placeholder skeleton is included at:

`mayhem_external_app_skeleton\fpv_still`

It is intentionally harmless: it has no baseband tag, appears as an RX external app when registered in Mayhem, and draws a 160x120 grayscale test pattern with the future UI labels `CH`, `FINE`, `GAIN`, `ALIGN`, `BRT`, `CON`, and `SIZE`.

If Mayhem is not available locally, clone it with:

```powershell
git clone https://github.com/portapack-mayhem/mayhem-firmware.git C:\Users\Render\Documents\mayhem-firmware
```

Then inspect the same folders above.

## Feasibility

This is feasible as a still-frame experiment, but it is sensitive to capture quality. The hard parts are not PNG output or downsampling; they are FM deviation, sample rate, gain, sync polarity, and timing stability. Expect to iterate with real captures before the output becomes recognizable.
