from __future__ import annotations

from dataclasses import dataclass
import tempfile
from pathlib import Path
from typing import Any

from scripts.config import project_tmp_dir


@dataclass
class Segment:
    text: str
    start: float | None = None
    end: float | None = None
    speaker: str | None = None


@dataclass
class Transcript:
    text: str
    segments: list[Segment]


def transcribe_audio(
    audio_path: Path,
    model_path: Path,
    language: str = "auto",
    *,
    chunk_duration: float = 30.0,
    min_chunk_duration: float = 1.0,
    max_tokens: int = 8192,
    prefill_step_size: int = 2048,
) -> Transcript:
    try:
        from mlx_audio.stt.generate import generate_transcription
        from mlx_audio.stt.utils import load_model
    except ImportError as exc:
        raise RuntimeError(
            "mlx-audio is not installed. Run: python -m pip install -e ."
        ) from exc

    model = load_model(str(model_path), lazy=True)
    with tempfile.TemporaryDirectory(
        prefix="meeting-summary-asr-", dir=project_tmp_dir()
    ) as temp_dir:
        kwargs: dict[str, Any] = {
            "model": model,
            "audio": str(audio_path),
            "output_path": str(Path(temp_dir) / "transcript"),
            "format": "txt",
            "verbose": False,
            "chunk_duration": chunk_duration,
            "min_chunk_duration": min_chunk_duration,
            "max_tokens": max_tokens,
            "prefill_step_size": prefill_step_size,
        }
        if language != "auto":
            kwargs["language"] = language

        result = generate_transcription(**kwargs)
    return normalize_transcription(result)


def normalize_transcription(result: Any) -> Transcript:
    text = _get_value(result, "text")
    if text is None and isinstance(result, str):
        text = result
    if text is None:
        text = ""

    raw_segments = _get_value(result, "segments") or []
    segments = [_normalize_segment(segment) for segment in raw_segments]
    segments = [segment for segment in segments if segment.text.strip()]

    if not segments and str(text).strip():
        segments = [Segment(text=str(text).strip())]

    return Transcript(text=str(text).strip(), segments=segments)


def _normalize_segment(segment: Any) -> Segment:
    return Segment(
        text=str(_get_value(segment, "text") or "").strip(),
        start=_as_float(_get_value(segment, "start")),
        end=_as_float(_get_value(segment, "end")),
        speaker=_normalize_speaker(
            _get_value(segment, "speaker")
            or _get_value(segment, "speaker_label")
            or _get_value(segment, "speaker_id")
        ),
    )


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_speaker(value: Any) -> str | None:
    if value is None:
        return None
    speaker = str(value).strip()
    return speaker or None
