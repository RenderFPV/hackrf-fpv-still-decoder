# FPV Still Mayhem Live Architecture Plan

Date: 2026-05-14

Status: planning only. The current FPV Still app remains the frozen UI-only baseline.

## Goal

Recover a low-rate 160x120 grayscale preview from 5.8 GHz analog FPV on HackRF One + PortaPack H4M/Mayhem without repeating the M0 hard fault caused by placing large decoder/framebuffer state inside `FPVStillView`.

The future live path still targets:

- Raceband R1-R8 only.
- `CH`, `FINE`, `GAIN`, `ALIGN`, `BRT`, `CON`, `SIZE`.
- 160x120 grayscale default.
- Around 1 FPS.
- No audio, transmit, color, 320x240 live mode, or generic broadcast TV behavior.

## Relevant Mayhem Patterns

### External app + bundled baseband image

Reference files:

- `firmware/application/external/analogtv/main.cpp`
- `firmware/application/external/noaaapt_rx/main.cpp`
- `firmware/tools/export_external_apps.py`
- `firmware/application/baseband_api.cpp`

External apps can include an M4/baseband tag in their `application_information_t`. The packaging script appends the matching baseband `.bin` into the `.ppma`, patches the app relocation address, and sets `m4_app_offset`.

Important limits from the exporter:

- External app image budget is 32 KiB total.
- If an M4 image is bundled, app code is relocated after the M4 image inside the same package/load area.
- If `m4_app_tag` is zero, no M4 image is packaged.

The UI starts the packaged M4 code with:

```cpp
baseband::run_prepared_image(portapack::memory::map::m4_code.base());
```

and stops it with:

```cpp
receiver_model.disable();
baseband::shutdown();
```

### RF tuning and receiver setup

Reference files:

- `firmware/application/external/analogtv/analog_tv_app.cpp`
- `firmware/application/external/noaaapt_rx/ui_noaaapt_rx.cpp`

The UI-side app is responsible for configuring `receiver_model`:

- target frequency
- sampling rate
- baseband bandwidth
- gain fields or presets
- enable/disable receiver

For FPV Still, that means:

- `CH` selects nominal Raceband frequency.
- `FINE` applies offset.
- R5 + -4 MHz tunes to 5802 MHz, but R5 is still nominally 5806 MHz.
- `GAIN` maps to internal LNA/VGA presets.

### Baseband to UI communication

Reference files:

- `firmware/common/message.hpp`
- `firmware/common/message_queue.hpp`
- `firmware/common/portapack_shared_memory.hpp`
- `firmware/application/event_m0.cpp`
- `firmware/baseband/tv_collector.cpp`
- `firmware/baseband/spectrum_collector.cpp`
- `firmware/application/external/analogtv/ui_tv.hpp`
- `firmware/application/external/analogtv/ui_tv.cpp`
- `firmware/baseband/proc_noaaapt_rx.cpp`
- `firmware/application/external/noaaapt_rx/ui_noaaapt_rx.cpp`

Mayhem has two common M4-to-M0 data patterns:

1. Push normal messages into `shared_memory.application_queue`.
2. Send one message that contains a pointer to an M4-owned FIFO, then drain that FIFO from the UI on `DisplayFrameSync`.

Ordinary queued messages are constrained by:

```cpp
Message::MAX_SIZE = 512
```

This is why `NoaaAptRxImageDataMessage` and `WeFaxRxImageDataMessage` carry 400-byte image chunks, and why `ChannelSpectrum` streaming uses a FIFO pointer rather than copying large buffers through the queue.

### Existing live display data references

Analog TV:

- `analogtv` uses a packaged M4 app (`PAMT`), starts it with `run_prepared_image`, receives `ChannelSpectrumFIFO*`, drains `ChannelSpectrum` entries on `DisplayFrameSync`, and draws lines with `display.render_line`.
- It is useful as a UI/baseband/FIFO/display reference, not as the FPV demod algorithm.

NOAA APT:

- `noaaapt_rx` uses M4-side demod and sends 400-byte grayscale image chunks as copied messages.
- UI converts bytes to `ui::Color` rows and renders incrementally.
- Useful for image-chunk display and for keeping UI-side image state small.

WEFAX:

- Similar to NOAA: M4 sends image chunks and status messages.
- Useful as another image-streaming reference.

Spectrum collectors:

- `spectrum_collector` and `tv_collector` own FIFOs in M4/baseband memory and send only a FIFO pointer to UI.
- Useful for avoiding big copied messages and for back-pressure/drop behavior.

## Memory Constraints

Known from local code:

- `Message::MAX_SIZE`: 512 bytes.
- Shared message queues: 2 KiB each (`1 << 11`) in shared memory.
- Shared memory region: 8 KiB.
- External app sections are 32 KiB maximum in the build/export tooling.
- M4 prepared code region is 32 KiB, followed by shared memory.
- Baseband thread working area is 4096 bytes.
- Baseband DMA buffer allocation uses 8192 baseband samples.

Practical implication:

- Do not store a 160x120 8-bit framebuffer (`19,200` bytes) in `FPVStillView`.
- Do not copy a full framebuffer through `MessageQueue`.
- Keep UI objects small. The UI should own controls, a tiny line draw buffer, counters/status, and maybe the latest FIFO pointer.
- M4/baseband may own DSP state, small FIFOs, and possibly one full framebuffer if code size/RAM tests prove it safe, but that should not be the first live design.

## Option Comparison

### A. Baseband outputs 160-byte grayscale lines

Feasibility: high.

RAM risk: low. A FIFO of four line records is roughly 4 x `(metadata + 160)` bytes, well below the risk of a 19.2 KiB UI framebuffer.

CPU risk: moderate. M4 still does RF sample handling, FM demod, sync detection, and line reconstruction. UI only maps one grayscale line to `ui::Color` and calls `display.render_line`.

UI responsiveness risk: low. UI drains queued lines on `DisplayFrameSync`; if it falls behind, old lines can be dropped.

Implementation complexity: moderate. Requires a new FPV-specific message/FIFO type and a small custom baseband processor.

Closest Mayhem pattern:

- `tv_collector` / `ChannelSpectrumFIFO`
- `analogtv::TVWidget` draining FIFO on `DisplayFrameSync`
- `noaaapt_rx` drawing image rows incrementally

External app + custom baseband fit: good. The `.ppma` can package a small FPV baseband image once the image size is proven under the external app budget.

Verdict: recommended first live architecture.

### B. Baseband outputs 160x8 or 160x16 tiles

Feasibility: medium.

RAM risk: moderate. A 160x8 tile is 1280 bytes, and 160x16 is 2560 bytes.

CPU risk: low-to-moderate for UI because fewer draw callbacks are needed, but M4 still does the same DSP.

UI responsiveness risk: moderate. Tiles reduce message frequency but increase burst size and copy/draw time.

Implementation complexity: moderate-to-high. Tiles cannot fit in `Message::MAX_SIZE`, so they need an M4-owned FIFO or shared pointer protocol.

Closest Mayhem pattern:

- `ChannelSpectrumFIFO` pointer model, not copied messages.

External app + custom baseband fit: possible, but not the safest first step.

Verdict: useful later if line-by-line drawing is too chatty, but not first.

### C. Baseband owns full 160x120 framebuffer; UI references/copies it

Feasibility: possible but risky.

RAM risk: high. The framebuffer alone is 19,200 bytes, before demod buffers, sync state, FIFOs, DMA, stack, and code. It is better on M4 than inside the UI view, but still needs careful map/stack/heap proof.

CPU risk: moderate. M4 can write the frame once and UI can draw it at 1 FPS, but full-frame transfer/copy semantics need care.

UI responsiveness risk: moderate. If UI draws 120 lines in one refresh, it may visibly stall. It must be chunked.

Implementation complexity: high. Requires safe ownership/versioning: double-buffer, frame-ready flag, no UI reading while M4 writes.

Closest Mayhem pattern:

- NOAA/WEFAX image chunks are closer than a full shared framebuffer.

External app + custom baseband fit: possible only after memory sizing is proven.

Verdict: not recommended for first live integration.

### D. UI-side decoder owns everything

Feasibility: poor.

RAM risk: very high. This is the pattern that already caused the M0 hard fault when large decoder/framebuffer state lived inside `FPVStillView`.

CPU risk: high. UI/M0 would be doing work that belongs in M4/baseband.

UI responsiveness risk: high. DSP and frame reconstruction would compete with controls, drawing, and app navigation.

Implementation complexity: deceptively simple at first, but unstable.

Closest Mayhem pattern:

- None appropriate for this workload.

External app + custom baseband fit: no.

Verdict: reject.

## Recommended Architecture

Use a custom FPV-specific M4/baseband processor and line-streamed UI display.

### Ownership

`FPVStillView` owns:

- UI controls only.
- Raceband table.
- Frequency/gain mapping.
- A `LineFIFO*` pointer or equivalent.
- A small `ui::Color line_buffer[160]` for drawing one line.
- A few counters/status fields.

Custom FPV baseband owns:

- RF/baseband sample processing.
- FM video demod state.
- Sync detection state.
- Line reconstruction state.
- Brightness/contrast normalization state.
- A small FIFO of reconstructed 160-byte grayscale lines.
- Optional tiny diagnostics counters.

No full 160x120 framebuffer should live in `FPVStillView`.

### Data flow

1. UI starts packaged FPV M4 image with `baseband::run_prepared_image(...)`.
2. UI configures `receiver_model`:
   - target frequency = Raceband nominal + FINE
   - sampling rate/bandwidth chosen by actual M4 feasibility
   - gain preset
3. UI sends an FPV config message to M4:
   - channel index
   - fine offset
   - align
   - brightness
   - contrast
   - output width/height fixed at 160x120 for now
4. M4 sends a FIFO pointer/config message to UI.
5. M4 pushes reconstructed line records:
   - frame id
   - y index, 0-119
   - status flags
   - 160 grayscale pixels
6. UI drains the FIFO on `DisplayFrameSync`.
7. UI converts each line to `ui::Color[160]` and renders at preview origin.
8. On app exit, UI stops receiver and calls `baseband::shutdown()`.

### Proposed line record

Keep each record small and naturally aligned:

```cpp
struct FPVStillLine {
    uint16_t frame_id;
    uint8_t y;
    uint8_t flags;
    uint8_t pixels[160];
};
```

This is about 164 bytes per line. A FIFO depth of 4-8 lines is reasonable for first tests. The queue message should carry only a pointer to that FIFO, following the `ChannelSpectrumConfigMessage` pattern.

Do not copy 160x8 tiles through `MessageQueue`; they exceed `Message::MAX_SIZE`.

## CPU/DSP Plan

Start conservative:

1. M4 accepts raw `buffer_c8_t` from `BasebandThread`.
2. Implement integer/fixed-point quadrature FM demod or reuse `dsp::demodulate::FM` if the input rate/format matches.
3. Decimate early enough to make sync detection feasible.
4. Detect horizontal sync and estimate samples-per-line.
5. Generate one 160-pixel luminance line at a time.
6. Push line records only when a plausible frame/line lock exists.
7. If lock fails, send a lightweight status message, not image data.

The PC decoder remains the algorithm reference, but the embedded implementation should be line-oriented and fixed-buffer from the beginning.

## Risk Notes

- 10 MS/s may be too heavy for the existing Mayhem M4 path. The first live branch must measure what sample rates actually work without M4 overruns.
- `MessageQueue` is not a bulk-pixel transport. Use pointer-to-FIFO or 400-byte copied chunks only.
- `DisplayFrameSync` is a good UI drain trigger, but drawing too many lines in one tick may still hurt responsiveness. Cap lines drawn per tick if needed.
- External `.ppma` + custom M4 image is supported by existing patterns, but the app + baseband image must fit the 32 KiB external app package budget.
- If the custom FPV baseband image cannot fit, move FPV Still from external app to firmware-integrated app/baseband.

## Next Milestone

Do not re-enable live RF yet.

Next implementation should be a harmless plumbing test:

1. Add only message/FIFO type definitions for FPV Still line streaming.
2. Add a tiny custom M4 baseband image that does not use RF samples yet.
3. Baseband pushes synthetic 160-byte grayscale lines through the FIFO.
4. UI drains FIFO and draws lines.
5. Keep receiver disabled for this milestone.
6. Verify app exit/back remains stable and no M0/M4 faults occur.

Only after that passes on hardware should the M4 processor consume real baseband samples.
