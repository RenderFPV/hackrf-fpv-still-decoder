# FPV Still RF Backend Rebuild Plan

Status: reset to UI-only baseline first.

## Non-Negotiable Image Scope

FPV Still is a black-and-white/grayscale preview project.

- No color decode.
- No chroma handling.
- No color framebuffer.
- No color preview/test pattern.
- 160x120 grayscale is the protected PortaPack target.
- 320x240 remains future PC/debug only.

Mayhem chrome may continue to use the active theme/skin, but FPV Still image content must remain luminance-only.

## Crash History Constraints

1. Large UI-owned buffers caused hard faults.
   - Do not store a 160x120 framebuffer in `FPVStillView`.
   - Do not store decoder state in `FPVStillView`.

2. `render_box(160x2)` plus `ui::Color[320]` caused hard faults.
   - Do not use `render_box` for FPV preview experiments yet.
   - Do not use `ui::Color[320]`.
   - If line drawing returns later, use `display.render_line()` with one `ui::Color[160]` line buffer.

3. M4 payload/package mismatch caused faults into unrelated code.
   - Every backend test must rebuild and export app plus payload together.
   - Never reuse a stale `.ppma` after changing M4 code.
   - Record `.ppma` SHA256, M4 payload SHA256, `m4_app_tag`, `m4_offset`, app memory address, and payload size.

4. Notification and lifecycle experiments drew over the Receive/App list.
   - Do not start backend work in the constructor.
   - Do not draw unless the FPV Still view is active.
   - Stop all backend work on back/exit/destructor.

## Stage 0 - UI-Only Baseline

Goal: freeze a harmless baseline.

- FPV Still appears under Receive.
- App opens normally.
- UI/header/theme follows Mayhem behavior.
- Controls render: `CH`, `FINE`, `GAIN`, `ALIGN`, `BRT`, `CON`, `SIZE`.
- Raceband R1-R8 only.
- Preview is static grayscale only.
- `m4_app_tag = {0,0,0,0}`.
- No M4 payload packaged.
- No RF.
- No FIFO.
- No decoder object.

This stage must be confirmed on hardware before Stage 1.

## Stage 1 - Backend Packaging Heartbeat

Goal: prove app plus M4 payload packaging without image data.

- Add the smallest possible M4 payload.
- No RF.
- No FIFO image data.
- No line streaming.
- No framebuffer.
- Send only a harmless heartbeat/status value.
- UI displays a tiny status indicator only.

Required report for each build:

- `.ppma` SHA256
- M4 payload SHA256
- `m4_app_tag`
- `m4_offset`
- app memory address
- payload size

## Stage 2 - RF Tune/Start/Stop Only

Goal: prove receiver lifecycle without decoding.

- Tune `CH + FINE`.
- Default `CH = R5`, `FINE = -4 MHz`, tuned `5802 MHz`.
- Raceband only:
  - R1 5658 MHz
  - R2 5695 MHz
  - R3 5732 MHz
  - R4 5769 MHz
  - R5 5806 MHz
  - R6 5843 MHz
  - R7 5880 MHz
  - R8 5917 MHz
- No video decode.
- No image output.
- Back/exit must stop safely.

## Stage 3 - RF-Derived Meter

Goal: prove live RF samples are arriving.

- Compute one tiny value only, such as average magnitude/RSSI.
- UI displays one number or small bar.
- VTX on/off should visibly affect the value.
- No framebuffer.
- No preview line streaming.

## Stage 4 - One RF-Derived Grayscale Line

Goal: prove preview can be driven by live RF without full-frame state in the view.

- Generate one 160-byte grayscale line from RF-derived data.
- Draw with `display.render_line()` only.
- Use one `ui::Color[160]` buffer.
- No `render_box`.
- No `ui::Color[320]`.
- No full framebuffer in `FPVStillView`.
- Keep update rate slow and safe.

## Stage 5 - Minimal FPV Demod/Sync

Goal: recover a recognizable FPV image.

Port only the minimal PC-side concepts:

- FM video demod from IQ/baseband samples.
- Luminance normalization.
- Crude sync detection.
- Line reconstruction.
- 160x120 grayscale output.

No OSD optimization, no color, no audio, no broadcast TV channel logic.
