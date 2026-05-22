from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.transcribe import Segment, Transcript


@dataclass
class SpeakerSegment:
    start: float
    end: float
    speaker: str


def clear_speakers(transcript: Transcript) -> Transcript:
    result = deepcopy(transcript)
    for segment in result.segments:
        segment.speaker = None
    return result


def diarize_transcript(
    transcript: Transcript,
    audio_path: Path,
    diarization_model_path: Path,
    *,
    threshold: float = 0.5,
    min_duration: float = 0.0,
    merge_gap: float = 0.0,
    chunk_duration: float = 30.0,
) -> Transcript:
    speaker_segments = diarize_audio(
        audio_path,
        diarization_model_path,
        threshold=threshold,
        min_duration=min_duration,
        merge_gap=merge_gap,
        chunk_duration=chunk_duration,
    )
    return assign_speakers(transcript, speaker_segments)


def diarize_audio(
    audio_path: Path,
    diarization_model_path: Path,
    *,
    threshold: float = 0.5,
    min_duration: float = 0.0,
    merge_gap: float = 0.0,
    chunk_duration: float = 30.0,
) -> list[SpeakerSegment]:
    try:
        from mlx_audio.vad import load
    except ImportError as exc:
        raise RuntimeError("mlx-audio VAD support is not installed.") from exc

    model = load(diarization_model_path, lazy=True)
    results = model.generate_stream(
        str(audio_path),
        chunk_duration=chunk_duration,
        threshold=threshold,
        min_duration=min_duration,
        merge_gap=merge_gap,
        verbose=False,
    )

    segments = [
        _normalize_diarization_segment(segment)
        for result in results
        for segment in result.segments
    ]
    return _merge_adjacent_segments(
        [segment for segment in segments if segment.end > segment.start],
        merge_gap=merge_gap,
    )


def assign_speakers(
    transcript: Transcript,
    speaker_segments: list[SpeakerSegment],
) -> Transcript:
    result = deepcopy(transcript)
    if not speaker_segments:
        return result

    for segment in result.segments:
        if segment.start is None or segment.end is None:
            continue
        speaker = _speaker_with_max_overlap(segment, speaker_segments)
        if speaker:
            segment.speaker = speaker

    return result


def _speaker_with_max_overlap(
    segment: Segment,
    speaker_segments: list[SpeakerSegment],
) -> str | None:
    overlaps: dict[str, float] = {}
    for speaker_segment in speaker_segments:
        overlap = _overlap_seconds(
            segment.start,
            segment.end,
            speaker_segment.start,
            speaker_segment.end,
        )
        if overlap > 0:
            overlaps[speaker_segment.speaker] = (
                overlaps.get(speaker_segment.speaker, 0.0) + overlap
            )

    if not overlaps:
        midpoint = (segment.start + segment.end) / 2
        nearest = min(
            speaker_segments,
            key=lambda speaker_segment: min(
                abs(midpoint - speaker_segment.start),
                abs(midpoint - speaker_segment.end),
            ),
        )
        return nearest.speaker

    return max(overlaps, key=overlaps.get)


def _overlap_seconds(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def _normalize_diarization_segment(segment: Any) -> SpeakerSegment:
    speaker = _get_value(segment, "speaker")
    return SpeakerSegment(
        start=float(_get_value(segment, "start")),
        end=float(_get_value(segment, "end")),
        speaker=f"Speaker {int(speaker) + 1}",
    )


def _merge_adjacent_segments(
    segments: list[SpeakerSegment],
    *,
    merge_gap: float,
) -> list[SpeakerSegment]:
    if not segments:
        return []

    sorted_segments = sorted(
        segments, key=lambda segment: (segment.speaker, segment.start)
    )
    merged = [sorted_segments[0]]
    for segment in sorted_segments[1:]:
        previous = merged[-1]
        if (
            segment.speaker == previous.speaker
            and segment.start - previous.end <= merge_gap
        ):
            merged[-1] = SpeakerSegment(
                start=previous.start,
                end=max(previous.end, segment.end),
                speaker=previous.speaker,
            )
        else:
            merged.append(segment)

    return sorted(merged, key=lambda segment: segment.start)


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key)
