from __future__ import annotations

from dataclasses import dataclass
import math
import tempfile
import wave
from pathlib import Path
from typing import Any, Callable

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
    progress: Callable[[int, int, float, float], None] | None = None,
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
        transcript = _transcribe_in_chunks(
            generate_transcription,
            model,
            audio_path,
            Path(temp_dir),
            language=language,
            chunk_duration=chunk_duration,
            min_chunk_duration=min_chunk_duration,
            max_tokens=max_tokens,
            prefill_step_size=prefill_step_size,
            progress=progress,
        )
    return transcript


def _transcribe_in_chunks(
    generate_transcription: Callable[..., Any],
    model: Any,
    audio_path: Path,
    temp_dir: Path,
    *,
    language: str,
    chunk_duration: float,
    min_chunk_duration: float,
    max_tokens: int,
    prefill_step_size: int,
    progress: Callable[[int, int, float, float], None] | None,
) -> Transcript:
    duration = _audio_duration(audio_path)
    window = max(chunk_duration, min_chunk_duration)
    total_chunks = max(1, math.ceil(duration / window))
    segments: list[Segment] = []
    texts: list[str] = []

    for index in range(total_chunks):
        start = index * window
        end = min(duration, start + window)
        if end - start < min_chunk_duration and segments:
            break
        chunk_path = audio_path
        if total_chunks > 1:
            chunk_path = temp_dir / f"chunk-{index + 1:04}.wav"
            _write_wav_chunk(audio_path, chunk_path, start, end - start)
        if progress:
            progress(index + 1, total_chunks, start, end)
        result = _generate_chunk(
            generate_transcription,
            model,
            chunk_path,
            temp_dir / f"transcript-{index + 1:04}",
            language=language,
            chunk_duration=chunk_duration,
            min_chunk_duration=min_chunk_duration,
            max_tokens=max_tokens,
            prefill_step_size=prefill_step_size,
        )
        transcript = normalize_transcription(result)
        texts.append(transcript.text)
        for segment in transcript.segments:
            segments.append(
                Segment(
                    text=segment.text,
                    start=segment.start + start if segment.start is not None else None,
                    end=segment.end + start if segment.end is not None else None,
                    speaker=segment.speaker,
                )
            )

    return Transcript(text="\n".join(text for text in texts if text).strip(), segments=segments)


def _generate_chunk(
    generate_transcription: Callable[..., Any],
    model: Any,
    audio_path: Path,
    output_path: Path,
    *,
    language: str,
    chunk_duration: float,
    min_chunk_duration: float,
    max_tokens: int,
    prefill_step_size: int,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": model,
        "audio": str(audio_path),
        "output_path": str(output_path),
        "format": "txt",
        "verbose": False,
        "chunk_duration": chunk_duration,
        "min_chunk_duration": min_chunk_duration,
        "max_tokens": max_tokens,
        "prefill_step_size": prefill_step_size,
    }
    if language != "auto":
        kwargs["language"] = language
    return generate_transcription(**kwargs)


def _audio_duration(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as audio:
        return audio.getnframes() / float(audio.getframerate())


def _write_wav_chunk(
    input_path: Path,
    output_path: Path,
    start: float,
    duration: float,
) -> None:
    with wave.open(str(input_path), "rb") as source:
        framerate = source.getframerate()
        source.setpos(min(source.getnframes(), max(0, int(start * framerate))))
        frames = source.readframes(max(0, int(duration * framerate)))
        with wave.open(str(output_path), "wb") as target:
            target.setparams(source.getparams())
            target.writeframes(frames)


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
