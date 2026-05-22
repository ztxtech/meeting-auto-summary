from __future__ import annotations

import html

from scripts.transcribe import Segment, Transcript


def render_txt(transcript: Transcript) -> str:
    if transcript.segments:
        return (
            "\n".join(
                _format_plain_segment(segment) for segment in transcript.segments
            ).strip()
            + "\n"
        )
    return transcript.text.strip() + "\n"


def render_markdown(transcript: Transcript, title: str | None = None) -> str:
    heading = title or "Meeting Transcript"
    lines = [f"# {heading}", "", "## Transcript", ""]

    if transcript.segments:
        for segment in transcript.segments:
            text = segment.text.strip()
            if segment.speaker:
                lines.append(f"**{segment.speaker}:** {text}")
            else:
                lines.append(text)
            lines.append("")
    elif transcript.text.strip():
        lines.append(transcript.text.strip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_srt(transcript: Transcript) -> str:
    if not transcript.segments:
        raise ValueError(
            "SRT output requires timestamped segments, but no segments were returned."
        )

    blocks = []
    for index, segment in enumerate(transcript.segments, start=1):
        if segment.start is None or segment.end is None:
            raise ValueError(
                "SRT output requires timestamped segments, but the ASR result did not include timestamps."
            )
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(segment.start)} --> {format_srt_timestamp(segment.end)}",
                    _format_plain_segment(segment),
                ]
            )
        )

    return "\n\n".join(blocks) + "\n"


def render_transcript(
    transcript: Transcript, output_format: str, title: str | None = None
) -> str:
    if output_format == "txt":
        return render_txt(transcript)
    if output_format == "md":
        return render_markdown(transcript, title)
    if output_format == "srt":
        return render_srt(transcript)
    raise ValueError(f"Unsupported output format: {output_format}")


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _format_plain_segment(segment: Segment) -> str:
    text = html.unescape(segment.text.strip())
    if segment.speaker:
        return f"{segment.speaker}: {text}"
    return text
