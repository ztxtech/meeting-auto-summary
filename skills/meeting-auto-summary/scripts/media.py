from __future__ import annotations

import shutil
import subprocess
import tempfile
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
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "audio.wav"
            if input_path.resolve() != audio_path.resolve():
                shutil.copy2(input_path, audio_path)
            return PreparedMedia(audio_path=audio_path)
        return PreparedMedia(audio_path=input_path)
    if suffix in VIDEO_EXTENSIONS:
        return _extract_audio(input_path, output_dir)

    supported = sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS)
    raise ValueError(
        f"Unsupported input file type '{suffix}'. Supported extensions: {', '.join(supported)}"
    )


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

    return PreparedMedia(audio_path=audio_path, temp_dir=temp_dir)
