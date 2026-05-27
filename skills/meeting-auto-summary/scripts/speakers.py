from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    min_duration: float = 0.0,
    merge_gap: float = 0.0,
    chunk_duration: float = 30.0,
    global_clustering: bool = True,
    clustering_threshold: float = 0.9,
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
        clustering_threshold=clustering_threshold,
        speaker_count=speaker_count,
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
    global_clustering: bool = True,
    clustering_threshold: float = 0.9,
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

    return globally_cluster_speakers(
        model,
        audio_path,
        merged_segments,
        threshold=clustering_threshold,
        speaker_count=speaker_count,
        merge_gap=merge_gap,
    )


def globally_cluster_speakers(
    model: Any,
    audio_path: Path,
    speaker_segments: list[SpeakerSegment],
    *,
    threshold: float = 0.9,
    speaker_count: int | None = None,
    merge_gap: float = 0.0,
) -> list[SpeakerSegment]:
    embeddings = _extract_sortformer_segment_embeddings(
        model, audio_path, speaker_segments
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
    relabeled = _merge_adjacent_segments(relabeled, merge_gap=merge_gap)
    if speaker_count is None and _distorted_significant_speakers(
        speaker_segments, relabeled
    ):
        return speaker_segments
    return relabeled


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
                continue
            if abs(((left.start + left.end) / 2) - ((right.start + right.end) / 2)) <= local_window:
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
