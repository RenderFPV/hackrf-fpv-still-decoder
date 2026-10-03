# Roadmap

## Milestone 1: PC Offline Still Decoder

- [x] Create modular Python skeleton.
- [x] Read complex64 IQ from file.
- [x] Add optional `hackrf_transfer` unsigned-byte IQ reader.
- [x] FM demodulate with phase difference.
- [x] Normalize composite waveform.
- [x] Attempt horizontal sync detection.
- [x] Attempt vertical/frame-start detection.
- [x] Extract luminance-only grayscale frame.
- [x] Save raw and resized PNGs.
- [x] Save waveform/sync debug artifacts.
- [ ] Test with a known-good analog FPV recording.
- [ ] Tune active video crop per NTSC/PAL capture.
- [ ] Add a small metadata sidecar for capture frequency, gains, and sample rate.

Success condition:

> Given a strong analog FPV signal recording, produce one recognizable black-and-white still image.

## Milestone 2: Better PC Robustness

- [ ] Add sample-rate-aware decimation after FM demodulation.
- [ ] Improve sync detection by measuring sync pulse width and blanking level.
- [ ] Add automatic luminance inversion detection.
- [ ] Add rolling frame extraction and choose the best frame by sync confidence.
- [ ] Add CLI support for live `hackrf_transfer` capture followed by offline decode.
- [ ] Add optional SoapySDR or pyhackrf live capture backend.
- [ ] Build a small corpus of test recordings with expected debug notes.

## Milestone 3: Mayhem/PortaPack Architecture Decision

Use the PC decoder results to decide how much processing must live on the baseband M4.

Current finding:

- [x] Inspect Mayhem external app structure and `.ppma` export path.
- [x] Confirm a UI-only external app can appear in the RX menu and draw a 160x120 placeholder preview.
- [x] Confirm live decoder work should not be UI-only because high-rate IQ/baseband samples belong on the M4 baseband side.
- [x] Add a feasibility report at `docs\mayhem_external_app_feasibility.md`.
- [x] Add a copy-ready placeholder skeleton at `mayhem_external_app_skeleton\fpv_still`.

Likely direction:

- External app for the UI under `firmware\application\external\fpv_still` or similar.
- Custom external baseband image under `firmware\baseband\proc_fpv_still.cpp`.
- Register the baseband image in `firmware\baseband\CMakeLists.txt` with a new four-character tag.
- In the external app `main.cpp`, set the app's `m4_app_tag` to the new baseband tag, following examples such as `application\external\analogtv\main.cpp` and `application\external\wefax_rx\main.cpp`.

Why not UI-only external app:

- The RF/baseband-heavy work needs access to high-rate samples.
- Current external apps are good for UI and app metadata, but the demod/sync loop belongs closer to `firmware\baseband`.
- Mayhem external app docs mention selecting a needed baseband in `main.cpp`; the inspected tree confirms examples use `m4_app_tag` for this.

Useful Mayhem examples:

- `firmware\application\external\analogtv`: external app that loads `PAMT`.
- `firmware\baseband\proc_am_tv.cpp`: simple baseband stream-to-display-ish example.
- `firmware\application\external\noaaapt_rx` and `firmware\baseband\proc_noaaapt_rx.cpp`: image-from-radio receive workflow.
- `firmware\application\external\wefax_rx` and `firmware\baseband\proc_wefaxrx.cpp`: slow image receive workflow.
- `firmware\baseband\proc_wfm_audio.cpp`: wideband FM demod reference.
- `firmware\baseband\proc_capture.cpp`: raw capture reference.

## Milestone 4: C/C++ Port Strategy And Minimal UI

- [ ] Port only the proven minimal PC algorithm.
- [ ] Use fixed-point or simple integer arithmetic where possible.
- [ ] Process chunks: capture/demod a short buffer, find sync, fill low-res grayscale framebuffer, repeat.
- [ ] Target 1 FPS, not real-time full-rate video.
- [ ] Avoid color, audio, and full-frame-rate rendering.
- [ ] Send only low-rate image rows or framebuffer updates to the UI side.
- [ ] Keep `160x120` as the protected PortaPack display target.
- [ ] Keep `320x240` experimental for PC/debug preview only until it recovers more real detail.
- [ ] Keep the future UI compact: `CH`, `FINE`, `GAIN`, `ALIGN`, `BRT`, `CON`, `SIZE`.
- [ ] Map `CH` to nominal FPV channel frequency and apply `FINE` as an offset. Example: R5 nominal 5806 MHz plus -4 MHz tunes 5802 MHz.
- [ ] Use gain presets in UI only: `LOW`, `MID`, `HIGH`, and optionally `AUTO`.
- [ ] Hide developer controls from the normal PortaPack UI: separate LNA/VGA, sync threshold, line tolerance, crop values, raw output, denoise, sharpen, gamma, scaler choices, and arbitrary width/height.

## Milestone 5: Firmware Integration Options

External app plus external/custom baseband is the first Mayhem target. Built-in firmware integration should only be considered if:

- The baseband image needs shared code or message types that are awkward as an external app.
- Performance requires tighter integration.
- The feature is stable enough to justify a normal Mayhem PR.

Do not start firmware work until the PC prototype can decode at least one recognizable still from a repeatable recording.
