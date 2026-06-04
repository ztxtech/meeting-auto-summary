from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
import sys
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
    chunk_duration: float = 10.0,
    chunk_strategy: str = "adaptive",
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
            chunk_strategy=chunk_strategy,
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
    chunk_strategy: str,
    min_chunk_duration: float,
    max_tokens: int,
    prefill_step_size: int,
    progress: Callable[[int, int, float, float], None] | None,
) -> Transcript:
    duration = _audio_duration(audio_path)
    chunks = _chunk_ranges(
        audio_path,
        duration=duration,
        strategy=chunk_strategy,
        max_duration=chunk_duration,
        min_duration=min_chunk_duration,
    )
    total_chunks = len(chunks)
    segments: list[Segment] = []
    texts: list[str] = []

    for index, (start, end) in enumerate(chunks):
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


def _chunk_ranges(
    audio_path: Path,
    *,
    duration: float,
    strategy: str,
    max_duration: float,
    min_duration: float,
) -> list[tuple[float, float]]:
    max_duration = max(max_duration, min_duration)
    if strategy == "fixed":
        return _fixed_chunk_ranges(duration, max_duration)
    if strategy != "adaptive":
        raise ValueError(f"Unsupported chunk strategy: {strategy}")
    return _adaptive_chunk_ranges(audio_path, duration, max_duration, min_duration)


def _fixed_chunk_ranges(duration: float, window: float) -> list[tuple[float, float]]:
    total_chunks = max(1, math.ceil(duration / window))
    return [
        (index * window, min(duration, (index + 1) * window))
        for index in range(total_chunks)
    ]


def _adaptive_chunk_ranges(
    audio_path: Path,
    duration: float,
    max_duration: float,
    min_duration: float,
) -> list[tuple[float, float]]:
    frames = _audio_activity_frames(audio_path)
    if not frames:
        return _fixed_chunk_ranges(duration, max_duration)

    chunks: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        hard_end = min(duration, start + max_duration)
        if hard_end >= duration:
            chunks.append((start, duration))
            break
        cut = _best_adaptive_cut(frames, start, hard_end, min_duration)
        if cut <= start + 0.05:
            cut = hard_end
        chunks.append((start, cut))
        start = cut
    return _merge_tiny_chunks(chunks, min_duration=min_duration, max_duration=max_duration)


def _best_adaptive_cut(
    frames: list[tuple[float, float, float]],
    start: float,
    hard_end: float,
    min_duration: float,
) -> float:
    earliest = start + min_duration
    target = hard_end
    candidates = [
        (time, energy)
        for time, _, energy in frames
        if earliest <= time <= hard_end
    ]
    if not candidates:
        return hard_end

    energies = [energy for _, energy in candidates]
    sorted_energies = sorted(energies)
    silence_floor = sorted_energies[max(0, int(len(sorted_energies) * 0.2) - 1)]
    quiet_candidates = [
        (time, energy)
        for time, energy in candidates
        if energy <= silence_floor * 1.6
    ]
    if quiet_candidates:
        return max(quiet_candidates, key=lambda item: item[0])[0]

    # If there is no clear silence, cut near the weakest recent energy point.
    recent = [(time, energy) for time, energy in candidates if time >= target - 3.0]
    if recent:
        return min(recent, key=lambda item: item[1])[0]
    return min(candidates, key=lambda item: abs(item[0] - target))[0]


def _audio_activity_frames(
    audio_path: Path,
    *,
    frame_seconds: float = 0.2,
) -> list[tuple[float, float, float]]:
    with wave.open(str(audio_path), "rb") as audio:
        sample_width = audio.getsampwidth()
        channels = audio.getnchannels()
        framerate = audio.getframerate()
        if sample_width != 2:
            return []
        frame_count = max(1, int(frame_seconds * framerate))
        frames: list[tuple[float, float, float]] = []
        index = 0
        while True:
            raw = audio.readframes(frame_count)
            if not raw:
                break
            samples = array("h")
            samples.frombytes(raw)
            if sys.byteorder == "big":
                samples.byteswap()
            if channels > 1:
                samples = array("h", samples[::channels])
            if not samples:
                continue
            rms = math.sqrt(sum(float(sample) * float(sample) for sample in samples) / len(samples))
            start = index * frame_seconds
            end = start + (len(samples) / framerate)
            frames.append((start, end, rms))
            index += 1
    return frames


def _merge_tiny_chunks(
    chunks: list[tuple[float, float]],
    *,
    min_duration: float,
    max_duration: float,
) -> list[tuple[float, float]]:
    if not chunks:
        return chunks
    merged: list[tuple[float, float]] = []
    for start, end in chunks:
        if merged and end - start < min_duration:
            prev_start, prev_end = merged[-1]
            if end - prev_start <= max_duration * 1.25:
                merged[-1] = (prev_start, end)
                continue
        merged.append((start, end))
    return merged


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
