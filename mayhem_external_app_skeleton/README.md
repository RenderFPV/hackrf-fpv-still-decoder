# Mayhem External App Skeleton

This folder contains a copy-ready Mayhem external app skeleton for the future FPV Still preview UI.

It is intentionally UI-only for now:

- no live RF decode;
- no custom baseband image yet;
- no full firmware integration;
- placeholder 160x120 grayscale test pattern only.

## Copy Into Mayhem

Copy this folder:

`mayhem_external_app_skeleton\fpv_still`

to the Mayhem tree as:

`firmware\application\external\fpv_still`

Then edit:

`firmware\application\external\external.cmake`

Add these source files to `EXTCPPSRC`:

```cmake
external/fpv_still/main.cpp
external/fpv_still/ui_fpv_still.cpp
```

Add this app prefix to `EXTAPPLIST`:

```cmake
fpv_still
```

Build Mayhem normally. The expected generated app is:

`build\firmware\application\fpv_still.ppma`

Place it on the PortaPack SD card:

`APPS\fpv_still.ppma`

## Future Baseband Hook

The skeleton uses:

```cpp
/*.m4_app_tag = portapack::spi_flash::image_tag_none */ {0, 0, 0, 0}
```

That is correct for the placeholder UI-only app.

When the real decoder moves to Mayhem, add a custom external baseband image, for example tag `PFVS`, and change the metadata to:

```cpp
/*.m4_app_tag = portapack::spi_flash::image_tag_fpv_still */ {'P', 'F', 'V', 'S'}
```

The corresponding baseband target would be registered in `firmware\baseband\CMakeLists.txt`, near other external images:

```cmake
set(MODE_CPPSRC
    proc_fpv_still.cpp
)
DeclareTargets(PFVS fpv_still)
```

At that point, the UI should call `baseband::run_prepared_image(portapack::memory::map::m4_code.base())` and receive low-rate grayscale frame/row messages from the custom M4 processor.
