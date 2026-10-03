# FPV Still M0 Hard Fault Report

Date: 2026-05-14

## Fault

Device output:

```text
M0 Guru Meditation Hard Fault
R0: 2000A575
R1: 00000000
R2: 00004BB0
R3: 10084240
R12: 000890AD
LR: 1008362D
PC: 0008908C
```

## Address mapping

The firmware map resolves:

- `PC = 0x0008908C` into newlib `memmove`, near `memmove+0x8`.
- `R12 = 0x000890AD` into `memset+1`.
- The generated `fpv_still.ppma` was relocated at runtime. Its header placed the app at `0x10082ABC`.
- `LR = 0x1008362D` maps back to the external app link address around `0xAE070B70`.

That adjusted LR lands in:

```text
ui::external_app::fpv_still::FPVStillView::FPVStillView(ui::NavigationView&)
```

The disassembly at that point is the return from a `__memset_veneer` call used while constructing the view.

## Root cause

The immediate crash is not a live sample buffer overrun yet. The M0 fault occurs while the FPV Still view is being constructed and a large block is being zero-filled.

Register interpretation for the mapped call:

- `R0 = 0x2000A575`: destination address for the zero-fill.
- `R1 = 0x00000000`: the `memset` fill value, not a null source pointer.
- `R2 = 0x00004BB0`: zero-fill length, about 19 KB.

That size matches the large UI-side decoder/framebuffer state introduced during the first live RF/baseband attempt. The UI view became too heavy for the external app/M0 runtime path, especially with the inactive decoder framebuffer and live message/FIFO state embedded directly in `FPVStillView`.

## Recovery change

The recovery build gates live RF/baseband off and restores a small TEST-only UI:

- `m4_app_tag` is set back to `image_tag_none`.
- No baseband image is packaged into the `.ppma`.
- `FPVStillView` no longer owns the large `FPVDecoder` framebuffer object.
- Receiver/baseband start/stop calls are removed from the UI view.
- The `SRC` field still shows `TEST` and `LIVE`, but selecting `LIVE` displays `LIVE OFF` and does not start RF/baseband code.
- The 160x120 placeholder/test pattern remains available.

## Next safe architecture

Before re-enabling live RF, the decoder state should not live as a large object inside the external UI view. Safer options:

- Keep only a small row/tile buffer in the UI app and render rows as they arrive.
- Put the larger sample/framebuffer state on the M4/baseband side and stream a compact 160-pixel grayscale row message to the UI.
- If a full 160x120 framebuffer is needed, allocate it in a carefully reviewed static/shared location rather than as part of `FPVStillView` construction.

Live RF should stay disabled until the baseband-to-UI message format and memory ownership are made small and explicit.
