---
name: meeting-auto-summary
description: Transcribe a meeting audio/video file, optionally separate speakers, generate subtitle/transcript files, optionally translate outputs, and produce polished summary.md/report.md files in the requested output folder. Use when the user wants meeting media converted into subtitles, transcript, and meeting notes.
---

# Meeting Auto Summary

Use this skill to turn a local meeting audio/video file into a same-folder output set:

- `audio.wav`
- `transcript.md`
- `subtitles.srt`
- `subtitles.txt`
- `summary.md`
- `report.md` when the user asks for a more formal or shareable report

## Interaction Policy

At the start, confirm the interaction language if it is ambiguous. Default to the language used by the user in their request.

Ask whether the transcript-derived text outputs should be translated. If the user wants translation, ask for:

- Target language name, for example `English`, `Japanese`, or `Chinese`.
- File suffix, preferably an ISO-like short code such as `en`, `ja`, or `zh`.

When translation is requested, keep the original files and create translated variants with `-<suffix>` before the extension:

```text
transcript-en.md
subtitles-en.srt
subtitles-en.txt
summary-en.md
report-en.md
```

Use the requested interaction language for questions, progress updates, and final response unless the user changes it.

## Workflow

1. Prepare and validate the environment.
2. Ask for missing input path, output directory, interaction language, and translation settings.
3. Run the local transcription script once with `--output-dir`.
4. Generate `summary.md` from `transcript.md` or `subtitles.txt`.
5. Generate `report.md` if requested or if the user asks for a formal/shareable meeting report.
6. Generate translated `-<suffix>` variants if requested.
7. Verify expected files exist.

## Environment

The skill directory contains the runner and local model folders:

```text
skills/meeting-auto-summary/
├── run.py
├── scripts/
└── model/
    ├── Qwen3-ASR-0.6B-6bit/
    └── diar_sortformer_4spk-v1-fp16/
```

Before running transcription, resolve the installed skill directory first:

```bash
SKILL_DIR="<path-to-installed-meeting-auto-summary-skill>"
```

Examples:

```bash
SKILL_DIR="skills/meeting-auto-summary"
SKILL_DIR="$HOME/.claude/skills/meeting-auto-summary"
SKILL_DIR="$HOME/.agents/skills/meeting-auto-summary"
```

Then check:

```bash
test -x .venv/bin/python
test -d "$SKILL_DIR/model/Qwen3-ASR-0.6B-6bit"
test -d "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16"
ffmpeg -version
.venv/bin/python "$SKILL_DIR/run.py" --help
```

If any check fails, report the missing dependency/path and stop before running the long job.

## Required Inputs

You need:

- Input media path: local audio or video file.
- Output directory: where generated files should be written.

If the user does not provide either value, ask before running. If the user provides only the input file, default the output directory to:

```text
<project-root>/tmp/<input-file-stem>/
```

If the user provides an output directory, keep generated files directly under that directory. Do not scatter outputs across multiple folders.

## Transcription

Run from the project root:

```bash
.venv/bin/python "$SKILL_DIR/run.py" "<input-media>" \
  --model "$SKILL_DIR/model/Qwen3-ASR-0.6B-6bit" \
  --speaker-mode diarize \
  --diarization-model "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16" \
  --output-dir "<output-dir>" \
  --title "<input-file-stem>"
```

Use `--speaker-mode none` only if the user explicitly does not want speaker separation or the diarization model is unavailable.

The `--output-dir` mode writes `audio.wav`, `transcript.md`, `subtitles.srt`, and `subtitles.txt` in one ASR pass. Use `--output`/`--format` only when the user asks for a single file.

For long media, expect the ASR step to take time. The diarization path uses chunked streaming to avoid Metal out-of-memory errors.

## Summary

After `transcript.md` or `subtitles.txt` exists, generate:

```text
<output-dir>/summary.md
```

`summary.md` should be polished meeting notes, not a raw transcript. Write it in the interaction language unless the user specifies otherwise. Use this structure unless the user asks for a different format:

```markdown
# Meeting Summary

> Source: `transcript.md`
> Note: If speaker names are not explicit, infer from Speaker labels and context; mark uncertain attributions clearly.

## 1. Overall Conclusion

## 2. Speaker Mapping

| Speaker | Identification Basis | Main Contributions |
|---|---|---|

## 3. Main Topics

### Topic 1: ...

#### Background
#### Discussion
#### Decisions
#### Follow-up

## 4. Action Items

| Item | Owner | Due / Follow-up | Status |
|---|---|---|---|

## 5. Whether to Continue Next Time
```

Use concise paraphrasing. Do not paste the full transcript into `summary.md`.

## Report

Generate `report.md` when the user asks for a formal report, shareable document, customer-facing recap, or detailed meeting output. Compared with `summary.md`, `report.md` should be more polished and self-contained:

- Start with a short executive summary.
- Group discussion by themes.
- Include decisions, risks, open questions, and next steps.
- Include speaker attribution only when useful.

If translation is requested, translate both `summary.md` and `report.md` into the target language and save the translated files with the requested suffix.

## Translation

Translation applies to transcript-derived text files only. Do not translate `audio.wav`.

When translating subtitles:

- Preserve SRT numbering and timestamps exactly.
- Translate only subtitle text lines.
- Preserve speaker labels unless the user asks to localize them.

When translating Markdown:

- Preserve headings, tables, links, and code spans.
- Translate prose and table content.
- Keep source file references such as `transcript.md` unchanged unless the user asks otherwise.

## Verification

Before final response, run:

```bash
ls -lh "<output-dir>"
test -s "<output-dir>/transcript.md"
test -s "<output-dir>/summary.md"
test -s "<output-dir>/subtitles.srt"
test -s "<output-dir>/subtitles.txt"
```

If `report.md` was requested, verify it too:

```bash
test -s "<output-dir>/report.md"
```

If translation was requested, verify every requested translated file:

```bash
test -s "<output-dir>/transcript-<suffix>.md"
test -s "<output-dir>/subtitles-<suffix>.srt"
test -s "<output-dir>/subtitles-<suffix>.txt"
test -s "<output-dir>/summary-<suffix>.md"
```

Final response should give clickable paths to generated files and mention any skipped outputs.
