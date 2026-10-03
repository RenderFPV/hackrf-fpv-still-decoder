# Mayhem External App Feasibility

This note is based on the local Mayhem checkout inspected at:

`C:\Users\Render\Documents\Codex\2026-05-09\im-looking-to-add-digital-fpv\mayhem-firmware`

## Short Answer

A Mayhem SD-card external app (`.ppma`) is practical for the FPV Still user interface, menu entry, tuning controls, and 160x120 grayscale preview display.

A UI-only external app is not enough for the real analog FPV decoder because the decoder needs high-rate IQ/baseband samples. The likely least-invasive architecture is:

```text
Mayhem external app (.ppma UI)
+ custom external M4 baseband image appended into the .ppma
+ small message stream from baseband to UI carrying low-rate grayscale rows/frames
```

This avoids a full built-in app at first, while still putting RF-heavy processing on the baseband side where Mayhem expects it.

## 1. External App Structure

External apps live under:

`firmware\application\external\<app_name>`

Typical files:

- `main.cpp`: declares `initialize_app()` and an `application_information_t` record.
- `ui_<app>.hpp` / `ui_<app>.cpp`: Mayhem UI view.
- Optional helper files.

The app is registered in:

`firmware\application\external\external.cmake`

Two lists matter:

- `EXTCPPSRC`: source files compiled into the application ELF external sections.
- `EXTAPPLIST`: app image prefixes exported to `.ppma`.

Examples inspected:

- `firmware\application\external\calculator`: UI-only app with `m4_app_tag = {0, 0, 0, 0}`.
- `firmware\application\external\analogtv`: RX app with a baseband tag `PAMT`.
- `firmware\application\external\wefax_rx`: RX image-display workflow with a custom baseband tag `PWFX`.
- `firmware\application\external\fpv_detect`: existing FPV detector/scanner external app, useful for FPV channel lists and tuning behavior, but not a video decoder.

## 2. Building a `.ppma`

The Mayhem application build links all external app sections into `application.elf`, strips them out of the built-in firmware image, then exports each external app section with:

`firmware\tools\export_external_apps.py`

The relevant command is wired in:

`firmware\application\CMakeLists.txt`

The export script:

- extracts section `.external_app_<name>`;
- patches the app load address;
- appends the M4 baseband image if `m4_app_tag` is non-zero;
- writes `<name>.ppma` under the build application's output folder.

Expected output location after a normal Mayhem build:

`build\firmware\application\<app_name>.ppma`

The export script enforces the external app size limit using `maximum_application_size` from:

`firmware\tools\external_app_info.py`

## 3. SD Card Placement

Compiled external apps go on the SD card in:

`APPS`

Mayhem tooling confirms this in:

- `firmware\tools\copy_external_apps.sh`
- `firmware\CMakeLists.txt`
- `firmware\standalone\common\ui\file_path.cpp`

The copy script creates `APPS` and copies:

- `application/*.ppma`
- `standalone/*/*.ppmp`

Manual placement for this project would be:

```text
SDCARD:\APPS\fpv_still.ppma
```

## 4. Can External Apps Access Receiver/IQ Samples?

Not directly in the way the PC decoder needs.

The application-side external app runs on the UI/application side. It can receive low-rate messages and display data, but high-rate IQ/baseband processing belongs in an M4 baseband processor.

Relevant patterns:

- `analogtv` uses `m4_app_tag = {'P','A','M','T'}` and then uses spectrum/baseband callbacks.
- `wefax_rx` uses `m4_app_tag = {'P','W','F','X'}` and receives image data messages.
- `noaaapt_rx` similarly uses a baseband image to turn RF into image lines.
- `fpv_detect` uses RF tuning and channel statistics, but not raw video reconstruction.

Conclusion: a real live FPV still decoder should use a custom external baseband image, likely `proc_fpv_still.cpp`, to demodulate FM video, find sync, and emit 160-pixel grayscale rows or a small frame buffer to the UI.

## 5. Can an External App Tune Frequency/Gain/Sample Rate?

Yes. RX external apps can use the normal application-side models and baseband API:

- `receiver_model.set_target_frequency(...)`
- `receiver_model.set_sampling_rate(...)`
- `receiver_model.set_baseband_bandwidth(...)`
- `receiver_model.enable()` / `receiver_model.disable()`
- `LNAGainField`, `VGAGainField`, `RFAmpField`, or custom UI/preset mapping
- `baseband::set_sample_rate(...)`
- `baseband::run_prepared_image(...)` when the `.ppma` carries an external M4 image

For this project, the future UI should not expose separate LNA/VGA fields. Use a compact `GAIN` preset and map internally:

- `LOW`
- `MID`
- `HIGH`
- optional `AUTO`

Known-good PC capture equivalent for the current sample was LNA 32, VGA 16.

## 6. Can an External App Draw a 160x120 Grayscale Preview?

Yes.

Mayhem UI code can draw normal widgets and can push pixel lines directly to the display. Existing examples use:

`portapack::display.render_line(...)`

Examples:

- `firmware\application\external\wefax_rx\ui_wefax_rx.cpp`
- `firmware\application\external\noaaapt_rx\ui_noaaapt_rx.cpp`
- `firmware\application\external\analogtv\ui_tv.cpp`

A 160x120 grayscale preview is small enough to draw as lines. To keep RAM use low, the preferred embedded path is:

- keep one 160-pixel `ui::Color` line buffer on the UI side;
- stream rows from baseband or copy rows from a compact `uint8_t` frame buffer;
- convert grayscale to RGB565 only while drawing each line.

Avoid a full `ui::Color[160 * 120]` buffer unless testing proves memory is comfortable.

## 7. What Would Force an Internal Firmware App?

Start with external app plus custom external baseband. Move to a built-in firmware app only if one of these becomes true:

- The needed baseband/UI message types cannot be kept cleanly in external-app-compatible code.
- The `.ppma` size limit is exceeded by the UI plus appended M4 image.
- The decoder needs shared internal APIs that external app sections cannot use safely.
- Performance requires tighter integration than external app plus M4 message passing.
- The feature becomes stable enough to upstream as a normal Mayhem app.

## Recommended Architecture

Phase 1: UI-only `.ppma` skeleton.

- Appears in RX app menu.
- Opens a blank FPV Still screen.
- Draws a placeholder 160x120 grayscale test pattern.
- Shows only future UI labels: `CH`, `FINE`, `GAIN`, `ALIGN`, `BRT`, `CON`, `SIZE`.
- Uses no baseband tag yet.

Phase 2: external app plus custom external baseband.

- Add `firmware\baseband\proc_fpv_still.cpp`.
- Register a new external baseband target in `firmware\baseband\CMakeLists.txt`, for example `DeclareTargets(PFVS fpv_still)`.
- Change the app metadata `m4_app_tag` to `{'P','F','V','S'}`.
- Call `baseband::run_prepared_image(portapack::memory::map::m4_code.base())` from the UI view, following `wefax_rx` and `sstvrx`.
- Configure receiver sample rate and bandwidth from app-side controls.
- Send one low-rate 160x120 luminance frame, or line updates, from baseband to UI.

Phase 3: only consider internal integration if external app plus external baseband proves too constrained.

## Relevant Mayhem Files

- `firmware\application\external\external.cmake`
- `firmware\application\external\calculator\main.cpp`
- `firmware\application\external\analogtv\main.cpp`
- `firmware\application\external\analogtv\ui_tv.cpp`
- `firmware\application\external\wefax_rx\ui_wefax_rx.cpp`
- `firmware\application\external\fpv_detect`
- `firmware\application\CMakeLists.txt`
- `firmware\baseband\CMakeLists.txt`
- `firmware\baseband\proc_am_tv.cpp`
- `firmware\baseband\proc_wfm_audio.cpp`
- `firmware\baseband\proc_capture.cpp`
- `firmware\tools\export_external_apps.py`
- `firmware\tools\copy_external_apps.sh`
- `firmware\common\external_app.hpp`
