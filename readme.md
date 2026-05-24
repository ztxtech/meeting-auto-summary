<h1 align="center">
  <img src="https://img.shields.io/badge/Meeting_Auto_Summary-Local_Media_Notes-7C3AED?style=for-the-badge&logo=openai&logoColor=white" alt="Meeting Auto Summary" />
</h1>

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

**Meeting Auto Summary** is a local skill for turning meeting audio or video into structured meeting artifacts: speaker-aware transcripts, SRT subtitles, plain-text subtitles, summaries, formal reports, and optional translated variants.

It bundles a small local ASR pipeline based on **Qwen3-ASR MLX** and a lightweight **Sortformer MLX diarization** model. The skill is designed for coding-agent workflows where the agent should first validate the local environment, ask for missing input/output details, run the transcription script, and then write `summary.md` / `report.md` in the requested output folder.

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-Local-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#-install-the-skill"><img src="https://img.shields.io/badge/Install-Skills-8B5CF6?style=for-the-badge" alt="Install"></a>
  <a href="#-supported-agents"><img src="https://img.shields.io/badge/Agents-5-10B981?style=for-the-badge" alt="Agents"></a>
  <a href="#-outputs"><img src="https://img.shields.io/badge/Outputs-Transcript%2FSubtitles%2FSummary-F59E0B?style=for-the-badge" alt="Outputs"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/MLX-Audio-06B6D4?style=flat" alt="MLX Audio">
  <img src="https://img.shields.io/badge/ffmpeg-required-EC4899?style=flat" alt="ffmpeg">
  <img src="https://img.shields.io/badge/Apple_Silicon-recommended-111827?style=flat" alt="Apple Silicon">
</p>

---

## ✨ What It Does

The skill produces a same-folder output set:

```text
audio.wav
transcript.md
subtitles.srt
subtitles.txt
summary.md
report.md                 # when requested
transcript-<lang>.md       # when translation is requested
subtitles-<lang>.srt
subtitles-<lang>.txt
summary-<lang>.md
report-<lang>.md
```

Core workflow:

1. Validate Python, ffmpeg, MLX Audio, and bundled model paths.
2. Confirm the interaction language. The default is the user input language.
3. Ask for the input media path and output directory if missing.
4. Ask whether transcript-derived outputs should be translated.
5. Run local ASR and optional speaker diarization.
6. Generate `summary.md`, and `report.md` when requested.
7. Verify that all expected files exist.

---

## 🚀 Quick Start

From this repository root:

```bash
# Start the local web console
npm start
```

Open:

```text
http://localhost:5177
```

The console opens as a local media library. Use the top-bar Manage Folders panel to add local directories; the console recursively scans media in subdirectories and can browse by directory/all media and folder/list view. After selecting a media file, the workbench shows an adaptive player above a vertical subtitle timeline on the left, and report/context/speaker/artifact tools on the right. Dragging the media timeline follows the active subtitle, and clicking an SRT subtitle seeks the player to that timestamp.

```bash
# Check the runner
SKILL_DIR="skills/meeting-auto-summary"
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/run.py" --help

# Transcribe a media file into an output directory
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/run.py" example/iShot_2026-05-22_14.54.02.mp4 \
  --model skills/meeting-auto-summary/model/Qwen3-ASR-0.6B-6bit \
  --speaker-mode diarize \
  --diarization-model skills/meeting-auto-summary/model/diar_sortformer_4spk-v1-fp16 \
  --output-dir tmp/iShot_2026-05-22_14.54.02 \
  --title iShot_2026-05-22_14.54.02
```

Then ask your coding agent to use `$meeting-auto-summary` to create `summary.md` and optional translated files from the generated transcript.

### Web Console Notes

- Generated files stay in the same directory as the selected media.
- The page also reads existing skill outputs from `tmp/<media-stem>/` so older generated files can be managed.
- Manage Folders supports a native folder picker, manual path entry, current scan-root listing, and path removal.
- The media library recursively scans subdirectories; the default scan depth is 12 and can be adjusted in Settings.
- The folder browser hides generated files so media selection remains clean.
- The Files tab shows generated files for the selected media directory, with text preview and direct download actions.
- Markdown reports render tables, code blocks, Mermaid diagrams, and MathJax formulas.
- The Speakers tab can rename `Speaker 1`, `Speaker 2`, and similar labels to real names, then sync those names across transcript, subtitle, summary, report, and translated text outputs.
- The top-bar `A-` / `A+` controls adjust global text size for subtitles and reports.
- Settings currently support Chinese and English; extend `config/languages.json` to add more languages later.
- AI summarization and translation provider integrations are reserved under `server/providers/`; the current console creates copy-ready context instead of calling an external model directly.
- Project-level skill installation can be run from the console or with `npm run install:project-skills`.
- Environment checks and venv deployment can be run from the console or with `npm run check` / `npm run deploy:env`.
- `.m4a` / `.aac` and other compressed audio inputs are converted with ffmpeg into real 16 kHz mono PCM WAV before ASR, avoiding fake `audio.wav` files that still contain compressed audio bytes.

---

## 📦 Install the Skill

The install commands below copy the skill folder. They assume this repository is cloned locally and that models are already present under:

```text
skills/meeting-auto-summary/model/
```

Use `rsync` instead of `cp -R` so updates replace old script files cleanly while keeping the folder structure.

### Choose a Qwen3-ASR MLX Model

The skill can use any local Qwen3-ASR MLX model directory. During setup, the agent should inspect your Mac and recommend a model, but you can still choose a smaller model for speed or memory headroom.

Model collection:

```text
https://huggingface.co/collections/mlx-community/qwen3-asr
```

Check your Mac:

```bash
system_profiler SPHardwareDataType | sed -n '1,30p'
sysctl -n hw.memsize
```

Recommended defaults:

| Mac memory | Recommended model | When to choose it |
|---|---|---|
| 8 GB | `mlx-community/Qwen3-ASR-0.6B-4bit` | Safest small model |
| 16 GB | `mlx-community/Qwen3-ASR-0.6B-6bit` | Balanced default |
| 24-36 GB | `mlx-community/Qwen3-ASR-1.7B-4bit` | Better quality, moderate memory |
| 48 GB+ | `mlx-community/Qwen3-ASR-1.7B-6bit` | Higher quality |
| 64 GB+ | `mlx-community/Qwen3-ASR-1.7B-8bit` or `mlx-community/Qwen3-ASR-1.7B-bf16` | Quality first, slower/heavier |

Install a selected model:

```bash
SKILL_DIR="skills/meeting-auto-summary"
mkdir -p "$SKILL_DIR/model"
huggingface-cli download mlx-community/Qwen3-ASR-0.6B-6bit \
  --local-dir "$SKILL_DIR/model/Qwen3-ASR-0.6B-6bit"
```

Available variants to consider:

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

Speaker diarization model:

```text
https://huggingface.co/mlx-community/diar_sortformer_4spk-v1-fp16
```

Install it with:

```bash
huggingface-cli download mlx-community/diar_sortformer_4spk-v1-fp16 \
  --local-dir "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16"
```

### Claude Code

Claude Code skills are documented as Markdown skill folders under `.claude/skills`. Project skills live in the project, and user skills live under the user Claude directory.

User-level install:

```bash
mkdir -p "$HOME/.claude/skills"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.claude/skills/meeting-auto-summary/"
```

Project-level install:

```bash
mkdir -p .claude/skills
rsync -a --delete skills/meeting-auto-summary/ .claude/skills/meeting-auto-summary/
```

### Codex

Codex skills use `SKILL.md` folders. Current OpenAI Codex documentation describes project skills under `.agents/skills`; this local Codex setup also supports user skills under `$CODEX_HOME/skills` or `~/.codex/skills`.

User-level install:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills"
rsync -a --delete skills/meeting-auto-summary/ "$CODEX_HOME/skills/meeting-auto-summary/"
```

Project-level install:

```bash
mkdir -p .agents/skills
rsync -a --delete skills/meeting-auto-summary/ .agents/skills/meeting-auto-summary/
```

### OpenCode

OpenCode supports its native project skill directory and also supports Claude-style skill folders in many setups.

User-level install:

```bash
mkdir -p "$HOME/.config/opencode/skill"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.config/opencode/skill/meeting-auto-summary/"
```

Project-level install:

```bash
mkdir -p .opencode/skill
rsync -a --delete skills/meeting-auto-summary/ .opencode/skill/meeting-auto-summary/
```

Compatibility project install:

```bash
mkdir -p .claude/skills
rsync -a --delete skills/meeting-auto-summary/ .claude/skills/meeting-auto-summary/
```

### OpenClaw

OpenClaw documents workspace, personal, and managed skill locations. Use workspace installation for repository-specific workflows and personal installation for reuse across projects.

User-level install:

```bash
mkdir -p "$HOME/.openclaw/skills"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.openclaw/skills/meeting-auto-summary/"
```

Project-level install:

```bash
mkdir -p .openclaw/skills
rsync -a --delete skills/meeting-auto-summary/ .openclaw/skills/meeting-auto-summary/
```

### Hermes

Hermes skills are installed under `~/.hermes/skills`. For project-scoped usage, keep the skill in the repository and configure Hermes external skill directories or add this repository as a Hermes-accessible skill source.

User-level install:

```bash
mkdir -p "$HOME/.hermes/skills"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.hermes/skills/meeting-auto-summary/"
```

Project-level install:

```bash
mkdir -p .hermes/skills
rsync -a --delete skills/meeting-auto-summary/ .hermes/skills/meeting-auto-summary/
```

If your Hermes build only loads `~/.hermes/skills`, point its external skill directory setting at:

```text
<your-project>/.hermes/skills
```

---

## 🧰 Environment

The environment must be fully installed before transcription. Do not run the long ASR job until Python, MLX Audio, ffmpeg, Hugging Face download tooling, and the selected models all pass checks.

Required:

| Dependency | Purpose |
|---|---|
| Skill-local Python virtualenv `$SKILL_DIR/.venv` | Runs the transcription scripts |
| `mlx-audio` | ASR and diarization backend |
| `ffmpeg` | Extracts 16 kHz mono audio from video |
| `Qwen3-ASR-0.6B-6bit` | Local speech recognition model |
| `diar_sortformer_4spk-v1-fp16` | Local MLX speaker diarization model |

Check:

```bash
SKILL_DIR="skills/meeting-auto-summary"
test -x "$SKILL_DIR/.venv/bin/python"
ffmpeg -version
huggingface-cli --help
"$SKILL_DIR/.venv/bin/python" - <<'PY'
import mlx_audio
print("mlx_audio ok")
PY
```

Install the base Python environment when missing:

```bash
SKILL_DIR="skills/meeting-auto-summary"
python3 -m venv "$SKILL_DIR/.venv"
"$SKILL_DIR/.venv/bin/python" -m pip install -U pip
"$SKILL_DIR/.venv/bin/python" -m pip install -U mlx-audio huggingface_hub
brew install ffmpeg
```

---

## 📁 Outputs

`--output-dir` mode writes:

| File | Description |
|---|---|
| `audio.wav` | Extracted 16 kHz mono audio |
| `transcript.md` | Markdown transcript with speaker labels when diarization is enabled |
| `subtitles.srt` | Pure SRT subtitles with timestamps |
| `subtitles.txt` | Plain text subtitle-style transcript |
| `summary.md` | Agent-written meeting summary |
| `report.md` | Optional formal report |

Translated variants use `-<suffix>`:

```text
summary-en.md
report-en.md
subtitles-en.srt
```

---

## 🧭 Supported Agents

This repository includes a portable `SKILL.md`, so the same folder can be copied into multiple agent ecosystems.

| Agent | User-level path | Project-level path |
|---|---|---|
| Claude Code | `~/.claude/skills/meeting-auto-summary` | `.claude/skills/meeting-auto-summary` |
| Codex | `$CODEX_HOME/skills/meeting-auto-summary` or `~/.codex/skills/meeting-auto-summary` | `.agents/skills/meeting-auto-summary` |
| OpenCode | `~/.config/opencode/skill/meeting-auto-summary` | `.opencode/skill/meeting-auto-summary` |
| OpenClaw | `~/.openclaw/skills/meeting-auto-summary` | `.openclaw/skills/meeting-auto-summary` |
| Hermes | `~/.hermes/skills/meeting-auto-summary` | `.hermes/skills/meeting-auto-summary` or external skill dir |

---

## 📚 References

- Claude Code skills: https://docs.claude.com/en/docs/claude-code/skills
- Codex skills: https://developers.openai.com/codex/skills
- OpenCode documentation: https://opencode.ai/docs
- OpenClaw skills: https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md
- Hermes skills: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md

---

## 📄 License

Use the license terms of this repository and the upstream model licenses for bundled model files.
