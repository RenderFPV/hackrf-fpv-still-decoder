# FPV Still Agent Instructions

## Protected Stable Baseline

The verified stable FPV Still baseline is:

`C:\Users\Render\Documents\baseline\candidates\throttle_5_lifecycle`

Do not modify that baseline under any circumstances.

Do not edit, rebuild in place, overwrite, delete, re-export, repackage, or
clean up files inside the protected baseline directory. For future tests, copy
the baseline into a new folder and modify only the copy.

Current verified stable baseline:

- FPV Still opens correctly.
- UI/header/theme is correct.
- Controls render correctly: `CH`, `FINE`, `GAIN`, `ALIGN`, `BRT`, `CON`, `SIZE`.
- No M0 Guru Meditation.
- Observed diagnostics: `P18`, `W19`, `R1`, `V18`.

Protected `.ppma`:

- Path: `C:\Users\Render\Documents\baseline\candidates\throttle_5_lifecycle\APPS\fpv_still.ppma`
- Size: `13572` bytes
- SHA256: `502DD45DAFB9881914569D014EE0E8D4697A807294E0F45C5A29DFA82FA87266`
- `m4_app_tag`: `PFPV`
- `m4_offset`: `4948`
- Embedded M4 payload: yes

Protected M4 payload:

- Path: `C:\Users\Render\Documents\baseline\candidates\throttle_5_lifecycle\PFPV.bin`
- Size: `8620` bytes
- SHA256: `86285E65159A4E0EC8A76A266502E7C258099B3D9BA76F53616745C6C5032D80`

## UI Freeze

Do not modify the stable UI visually or structurally:

- Do not redesign the screen.
- Do not change control layout.
- Do not change labels.
- Do not change header/theme behavior.
- Do not change preview drawing behavior.
- Do not add color image output.
- Do not add 320x240 preview.

Image content remains black-and-white/grayscale only.

## Previous Failure Constraints

- Do not put decoder state in `FPVStillView`.
- Do not put a full 160x120 framebuffer in `FPVStillView`.
- Do not put large arrays or large stack buffers in constructors or paint paths.
- Do not use `render_box`.
- Do not use `ui::Color[320]`.
- Keep any future line drawing on the known-stable `render_line` + `ui::Color[160]` path.
- Do not start backend work in the constructor.
- Gate backend messages with an active-view flag.
- Stop backend work on exit/destructor.
- Never draw unless FPV Still is the active view.
- Do not reuse stale `.ppma` files after changing M4/baseband code.

## Required Build Discipline

Every backend test must regenerate and verify the `.ppma` and M4 payload
together in a copied test directory. After every build, record:

- `.ppma` SHA256
- M4 payload SHA256
- `m4_app_tag`
- `m4_offset`
- memory address
- payload size
- SD-card `D:\APPS\fpv_still.ppma` SHA256 after copy

## RF/Baseband Plan

Do not write RF/baseband code until the reintegration analysis is approved.

Current analysis:

`C:\Users\Render\Documents\baseline\RF_BASEBAND_REINTEGRATION_PLAN.md`
