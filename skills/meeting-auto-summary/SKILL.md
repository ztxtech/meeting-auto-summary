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

All assistant replies for this skill must use the same language as the user's current message. This applies to questions, progress updates, error messages, and the final response. Do not ask the user to choose an interaction language. If the user changes language in a later message, switch to that language in the next reply.

Output document language is separate from reply language. Write generated notes in the user's current message language unless the user explicitly asks for a different output language or translation.

Any workflow choice must be explicitly chosen by the user unless their prompt already specifies it. A recommendation is only a recommendation; never treat it as consent to proceed. If a choice is missing, ask before downloading models, running ASR, generating optional outputs, or translating files.

For choices, show the recommended option first and explain the tradeoff briefly. Do not auto-select the recommendation after showing it. Wait for the user's answer.

Required decision gates:

- ASR model variant.
- Whether to enable speaker separation / diarization.
- Whether transcript-derived outputs should be translated.
- Whether to generate `report.md` in addition to `summary.md`.
- Output directory when the user has not explicitly provided one.

Ask these decisions in one concise batch when possible. If the user explicitly specifies some choices in the prompt, only ask for the missing choices. If the user explicitly asks to use defaults, present the defaults and ask for confirmation before continuing.

For translation, ask whether the transcript-derived text outputs should be translated. If the user wants translation, ask for:

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

Use the user's current message language for all conversation replies.

## Workflow

1. Prepare and validate the environment.
2. Ask for missing input path and all missing decision-gate choices.
3. Select or install the user-selected ASR model variant.
4. Install the diarization model only if the user chose speaker separation.
5. Run the local transcription script once with `--output-dir`.
6. Generate `summary.md` from `transcript.md` or `subtitles.txt`.
7. Generate `report.md` only if requested or explicitly chosen.
8. Generate translated `-<suffix>` variants only if requested or explicitly chosen.
9. Verify expected files exist.

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

Environment preparation is mandatory. Do not run transcription until every required dependency and every user-selected model is installed and verified. If anything is missing, guide the user through installation and continue checking until the environment is complete.

The Python virtual environment must be created in the same directory as this `SKILL.md` file:

```text
<skill-dir>/.venv
```

In commands, this path is always:

```bash
"$SKILL_DIR/.venv"
```

Do not use a workspace-root `.venv`, system Python, Conda environment, or any unrelated project environment for this skill.

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

Then inspect the Mac and check the base runtime:

```bash
system_profiler SPHardwareDataType | sed -n '1,30p'
sysctl -n hw.memsize
test -x "$SKILL_DIR/.venv/bin/python"
ffmpeg -version
huggingface-cli --help
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/run.py" --help
"$SKILL_DIR/.venv/bin/python" - <<'PY'
import mlx_audio
print("mlx_audio ok")
PY
```

After the user selects speaker separation, also check:

```bash
test -d "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16"
```

If any check fails, stop the workflow and install or ask the user to install the missing part. After installation, rerun the full check. Do not accept partial setup as "good enough".

Required setup items:

| Item | Required state |
|---|---|
| Python virtual environment | `$SKILL_DIR/.venv/bin/python` exists and can run the skill runner |
| `mlx-audio` | Import succeeds inside `$SKILL_DIR/.venv` |
| `ffmpeg` | `ffmpeg -version` succeeds |
| Hugging Face CLI | `huggingface-cli --help` succeeds or an equivalent download method is available |
| Qwen3-ASR MLX model | The selected ASR model directory exists under `$SKILL_DIR/model/` |
| Sortformer diarization model | `$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16` exists only when speaker separation is requested |

Typical install commands:

```bash
python3 -m venv "$SKILL_DIR/.venv"
"$SKILL_DIR/.venv/bin/python" -m pip install -U pip
"$SKILL_DIR/.venv/bin/python" -m pip install -U mlx-audio huggingface_hub
brew install ffmpeg
```

If Homebrew is unavailable, tell the user which system dependency is missing and ask them to install `ffmpeg` with their package manager.

## Decision Gates

When the prompt does not already answer these items, ask before continuing. Use the user's current message language.

Example question batch:

```text
I found/received the input file. Before I run transcription, please choose:

1. ASR model: recommended `mlx-community/Qwen3-ASR-0.6B-6bit` for this Mac, or choose another from the list below.
2. Speaker separation: yes/no. Recommended: yes for multi-person meetings.
3. Translation: no, or target language + suffix such as `English/en`.
4. Report: generate only `summary.md`, or also generate `report.md`.
5. Output directory: use `<project-root>/tmp/<input-file-stem>/`, or provide another path.
```

Proceed only after the user answers the missing choices. If the answer is ambiguous, ask a targeted follow-up.

## ASR Model Selection

During environment preparation, ask the user which Qwen3-ASR MLX model variant they want to use. First inspect the system memory and give a recommendation, but always show the available list because a powerful Mac may still prefer a smaller/faster model.

Do not run with the recommended ASR model until the user explicitly chooses or confirms it.

Use the MLX Community Qwen3-ASR collection as the source for available ASR models:

```text
https://huggingface.co/collections/mlx-community/qwen3-asr
```

Use this recommendation heuristic:

| Mac memory | Recommended default | Notes |
|---|---|---|
| 8 GB | `mlx-community/Qwen3-ASR-0.6B-4bit` | Smallest and safest option. |
| 16 GB | `mlx-community/Qwen3-ASR-0.6B-6bit` | Balanced default. |
| 24-36 GB | `mlx-community/Qwen3-ASR-1.7B-4bit` | Better recognition quality with moderate memory. |
| 48 GB or more | `mlx-community/Qwen3-ASR-1.7B-6bit` | Higher quality; user may still choose a smaller model for speed. |
| 64 GB or more | `mlx-community/Qwen3-ASR-1.7B-8bit` or `mlx-community/Qwen3-ASR-1.7B-bf16` | Use only when the user prioritizes quality over memory/speed. |

Available MLX ASR variants to present:

```text
mlx-community/Qwen3-ASR-0.6B-4bit
mlx-community/Qwen3-ASR-0.6B-5bit
mlx-community/Qwen3-ASR-0.6B-6bit
mlx-community/Qwen3-ASR-0.6B-8bit
mlx-community/Qwen3-ASR-0.6B-bf16
mlx-community/Qwen3-ASR-1.7B-4bit
mlx-community/Qwen3-ASR-1.7B-5bit
mlx-community/Qwen3-ASR-1.7B-6bit
mlx-community/Qwen3-ASR-1.7B-8bit
mlx-community/Qwen3-ASR-1.7B-bf16
```

If the chosen model is not installed, install it under the skill model directory:

```bash
mkdir -p "$SKILL_DIR/model"
huggingface-cli download mlx-community/Qwen3-ASR-0.6B-6bit \
  --local-dir "$SKILL_DIR/model/Qwen3-ASR-0.6B-6bit"
```

Replace both the Hugging Face repository name and local directory name with the user's chosen variant. After download, set:

```bash
ASR_MODEL_DIR="$SKILL_DIR/model/<chosen-qwen3-asr-folder>"
```

If the model already exists locally, set `ASR_MODEL_DIR` to that path and do not redownload.

## Diarization Model

Use the MLX Community Sortformer speaker diarization model for speaker separation:

```text
https://huggingface.co/mlx-community/diar_sortformer_4spk-v1-fp16
```

If it is not installed, download it under the skill model directory:

```bash
mkdir -p "$SKILL_DIR/model"
huggingface-cli download mlx-community/diar_sortformer_4spk-v1-fp16 \
  --local-dir "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16"
```

Then set:

```bash
DIARIZATION_MODEL_DIR="$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16"
```

Only download or use the diarization model after the user explicitly chooses speaker separation. If the user chooses no speaker separation, run with `--speaker-mode none` and do not require the diarization model check.

## Required Inputs

You need:

- Input media path: local audio or video file.
- Output directory: where generated files should be written.

If the user does not provide either value, ask before running. If the user provides only the input file, recommend this output directory but ask the user to confirm or replace it:

```text
<project-root>/tmp/<input-file-stem>/
```

If the user provides an output directory, keep generated files directly under that directory. Do not scatter outputs across multiple folders.

## Transcription

Run from the project root:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/run.py" "<input-media>" \
  --model "$ASR_MODEL_DIR" \
  --speaker-mode diarize \
  --diarization-model "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16" \
  --speaker-global-clustering \
  --chunk-strategy adaptive \
  --chunk-duration 10 \
  --output-dir "<output-dir>" \
  --title "<input-file-stem>"
```

Use `--speaker-mode none` only if the user explicitly does not want speaker separation or the diarization model is unavailable.

The `--output-dir` mode writes `audio.wav`, `transcript.md`, `subtitles.srt`, and `subtitles.txt` in one ASR pass. Use `--output`/`--format` only when the user asks for a single file.

For long media, expect the ASR step to take time. ASR chunking defaults to `--chunk-strategy adaptive`, which uses low-energy points under `--chunk-duration` as dynamic cut points instead of blindly cutting every N seconds. Use `--chunk-strategy fixed` only when deterministic fixed windows are preferred.

The diarization path uses chunked streaming to avoid Metal out-of-memory errors. Global speaker clustering is enabled by default when diarization is enabled. By default it reuses Sortformer encoder representations to relabel speaker segments across the full audio. Use `--no-speaker-global-clustering` only when the user wants the raw streaming Sortformer labels.

For stronger voiceprint clustering, use the optional CAMPPlus backend:

```bash
--speaker-embedding-backend campplus \
--speaker-embedding-model "$SKILL_DIR/model/speech_campplus_sv_zh-cn_16k-common"
```

CAMPPlus requires optional `funasr`, `torch`, and `torchaudio` dependencies plus the local 3D-Speaker/CAMPPlus model. If these are missing, report that CAMPPlus is unavailable and either install them or fall back to `--speaker-embedding-backend sortformer`.

If the user knows the expected participant count, add `--speaker-count <count>` to constrain global clustering. Mention that the bundled Sortformer model is a 4-speaker diarization model, so an expected count above 4 is only a best-effort global relabeling aid.

## Summary

After `transcript.md` or `subtitles.txt` exists, generate:

```text
<output-dir>/summary.md
```

`summary.md` should be polished meeting notes, not a raw transcript. Write it in the user's current message language unless the user specifies otherwise. Use this structure unless the user asks for a different format:

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
