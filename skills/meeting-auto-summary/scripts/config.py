from __future__ import annotations

from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def project_tmp_dir() -> Path:
    path = project_root() / "tmp"
    path.mkdir(exist_ok=True)
    return path


def resolve_model_path(model_path: str | Path) -> Path:
    candidate = Path(model_path).expanduser()
    if candidate.exists() and candidate.is_dir():
        return candidate.resolve()

    raise FileNotFoundError(f"Model directory does not exist: {candidate}")
