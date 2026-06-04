from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import tempfile
import wave

import numpy as np

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
    min_duration: float = 0.5,
    merge_gap: float = 0.2,
    chunk_duration: float = 30.0,
    global_clustering: bool = True,
    embedding_backend: str = "sortformer",
    embedding_model_path: Path | None = None,
    clustering_threshold: float = 0.82,
    speaker_count: int | None = None,
) -> Transcript:
    speaker_segments = diarize_audio(
        audio_path,
        diarization_model_path,
        threshold=threshold,
        min_duration=min_duration,
        merge_gap=merge_gap,
        chunk_duration=chunk_duration,
        global_clustering=global_clustering,
        embedding_backend=embedding_backend,
        embedding_model_path=embedding_model_path,
        clustering_threshold=clustering_threshold,
        speaker_count=speaker_count,
    )
    return assign_speakers(transcript, speaker_segments)


def diarize_audio(
    audio_path: Path,
    diarization_model_path: Path,
    *,
    threshold: float = 0.5,
    min_duration: float = 0.5,
    merge_gap: float = 0.2,
    chunk_duration: float = 30.0,
    global_clustering: bool = True,
    embedding_backend: str = "sortformer",
    embedding_model_path: Path | None = None,
    clustering_threshold: float = 0.82,
    speaker_count: int | None = None,
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
    merged_segments = _merge_adjacent_segments(
        [segment for segment in segments if segment.end > segment.start],
        merge_gap=merge_gap,
    )
    if not global_clustering or len(merged_segments) < 2:
        return merged_segments

    if speaker_count == 1:
        return _force_single_speaker(merged_segments, merge_gap=merge_gap)

    raw_speaker_count = _estimated_speaker_count(merged_segments)
    if speaker_count is None:
        sortformer_reference = globally_cluster_speakers(
            model,
            audio_path,
            merged_segments,
            embedding_backend="sortformer",
            embedding_model_path=None,
            threshold=clustering_threshold,
            speaker_count=None,
            merge_gap=merge_gap,
        )
        reference_speaker_count = _estimated_speaker_count(sortformer_reference)
        if raw_speaker_count == 1 and reference_speaker_count == 1:
            return _force_single_speaker(sortformer_reference, merge_gap=merge_gap)
        effective_speaker_count = max(
            count
            for count in (raw_speaker_count, reference_speaker_count)
            if count is not None
        )
        if embedding_backend == "sortformer":
            return sortformer_reference
    else:
        effective_speaker_count = speaker_count

    return globally_cluster_speakers(
        model,
        audio_path,
        merged_segments,
        embedding_backend=embedding_backend,
        embedding_model_path=embedding_model_path,
        threshold=clustering_threshold,
        speaker_count=effective_speaker_count,
        merge_gap=merge_gap,
    )


def _force_single_speaker(
    segments: list[SpeakerSegment],
    *,
    merge_gap: float,
) -> list[SpeakerSegment]:
    return _merge_adjacent_segments(
        [
            SpeakerSegment(
                start=segment.start,
                end=segment.end,
                speaker="Speaker 1",
            )
            for segment in segments
        ],
        merge_gap=merge_gap,
    )


def globally_cluster_speakers(
    model: Any,
    audio_path: Path,
    speaker_segments: list[SpeakerSegment],
    *,
    embedding_backend: str = "sortformer",
    embedding_model_path: Path | None = None,
    threshold: float = 0.82,
    speaker_count: int | None = None,
    merge_gap: float = 0.0,
) -> list[SpeakerSegment]:
    embeddings = _extract_segment_embeddings(
        model,
        audio_path,
        speaker_segments,
        backend=embedding_backend,
        model_path=embedding_model_path,
    )
    if not embeddings:
        return speaker_segments

    clusters = _cluster_embeddings(
        embeddings,
        speaker_segments,
        threshold=threshold,
        target_count=speaker_count,
    )
    speaker_names = _speaker_names_by_first_appearance(clusters, speaker_segments)
    relabeled = [
        SpeakerSegment(
            start=segment.start,
            end=segment.end,
            speaker=speaker_names[cluster_id],
        )
        for segment, cluster_id in zip(speaker_segments, clusters)
    ]
    return _merge_adjacent_segments(relabeled, merge_gap=merge_gap)


def _extract_segment_embeddings(
    sortformer_model: Any,
    audio_path: Path,
    speaker_segments: list[SpeakerSegment],
    *,
    backend: str,
    model_path: Path | None,
) -> list[np.ndarray]:
    if backend == "sortformer":
        return _extract_sortformer_segment_embeddings(
            sortformer_model, audio_path, speaker_segments
        )
    if backend == "campplus":
        if model_path is None:
            raise RuntimeError(
                "CAMPPlus speaker embedding model path is required when "
                "--speaker-embedding-backend campplus is used."
            )
        return _extract_campplus_segment_embeddings(
            audio_path, speaker_segments, model_path
        )
    raise RuntimeError(f"Unsupported speaker embedding backend: {backend}")


def assign_speakers(
    transcript: Transcript,
    speaker_segments: list[SpeakerSegment],
) -> Transcript:
    result = deepcopy(transcript)
    if not speaker_segments:
        return result

    split_segments: list[Segment] = []
    for segment in result.segments:
        if segment.start is None or segment.end is None:
            split_segments.append(segment)
            continue
        parts = _split_transcript_segment_by_speaker(segment, speaker_segments)
        if parts:
            split_segments.extend(parts)
            continue
        speaker = _speaker_with_max_overlap(segment, speaker_segments)
        if speaker:
            segment.speaker = speaker
        split_segments.append(segment)

    result.segments = split_segments
    return result


def _split_transcript_segment_by_speaker(
    segment: Segment,
    speaker_segments: list[SpeakerSegment],
) -> list[Segment]:
    if segment.start is None or segment.end is None or segment.end <= segment.start:
        return []

    overlaps: list[tuple[float, float, str]] = []
    for speaker_segment in speaker_segments:
        start = max(segment.start, speaker_segment.start)
        end = min(segment.end, speaker_segment.end)
        if end > start:
            overlaps.append((start, end, speaker_segment.speaker))
    if not overlaps:
        return []

    intervals = _merge_same_speaker_intervals(overlaps)
    speakers = {speaker for _, _, speaker in intervals}
    if len(speakers) <= 1:
        return []

    text_parts = _split_text_for_intervals(segment.text, intervals)
    if len(text_parts) != len(intervals):
        return []

    return [
        Segment(text=text, start=start, end=end, speaker=speaker)
        for (start, end, speaker), text in zip(intervals, text_parts)
        if text.strip()
    ]


def _merge_same_speaker_intervals(
    intervals: list[tuple[float, float, str]],
    *,
    gap: float = 0.25,
) -> list[tuple[float, float, str]]:
    merged: list[tuple[float, float, str]] = []
    for start, end, speaker in sorted(intervals, key=lambda item: item[0]):
        if not merged:
            merged.append((start, end, speaker))
            continue
        prev_start, prev_end, prev_speaker = merged[-1]
        if speaker == prev_speaker and start - prev_end <= gap:
            merged[-1] = (prev_start, max(prev_end, end), speaker)
        else:
            merged.append((start, end, speaker))
    return merged


def _split_text_for_intervals(
    text: str,
    intervals: list[tuple[float, float, str]],
) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    units = _text_split_units(stripped)
    if len(units) < len(intervals):
        return []

    durations = [max(0.0, end - start) for start, end, _ in intervals]
    total = sum(durations)
    if total <= 0:
        return []

    counts: list[int] = []
    remaining_units = len(units)
    remaining_duration = total
    for index, duration in enumerate(durations):
        intervals_left = len(durations) - index
        if intervals_left == 1:
            count = remaining_units
        else:
            proportional = round(remaining_units * duration / remaining_duration)
            count = min(
                remaining_units - (intervals_left - 1),
                max(1, proportional),
            )
        counts.append(count)
        remaining_units -= count
        remaining_duration -= duration

    parts: list[str] = []
    offset = 0
    for count in counts:
        parts.append(_join_text_units(units[offset : offset + count]))
        offset += count
    return parts


def _text_split_units(text: str) -> list[str]:
    non_space = re.findall(r"\S", text)
    if not non_space:
        return []
    cjk_count = sum(1 for char in non_space if _is_cjk(char))
    if cjk_count / len(non_space) >= 0.2:
        return non_space
    return re.findall(r"\S+", text)


def _join_text_units(units: list[str]) -> str:
    if not units:
        return ""
    if any(len(unit) == 1 and _is_cjk(unit) for unit in units):
        return "".join(units).strip()
    return " ".join(units).strip()


def _is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


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


def _extract_sortformer_segment_embeddings(
    model: Any,
    audio_path: Path,
    speaker_segments: list[SpeakerSegment],
) -> list[np.ndarray]:
    try:
        import mlx.core as mx
        from mlx_audio.vad.models.sortformer.sortformer import extract_mel_features
    except ImportError as exc:
        raise RuntimeError("mlx-audio Sortformer support is not installed.") from exc

    waveform, sample_rate = model._load_audio(str(audio_path), 16000)
    proc = model._processor_config
    if sample_rate != proc.sampling_rate:
        waveform = model._resample(waveform, sample_rate, proc.sampling_rate)

    use_v2_features = model.config.modules_config.use_aosc
    trim_offset_sec = 0.0
    if not use_v2_features:
        waveform, trim_offset = model._trim_silence(waveform, proc.sampling_rate)
        trim_offset_sec = trim_offset / proc.sampling_rate
        waveform = (1.0 / (mx.max(mx.abs(waveform)) + 1e-3)) * waveform
    features = extract_mel_features(
        waveform,
        sample_rate=proc.sampling_rate,
        n_fft=proc.n_fft,
        hop_length=proc.hop_length,
        win_length=proc.win_length,
        n_mels=proc.feature_size,
        preemphasis_coeff=proc.preemphasis,
        normalize=None if use_v2_features else "per_feature",
        pad_to=0 if use_v2_features else 16,
    )

    embeddings = _pre_encode_features_in_chunks(model, features)
    frame_duration = _sortformer_frame_duration(model)
    return [
        _segment_embedding(embeddings, segment, frame_duration, trim_offset_sec)
        for segment in speaker_segments
    ]


def _extract_campplus_segment_embeddings(
    audio_path: Path,
    speaker_segments: list[SpeakerSegment],
    model_path: Path,
) -> list[np.ndarray]:
    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise RuntimeError(
            "CAMPPlus speaker embedding requires funasr and torch. Install them in "
            "the skill venv, for example: python -m pip install -U funasr torch torchaudio"
        ) from exc

    if not model_path.exists():
        raise RuntimeError(
            f"CAMPPlus speaker embedding model does not exist: {model_path}. "
            "Download a 3D-Speaker/CAMPPlus model into this directory first."
        )

    model = AutoModel(model=str(model_path), disable_update=True)
    embeddings: list[np.ndarray] = []
    with tempfile.TemporaryDirectory(prefix="meeting-summary-campplus-") as temp_dir:
        temp_path = Path(temp_dir)
        for index, segment in enumerate(speaker_segments):
            clip_path = temp_path / f"speaker-{index:04}.wav"
            _write_wav_clip(audio_path, clip_path, segment.start, segment.end)
            result = model.generate(input=str(clip_path), disable_pbar=True)
            embeddings.append(_normalize_embedding(_campplus_embedding_from_result(result)))
    return embeddings


def _campplus_embedding_from_result(result: Any) -> np.ndarray:
    candidates: list[Any]
    if isinstance(result, list):
        candidates = result
    else:
        candidates = [result]
    for item in candidates:
        embedding = _find_embedding_value(item)
        if embedding is not None:
            array = np.asarray(embedding, dtype=np.float32).reshape(-1)
            if array.size:
                return array
    raise RuntimeError("CAMPPlus did not return a speaker embedding.")


def _find_embedding_value(value: Any) -> Any | None:
    if isinstance(value, dict):
        for key in ("spk_embedding", "speaker_embedding", "embedding", "emb"):
            if key in value:
                return value[key]
        for child in value.values():
            found = _find_embedding_value(child)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _find_embedding_value(child)
            if found is not None:
                return found
    return None


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.astype(np.float32)


def _write_wav_clip(
    input_path: Path,
    output_path: Path,
    start: float,
    end: float,
) -> None:
    with wave.open(str(input_path), "rb") as source:
        framerate = source.getframerate()
        start_frame = min(source.getnframes(), max(0, int(start * framerate)))
        end_frame = min(source.getnframes(), max(start_frame + 1, int(end * framerate)))
        source.setpos(start_frame)
        frames = source.readframes(end_frame - start_frame)
        with wave.open(str(output_path), "wb") as target:
            target.setparams(source.getparams())
            target.writeframes(frames)


def _pre_encode_features_in_chunks(model: Any, features: Any) -> np.ndarray:
    import mlx.core as mx

    proc = model._processor_config
    subsampling_factor = model.config.fc_encoder_config.subsampling_factor
    chunk_mel = (
        round(60.0 * proc.sampling_rate / proc.hop_length / subsampling_factor)
        * subsampling_factor
    )
    chunk_mel = max(chunk_mel, subsampling_factor)

    encoded_chunks = []
    for offset in range(0, features.shape[2], chunk_mel):
        chunk = features[:, :, offset : offset + chunk_mel]
        chunk_lengths = mx.array([chunk.shape[2]])
        pre_embs, pre_emb_lengths = model.fc_encoder.pre_encode(chunk, chunk_lengths)
        emb_len = int(pre_emb_lengths[0].item())
        pre_embs = pre_embs[:, :emb_len, :]
        mx.eval(pre_embs)
        encoded_chunks.append(np.asarray(pre_embs[0].tolist(), dtype=np.float32))

    if not encoded_chunks:
        return np.empty((0, model.config.fc_encoder_config.hidden_size), dtype=np.float32)
    return np.concatenate(encoded_chunks, axis=0)


def _sortformer_frame_duration(model: Any) -> float:
    proc = model._processor_config
    subsampling_factor = model.config.fc_encoder_config.subsampling_factor
    return (proc.hop_length * subsampling_factor) / proc.sampling_rate


def _segment_embedding(
    frame_embeddings: np.ndarray,
    segment: SpeakerSegment,
    frame_duration: float,
    trim_offset_sec: float,
) -> np.ndarray:
    local_start = max(0.0, segment.start - trim_offset_sec)
    local_end = max(local_start + frame_duration, segment.end - trim_offset_sec)
    start_frame = max(0, int(math.floor(local_start / frame_duration)))
    end_frame = min(
        len(frame_embeddings),
        max(start_frame + 1, int(math.ceil(local_end / frame_duration))),
    )
    if start_frame >= len(frame_embeddings):
        start_frame = max(0, len(frame_embeddings) - 1)
        end_frame = len(frame_embeddings)

    if len(frame_embeddings) == 0:
        return np.empty((0,), dtype=np.float32)

    embedding = frame_embeddings[start_frame:end_frame].mean(axis=0)
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.astype(np.float32)


def _cluster_embeddings(
    embeddings: list[np.ndarray],
    speaker_segments: list[SpeakerSegment],
    *,
    threshold: float,
    target_count: int | None,
) -> list[int]:
    incompatible = _incompatible_segment_pairs(
        speaker_segments,
        local_window=5.0 if target_count is not None else 180.0,
    )
    if target_count is not None and target_count > 0:
        clusters = [[index] for index in range(len(embeddings))]
        clusters = _merge_to_target_count(
            clusters, embeddings, incompatible, target_count
        )
    else:
        clusters = _streaming_cluster_embeddings(
            embeddings,
            incompatible,
            threshold=threshold,
        )
        clusters = _merge_nearby_clusters(
            clusters,
            embeddings,
            incompatible,
            threshold,
            target_count=None,
        )
    return _labels_from_clusters(clusters)


def _streaming_cluster_embeddings(
    embeddings: list[np.ndarray],
    incompatible: set[tuple[int, int]],
    *,
    threshold: float,
) -> list[list[int]]:
    clusters: list[list[int]] = []
    centroids: list[np.ndarray] = []

    for index, embedding in enumerate(embeddings):
        best_cluster = None
        best_score = -1.0
        for cluster_id, centroid in enumerate(centroids):
            if _cluster_has_incompatible_segment(index, clusters[cluster_id], incompatible):
                continue
            score = _cosine_similarity(embedding, centroid)
            if score > best_score:
                best_cluster = cluster_id
                best_score = score

        if best_cluster is None or best_score < threshold:
            clusters.append([index])
            centroids.append(embedding)
        else:
            clusters[best_cluster].append(index)
            centroids[best_cluster] = _normalized_mean(
                [embeddings[item] for item in clusters[best_cluster]]
            )
    return clusters


def _merge_to_target_count(
    clusters: list[list[int]],
    embeddings: list[np.ndarray],
    incompatible: set[tuple[int, int]],
    target_count: int,
) -> list[list[int]]:
    return _merge_nearby_clusters(
        clusters,
        embeddings,
        incompatible,
        threshold=-1.0,
        target_count=target_count,
    )


def _merge_nearby_clusters(
    clusters: list[list[int]],
    embeddings: list[np.ndarray],
    incompatible: set[tuple[int, int]],
    threshold: float,
    target_count: int | None,
) -> list[list[int]]:
    changed = True
    while changed:
        changed = False
        if target_count is not None and len(clusters) <= target_count:
            break
        centroids = [
            _normalized_mean([embeddings[index] for index in cluster])
            for cluster in clusters
        ]
        best_pair = None
        best_score = -1.0
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                if _clusters_are_incompatible(clusters[left], clusters[right], incompatible):
                    continue
                score = _cosine_similarity(centroids[left], centroids[right])
                if score > best_score:
                    best_pair = (left, right)
                    best_score = score
        if best_pair is None:
            break
        if target_count is None and best_score < threshold:
            break
        left, right = best_pair
        clusters[left].extend(clusters[right])
        del clusters[right]
        changed = True
    return clusters


def _incompatible_segment_pairs(
    speaker_segments: list[SpeakerSegment],
    *,
    local_window: float = 180.0,
) -> set[tuple[int, int]]:
    # Only truly overlapping speech is impossible to merge into one speaker.
    # Nearby non-overlapping turns may be the same person after a Sortformer
    # streaming window reset, so blocking them prevents global relabeling from
    # fixing Speaker 14 / Speaker 52 style label drift.
    incompatible: set[tuple[int, int]] = set()
    for left_index, left in enumerate(speaker_segments):
        for right_index in range(left_index + 1, len(speaker_segments)):
            right = speaker_segments[right_index]
            if right.start - left.end > local_window:
                break
            if left.speaker == right.speaker:
                continue
            if _overlap_seconds(left.start, left.end, right.start, right.end) > 0:
                incompatible.add((left_index, right_index))
    return incompatible


def _cluster_has_incompatible_segment(
    index: int,
    cluster: list[int],
    incompatible: set[tuple[int, int]],
) -> bool:
    return any(_pair_key(index, member) in incompatible for member in cluster)


def _clusters_are_incompatible(
    left: list[int],
    right: list[int],
    incompatible: set[tuple[int, int]],
) -> bool:
    return any(
        _pair_key(left_item, right_item) in incompatible
        for left_item in left
        for right_item in right
    )


def _pair_key(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def _distorted_significant_speakers(
    original: list[SpeakerSegment],
    relabeled: list[SpeakerSegment],
    *,
    min_duration: float = 20.0,
) -> bool:
    original_count = _significant_speaker_count(original, min_duration=min_duration)
    relabeled_count = _significant_speaker_count(relabeled, min_duration=min_duration)
    if original_count <= 1:
        return False
    lower_bound = max(2, math.ceil(original_count / 2))
    upper_bound = original_count
    return relabeled_count < lower_bound or relabeled_count > upper_bound


def _significant_speaker_count(
    segments: list[SpeakerSegment],
    *,
    min_duration: float,
) -> int:
    durations: dict[str, float] = {}
    for segment in segments:
        durations[segment.speaker] = durations.get(segment.speaker, 0.0) + max(
            0.0, segment.end - segment.start
        )
    return sum(duration >= min_duration for duration in durations.values())


def _estimated_speaker_count(
    segments: list[SpeakerSegment],
    *,
    min_duration: float = 20.0,
    min_share: float = 0.05,
) -> int | None:
    durations: dict[str, float] = {}
    total = 0.0
    for segment in segments:
        duration = max(0.0, segment.end - segment.start)
        durations[segment.speaker] = durations.get(segment.speaker, 0.0) + duration
        total += duration
    if total <= 0:
        return None

    count = sum(
        1
        for duration in durations.values()
        if duration >= min_duration and duration / total >= min_share
    )
    return max(1, count) if durations else None


def _labels_from_clusters(clusters: list[list[int]]) -> list[int]:
    labels = [0] * sum(len(cluster) for cluster in clusters)
    for cluster_id, cluster in enumerate(clusters):
        for index in cluster:
            labels[index] = cluster_id
    return labels


def _normalized_mean(embeddings: list[np.ndarray]) -> np.ndarray:
    mean = np.mean(np.stack(embeddings), axis=0)
    norm = np.linalg.norm(mean)
    if norm > 0:
        mean = mean / norm
    return mean.astype(np.float32)


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(left, right))


def _speaker_names_by_first_appearance(
    clusters: list[int],
    speaker_segments: list[SpeakerSegment],
) -> dict[int, str]:
    ordered_clusters = sorted(
        set(clusters),
        key=lambda cluster_id: min(
            segment.start
            for segment, segment_cluster in zip(speaker_segments, clusters)
            if segment_cluster == cluster_id
        ),
    )
    return {
        cluster_id: f"Speaker {index + 1}"
        for index, cluster_id in enumerate(ordered_clusters)
    }


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
