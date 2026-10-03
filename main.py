"""Command-line entry point for the FPV still-frame decoder."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from capture_hackrf import read_complex64_iq, read_hackrf_u8_iq
from composite_sync import STANDARDS, detect_sync_pulses
from display_frame import save_debug_artifacts, save_png
from fm_demod import moving_average_lowpass, quadrature_demod, remove_dc_and_normalize
from frame_extract import extract_luma_frame


CHANNELS_MHZ = {
    "R1": 5658.0,
    "R2": 5695.0,
    "R3": 5732.0,
    "R4": 5769.0,
    "R5": 5806.0,
    "R6": 5843.0,
    "R7": 5880.0,
    "R8": 5917.0,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decode a rough grayscale still frame from analog FPV HackRF IQ."
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--iq", help="Input IQ file")
    inputs.add_argument(
        "--composite",
        help="Input demodulated composite waveform file as float32, for decoder fallback/debug",
    )
    parser.add_argument("--sample-rate", type=float, required=True, help="Input sample rate in Hz")
    parser.add_argument("--standard", choices=sorted(STANDARDS), default="ntsc")
    parser.add_argument("--out", default="frame.png", help="Output PNG path")
    parser.add_argument("--debug-dir", default="debug", help="Directory for debug artifacts")
    ui = parser.add_argument_group("future PortaPack UI controls")
    ui.add_argument("--ch", help="Channel label for future UI metadata, for example R5")
    ui.add_argument(
        "--fine",
        type=float,
        default=0.0,
        help="Fine tune offset in MHz around --ch nominal frequency; metadata only for offline IQ",
    )
    ui.add_argument(
        "--gain",
        choices=["LOW", "MID", "HIGH", "AUTO", "low", "mid", "high", "auto"],
        help="Future UI RF gain preset metadata; developer capture can still use explicit LNA/VGA",
    )
    ui.add_argument(
        "--align",
        type=int,
        default=0,
        help="Simple frame alignment nudge, added to --frame-start-offset",
    )
    ui.add_argument("--brt", "--brightness", dest="brightness", type=float, default=0.0, help="Brightness offset")
    ui.add_argument("--con", "--contrast", dest="contrast", type=float, default=1.0, help="Contrast multiplier")
    ui.add_argument(
        "--size",
        choices=["160", "160x120", "320", "320x240"],
        help="Future UI size selector; 320x240 still requires --experimental-preview",
    )
    advanced = parser.add_argument_group("advanced PC/developer options")
    parser.add_argument(
        "--sample-format",
        choices=["complex64", "hackrf_u8"],
        default="complex64",
        help="IQ file format. complex64 is the primary path.",
    )
    advanced.add_argument("--max-samples", type=int, help="Limit samples read from input")
    advanced.add_argument("--output-width", type=int, default=160)
    advanced.add_argument("--output-height", type=int, default=120)
    advanced.add_argument("--width", type=int, help="Final output width")
    advanced.add_argument("--height", type=int, help="Final output height")
    advanced.add_argument(
        "--target",
        choices=["portapack", "preview", "raw"],
        help="Output target: portapack=160x120, preview=320x240, raw=unscaled reconstructed frame",
    )
    advanced.add_argument(
        "--experimental-preview",
        action="store_true",
        help="Allow preview/display sizes above the 160x120 PortaPack baseline",
    )
    advanced.add_argument(
        "--frame-lines",
        type=int,
        help="Number of detected video lines to assemble; default uses one field",
    )
    advanced.add_argument(
        "--skip-lines",
        type=int,
        default=0,
        help="Drop this many detected lines after the chosen frame/field start",
    )
    advanced.add_argument(
        "--frame-start-offset",
        type=int,
        default=0,
        help="Additional detected-line offset from chosen frame/field start",
    )
    advanced.add_argument("--crop-top", type=int, default=0, help="Drop lines from top after assembly")
    advanced.add_argument("--crop-bottom", type=int, default=0, help="Drop lines from bottom after assembly")
    advanced.add_argument(
        "--minimal-processing",
        action="store_true",
        help="Keep post-processing to the current baseline behavior",
    )
    advanced.add_argument(
        "--demod-gain",
        type=float,
        default=1.0,
        help="Scale FM-demodulated waveform before normalization when --fm-deviation is not set",
    )
    advanced.add_argument(
        "--fm-deviation",
        type=float,
        help="Expected FM deviation in Hz; converts phase delta to deviation-normalized video",
    )
    advanced.add_argument(
        "--sync-threshold",
        type=float,
        help="Manual sync threshold on normalized signed waveform; default uses percentile auto-threshold",
    )
    advanced.add_argument(
        "--line-tolerance",
        type=float,
        default=0.25,
        help="Allowed fractional sync-to-sync line length error, default 0.25",
    )
    advanced.add_argument(
        "--crop-start",
        type=float,
        help="Active video crop start as fraction of each line after sync, default depends on standard",
    )
    advanced.add_argument(
        "--crop-end",
        type=float,
        help="Active video crop end as fraction of each line after sync, default depends on standard",
    )
    advanced.add_argument(
        "--sync-polarity",
        choices=["auto", "negative", "positive"],
        default="auto",
        help="Composite sync polarity after FM demodulation",
    )
    advanced.add_argument(
        "--invert-video",
        action="store_true",
        help="Invert final black/white mapping",
    )
    advanced.add_argument(
        "--invert-luma",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    advanced.add_argument("--smooth", type=int, default=1, help="Optional moving-average taps")
    advanced.add_argument(
        "--save-composite",
        help="Optional path to save normalized demodulated composite waveform as float32",
    )
    advanced.add_argument(
        "--save-demod-waveform",
        action="store_true",
        help="Write debug/demod_waveform.npy for offline tuning",
    )
    return parser


def output_size_for_args(args: argparse.Namespace) -> tuple[int | None, int | None]:
    if args.target == "raw":
        return None, None
    if args.size in ("160", "160x120"):
        return 160, 120
    if args.size in ("320", "320x240"):
        validate_preview_size(320, 240, args.experimental_preview)
        return 320, 240
    if args.width or args.height:
        width = args.width or args.output_width
        height = args.height or args.output_height
        validate_preview_size(width, height, args.experimental_preview)
        return width, height
    if args.target == "preview":
        validate_preview_size(320, 240, args.experimental_preview)
        return 320, 240
    if args.target == "portapack":
        return 160, 120
    validate_preview_size(args.output_width, args.output_height, args.experimental_preview)
    return args.output_width, args.output_height


def validate_preview_size(width: int, height: int, experimental_preview: bool) -> None:
    if (width, height) == (160, 120):
        return
    if width > 160 or height > 120:
        if not experimental_preview:
            raise ValueError(
                "Output sizes above 160x120 are experimental. "
                "Use --experimental-preview only for PC-side inspection, or use --target raw "
                "to inspect the reconstructed active frame without display scaling."
            )


def tuned_frequency_mhz(channel: str | None, fine_mhz: float) -> tuple[float, float] | None:
    if not channel:
        return None
    nominal = CHANNELS_MHZ.get(channel.upper())
    if nominal is None:
        return None
    return nominal, nominal + fine_mhz


def load_waveform(args: argparse.Namespace) -> tuple[np.ndarray, np.ndarray | None]:
    if args.composite:
        count = -1 if args.max_samples is None else args.max_samples
        waveform = np.fromfile(Path(args.composite), dtype=np.float32, count=count)
        if waveform.size == 0:
            raise ValueError(f"No float32 composite samples found in {args.composite}")
        normalized = remove_dc_and_normalize(waveform)
        return normalized, None

    if args.sample_format == "complex64":
        iq = read_complex64_iq(args.iq, args.max_samples)
    else:
        iq = read_hackrf_u8_iq(args.iq, args.max_samples)

    video = quadrature_demod(iq)
    if args.fm_deviation:
        if args.fm_deviation <= 0:
            raise ValueError("--fm-deviation must be greater than zero")
        video = video * (float(args.sample_rate) / (2.0 * math.pi * float(args.fm_deviation)))
    else:
        video = video * float(args.demod_gain)
    filtered = moving_average_lowpass(video, args.smooth)
    return remove_dc_and_normalize(filtered), filtered if args.smooth > 1 else None


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    standard = STANDARDS[args.standard]
    channel_tuning = tuned_frequency_mhz(args.ch, args.fine)

    waveform, filtered_waveform = load_waveform(args)
    if args.save_composite:
        Path(args.save_composite).parent.mkdir(parents=True, exist_ok=True)
        waveform.astype(np.float32).tofile(args.save_composite)

    sync = detect_sync_pulses(
        waveform,
        sample_rate_hz=args.sample_rate,
        standard=standard,
        polarity=args.sync_polarity,
        sync_threshold=args.sync_threshold,
        line_tolerance=args.line_tolerance,
    )
    requested_size = output_size_for_args(args)
    probe_size = (1, 1) if requested_size == (None, None) else requested_size
    frame = extract_luma_frame(
        waveform,
        sync=sync,
        standard=standard,
        output_size=probe_size,
        invert_luma=args.invert_video or args.invert_luma,
        crop_start=args.crop_start,
        crop_end=args.crop_end,
        frame_lines=args.frame_lines,
        line_tolerance=args.line_tolerance,
        skip_lines=args.skip_lines,
        frame_start_offset=args.frame_start_offset + args.align,
        crop_top=args.crop_top,
        crop_bottom=args.crop_bottom,
        brightness=args.brightness,
        contrast=args.contrast,
    )
    if requested_size == (None, None):
        frame.resized_frame = frame.raw_frame

    save_png(frame.resized_frame, args.out)
    save_debug_artifacts(
        args.debug_dir,
        waveform,
        sync.sync_indices,
        frame.raw_frame,
        frame.resized_frame,
        sample_rate_hz=args.sample_rate,
        save_demod_waveform=args.save_demod_waveform,
        filtered_waveform=filtered_waveform,
        assembled_lines=frame.assembled_lines,
        estimated_line_length=sync.line_length_samples,
        sync_threshold=sync.threshold,
        first_line_index=frame.first_line_index,
    )

    print(f"Saved {args.out}")
    print(f"Standard: {standard.name}")
    print(f"Estimated line length: {sync.line_length_samples} samples")
    print(f"Detected sync pulses: {sync.sync_indices.size}")
    print(f"Frame start index: {sync.frame_start_index}")
    print(f"Sync threshold: {sync.threshold:.6g}")
    print(f"Sync polarity: {'positive' if sync.sync_polarity > 0 else 'negative'}")
    print(f"Lines used: {frame.lines_used}")
    print(f"First stable line index: {frame.first_line_index}")
    print(f"Active window: start +{frame.active_start_samples}, width {frame.active_width_samples}")
    if channel_tuning:
        nominal, tuned = channel_tuning
        print(f"CH: {args.ch.upper()} nominal={nominal:.1f} MHz fine={args.fine:+.1f} MHz tuned={tuned:.1f} MHz")
    elif args.ch:
        print(f"CH: {args.ch} fine={args.fine:+.1f} MHz (unknown nominal)")
    if args.gain:
        print(f"GAIN preset: {args.gain.upper()}")
    print(f"Debug artifacts: {args.debug_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
