from __future__ import annotations

from array import array
import math
import shutil
import subprocess
import tempfile
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from scripts.config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, project_tmp_dir


@dataclass
class PreparedMedia:
    audio_path: Path
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def cleanup(self) -> None:
        if self.temp_dir is not None:
            self.temp_dir.cleanup()


def prepare_media(input_path: Path, output_dir: Path | None = None) -> PreparedMedia:
    suffix = input_path.suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return _convert_audio(input_path, output_dir)
    if suffix in VIDEO_EXTENSIONS:
        return _extract_audio(input_path, output_dir)

    supported = sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS)
    raise ValueError(
        f"Unsupported input file type '{suffix}'. Supported extensions: {', '.join(supported)}"
    )


def _convert_audio(input_path: Path, output_dir: Path | None = None) -> PreparedMedia:
    if input_path.suffix.lower() == ".wav" and output_dir is None:
        return PreparedMedia(audio_path=input_path)
    return _extract_audio(input_path, output_dir)


def _extract_audio(input_path: Path, output_dir: Path | None = None) -> PreparedMedia:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "Video input requires ffmpeg. Install it with: brew install ffmpeg"
        )

    temp_dir = None
    if output_dir is None:
        temp_dir = tempfile.TemporaryDirectory(
            prefix="meeting-summary-", dir=project_tmp_dir()
        )
        audio_path = Path(temp_dir.name) / "audio.wav"
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / "audio.wav"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(audio_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        if temp_dir is not None:
            temp_dir.cleanup()
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(f"ffmpeg failed to extract audio: {detail}") from exc

    try:
        _ensure_audible_audio(audio_path)
    except RuntimeError:
        if temp_dir is not None:
            temp_dir.cleanup()
        raise

    return PreparedMedia(audio_path=audio_path, temp_dir=temp_dir)


def _ensure_audible_audio(audio_path: Path) -> None:
    stats = _audio_signal_stats(audio_path)
    if stats["sample_count"] == 0:
        raise RuntimeError("Extracted audio is empty. Check the media file's audio track.")
    if stats["peak_dbfs"] < -70.0 or (
        stats["rms_dbfs"] < -45.0 and stats["active_ratio"] < 0.01
    ):
        raise RuntimeError(
            "Extracted audio is near silent "
            f"(peak {stats['peak_dbfs']:.1f} dBFS, RMS {stats['rms_dbfs']:.1f} dBFS, "
            f"active samples {stats['active_ratio']:.2%}). "
            "Check the recording input/source audio and try again."
        )


def _audio_signal_stats(audio_path: Path) -> dict[str, float]:
    with wave.open(str(audio_path), "rb") as audio:
        if audio.getsampwidth() != 2:
            return {"sample_count": 1.0, "peak_dbfs": 0.0, "rms_dbfs": 0.0, "active_ratio": 1.0}

        max_abs = 0
        sum_squares = 0.0
        sample_count = 0
        active_count = 0
        while True:
            frames = audio.readframes(16000)
            if not frames:
                break
            samples = array("h")
            samples.frombytes(frames)
            if sys.byteorder == "big":
                samples.byteswap()
            if not samples:
                continue
            max_abs = max(max_abs, max(abs(sample) for sample in samples))
            active_count += sum(1 for sample in samples if abs(sample) >= 512)
            sum_squares += sum(float(sample) * float(sample) for sample in samples)
            sample_count += len(samples)

    full_scale = float(2**15 - 1)
    peak_dbfs = _dbfs(max_abs / full_scale)
    rms_dbfs = (
        _dbfs(math.sqrt(sum_squares / sample_count) / full_scale)
        if sample_count
        else -math.inf
    )
    return {
        "sample_count": float(sample_count),
        "peak_dbfs": peak_dbfs,
        "rms_dbfs": rms_dbfs,
        "active_ratio": active_count / sample_count if sample_count else 0.0,
    }


def _dbfs(value: float) -> float:
    if value <= 0:
        return -math.inf
    return 20 * math.log10(value)
