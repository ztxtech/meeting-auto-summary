from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.config import resolve_model_path
from scripts.media import prepare_media
from scripts.output import render_transcript
from scripts.speakers import clear_speakers, diarize_transcript
from scripts.transcribe import transcribe_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe meeting audio/video with local Qwen3-ASR."
    )
    parser.add_argument("input", nargs="?", type=Path, help="Input audio or video file")
    parser.add_argument("--output", "-o", type=Path, help="Output file path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for audio.wav, transcript.md, subtitles.srt, and subtitles.txt",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["md", "txt", "srt"],
        default="md",
        help="Output format",
    )
    parser.add_argument(
        "--model",
        required=True,
        type=Path,
        help="Path to local Qwen3-ASR model directory",
    )
    parser.add_argument(
        "--language",
        default="auto",
        help="Recognition language, for example auto, zh, or en",
    )
    parser.add_argument(
        "--chunk-duration",
        type=float,
        default=30.0,
        help="Maximum audio chunk duration in seconds",
    )
    parser.add_argument(
        "--min-chunk-duration",
        type=float,
        default=1.0,
        help="Minimum audio chunk duration in seconds",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=8192, help="Maximum tokens to generate"
    )
    parser.add_argument(
        "--prefill-step-size",
        type=int,
        default=2048,
        help="Prefill step size for MLX generation",
    )
    parser.add_argument(
        "--speaker-mode",
        choices=["none", "diarize"],
        default="none",
        help="Speaker labeling mode",
    )
    parser.add_argument(
        "--diarization-model",
        type=Path,
        help="Path to local speaker diarization model directory",
    )
    parser.add_argument(
        "--diarization-threshold",
        type=float,
        default=0.5,
        help="Speaker activity threshold",
    )
    parser.add_argument(
        "--diarization-min-duration",
        type=float,
        default=0.0,
        help="Minimum speaker segment duration",
    )
    parser.add_argument(
        "--diarization-merge-gap",
        type=float,
        default=0.0,
        help="Maximum gap to merge speaker segments",
    )
    parser.add_argument(
        "--diarization-chunk-duration",
        type=float,
        default=30.0,
        help="Diarization chunk duration in seconds",
    )
    parser.add_argument(
        "--speaker-global-clustering",
        dest="speaker_global_clustering",
        action="store_true",
        default=True,
        help="Globally recluster diarization speaker labels across the full audio",
    )
    parser.add_argument(
        "--no-speaker-global-clustering",
        dest="speaker_global_clustering",
        action="store_false",
        help="Disable global speaker relabeling after diarization",
    )
    parser.add_argument(
        "--speaker-clustering-threshold",
        type=float,
        default=0.9,
        help="Cosine threshold for global speaker clustering",
    )
    parser.add_argument(
        "--speaker-count",
        type=int,
        help="Expected global speaker count for constrained clustering",
    )
    parser.add_argument("--title", help="Markdown title")
    parser.add_argument(
        "--keep-temp", action="store_true", help="Keep temporary extracted audio files"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        return run(args)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def run(args: argparse.Namespace) -> int:
    input_path = args.input.expanduser().resolve()
    if not input_path.exists() or not input_path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    _progress("Loading ASR model")
    model_path = resolve_model_path(args.model)
    diarization_model_path = _resolve_diarization_model_path(args)
    output_path = _resolve_output_path(input_path, args.output, args.format, args.output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _progress("Preparing audio")
    prepared = prepare_media(input_path, output_path.parent if args.output_dir else None)
    try:
        _progress("Running ASR")
        transcript = transcribe_audio(
            prepared.audio_path,
            model_path,
            args.language,
            chunk_duration=args.chunk_duration,
            min_chunk_duration=args.min_chunk_duration,
            max_tokens=args.max_tokens,
            prefill_step_size=args.prefill_step_size,
            progress=_asr_progress,
        )
        if args.speaker_mode == "diarize":
            _progress("Running speaker diarization")
            transcript = diarize_transcript(
                transcript,
                prepared.audio_path,
                diarization_model_path,
                threshold=args.diarization_threshold,
                min_duration=args.diarization_min_duration,
                merge_gap=args.diarization_merge_gap,
                chunk_duration=args.diarization_chunk_duration,
                global_clustering=args.speaker_global_clustering,
                clustering_threshold=args.speaker_clustering_threshold,
                speaker_count=args.speaker_count,
            )
        else:
            transcript = clear_speakers(transcript)
        _progress("Writing output files")
        if args.output_dir:
            _write_output_dir(transcript, output_path.parent, args.title or input_path.stem)
        else:
            output = render_transcript(transcript, args.format, args.title)
            output_path.write_text(output, encoding="utf-8")
    finally:
        if not args.keep_temp:
            prepared.cleanup()

    if args.output_dir:
        print(f"Wrote {output_path.parent}")
    else:
        print(f"Wrote {output_path}")
    return 0


def _progress(message: str) -> None:
    print(f"PROGRESS: {message}", flush=True)


def _asr_progress(index: int, total: int, start: float, end: float) -> None:
    _progress(
        f"Running ASR chunk {index}/{total} "
        f"({format_duration(start)}-{format_duration(end)})"
    )


def format_duration(seconds: float) -> str:
    rounded = max(0, int(seconds))
    minutes, secs = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def _resolve_output_path(
    input_path: Path,
    output_path: Path | None,
    output_format: str,
    output_dir: Path | None = None,
) -> Path:
    if output_dir is not None:
        return output_dir.expanduser().resolve() / "transcript.md"
    if output_path is not None:
        return output_path.expanduser().resolve()
    return input_path.with_suffix(f".{output_format}").resolve()


def _resolve_diarization_model_path(args: argparse.Namespace) -> Path | None:
    if args.speaker_mode != "diarize":
        return None
    if args.diarization_model is None:
        raise ValueError("--diarization-model is required when --speaker-mode diarize")
    return resolve_model_path(args.diarization_model)


def _write_output_dir(transcript, output_dir: Path, title: str) -> None:
    outputs = {
        "transcript.md": render_transcript(transcript, "md", title),
        "subtitles.srt": render_transcript(transcript, "srt"),
        "subtitles.txt": render_transcript(transcript, "txt"),
    }
    for filename, content in outputs.items():
        (output_dir / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
