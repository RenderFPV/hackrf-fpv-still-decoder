# FPV Still Live RF Integration Report

Date: 2026-05-14

## Goal

Begin the first live RF experiment for FPV Still while preserving the working UI/test-frame path. This revision is focused on 5.8 GHz analog FPV still-image recovery, not broadcast analog TV reception.

## Scope

- Raceband only: R1 through R8.
- Protected live display target: 160x120 grayscale.
- Default source mode: `TEST`, using the synthetic framebuffer.
- Optional source mode: `LIVE`, starting an experimental FPV-specific M4/baseband image.
- Initial test case: R5 + FINE -4 MHz = 5802 MHz.
- Gain preset `MID` maps to the PC baseline equivalent of LNA 32 / VGA 16.

## Why This Is Not the Analog TV Pipeline

The PC decoder already proved that a recognizable FPV image can be recovered from a 10 MS/s HackRF capture using a simple FPV-specific path:

IQ -> FM discriminator -> composite-like video waveform -> sync/line recovery -> 160x120 grayscale frame.

Mayhem's existing Analog TV app/baseband is useful as a reference for app structure, baseband startup, and display plumbing. It is not used as the decoder assumption for FPV Still because FPV Still does not need broadcast TV channel plans, audio carrier support, full-frame analog TV output, or broadcast-TV-specific tuning behavior.

## Implemented First Live Path

This revision adds an experimental baseband processor:

- `firmware/baseband/proc_fpv_still.hpp`
- `firmware/baseband/proc_fpv_still.cpp`
- Baseband image tag: `PFPV`

The app now has a source selector:

- `TEST`: synthetic 160x120 framebuffer, safe default.
- `LIVE`: starts the bundled `PFPV` M4 image and attempts a live FPV still-frame decode.

In LIVE mode the UI configures:

- Frequency = selected Raceband channel + FINE offset.
- R5 with FINE -4 MHz tunes to 5802 MHz.
- Sampling rate request = 10 MS/s.
- Baseband bandwidth request = 10 MHz.
- RF amp disabled, matching the PC `hackrf_transfer` baseline where `-a` was not used.
- Gain presets:
  - LOW: LNA 16, VGA 8
  - MID/AUTO: LNA 32, VGA 16
  - HIGH: LNA 40, VGA 32

## Current Decoder Behavior

The M4 processor performs a minimal fixed-point friendly FM discriminator:

`fm_video = I0 * Q1 - Q0 * I1`

It then tries to:

- Track video min/max slowly.
- Score both sync polarities.
- Use rough sync-to-sync timing around the NTSC 10 MS/s line estimate.
- Accumulate active line samples into 160 horizontal pixels.
- Combine pairs of source lines into 120 preview rows.
- Send compact 160-byte grayscale rows to the UI.

The UI receives rows through the existing `ChannelSpectrumFIFO` type as a compact transport container only. The data is not spectrum data, and this does not use broadcast Analog TV demodulation.

## Expected Limitations

This is a first live experiment, so it may show noise, partial bands, unstable rows, or no recognizable image yet.

Known rough edges:

- Line timing is initialized around 636 samples per line for NTSC at 10 MS/s.
- PAL is not handled in the M4 live path yet.
- Vertical/frame-start detection is intentionally minimal.
- The luma mapping is a rough live min/max normalization.
- The actual hardware/firmware receive path may not deliver a clean 10 MS/s stream in the exact same shape as `hackrf_transfer`.
- If the UI receives no rows, the blocker is likely baseband image startup, sample-rate configuration, M4 CPU load, FIFO transport, or RF gain/tuning.

## Test Procedure

1. Set VTX to Raceband R5.
2. Open FPV Still.
3. Confirm `SRC` is `TEST` first.
4. Confirm `CH` is `R5` and `FINE` is `-4`.
5. Set `GAIN` to `MID`.
6. Switch `SRC` to `LIVE`.
7. Look for row/status updates and any recognizable 160x120 grayscale image.
8. If unstable, return `SRC` to `TEST` or exit the app. The app stops the live receiver/baseband path on exit.

## Next Step

If LIVE produces rows but no image, the next iteration should add baseband-side debug counters or a reduced waveform/line debug view. If LIVE produces no rows, verify whether the `PFPV` baseband image is being packaged into the `.ppma` and whether the receiver/baseband is actually starting at the requested 10 MS/s.

## Build Result

The FPV Still baseband and application compiled in the Mayhem Docker build environment.

Generated artifacts:

- App package: `C:\Users\Render\Documents\Codex\2026-05-09\im-looking-to-add-digital-fpv\mayhem-firmware\build\firmware\application\fpv_still.ppma`
- Matching SD-card copy: `C:\Users\Render\Documents\Codex\2026-05-09\im-looking-to-add-digital-fpv\mayhem-firmware\build\firmware\firmware_tar\APPS\fpv_still.ppma`
- FPV baseband image: `C:\Users\Render\Documents\Codex\2026-05-09\im-looking-to-add-digital-fpv\mayhem-firmware\build\firmware\baseband\PFPV.bin`
- Application image: `C:\Users\Render\Documents\Codex\2026-05-09\im-looking-to-add-digital-fpv\mayhem-firmware\build\firmware\application\application.bin`

The `.ppma` SHA-256 is:

`DE89905AD0BA77560DF75B4F5E2E12A14E0274E35BCC18D925A6BE6989FF788E`
