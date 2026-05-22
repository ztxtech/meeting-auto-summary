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
# Check the runner
.venv/bin/python skills/meeting-auto-summary/run.py --help

# Transcribe a media file into an output directory
.venv/bin/python skills/meeting-auto-summary/run.py example/iShot_2026-05-22_14.54.02.mp4 \
  --model skills/meeting-auto-summary/model/Qwen3-ASR-0.6B-6bit \
  --speaker-mode diarize \
  --diarization-model skills/meeting-auto-summary/model/diar_sortformer_4spk-v1-fp16 \
  --output-dir tmp/iShot_2026-05-22_14.54.02 \
  --title iShot_2026-05-22_14.54.02
```

Then ask your coding agent to use `$meeting-auto-summary` to create `summary.md` and optional translated files from the generated transcript.

---

## 📦 Install the Skill

The install commands below copy the skill folder. They assume this repository is cloned locally and that models are already present under:

```text
skills/meeting-auto-summary/model/
```

Use `rsync` instead of `cp -R` so updates replace old script files cleanly while keeping the folder structure.

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

Required:

| Dependency | Purpose |
|---|---|
| Python virtualenv `.venv` | Runs the transcription scripts |
| `mlx-audio` | ASR and diarization backend |
| `ffmpeg` | Extracts 16 kHz mono audio from video |
| `Qwen3-ASR-0.6B-6bit` | Local speech recognition model |
| `diar_sortformer_4spk-v1-fp16` | Local MLX speaker diarization model |

Check:

```bash
test -x .venv/bin/python
ffmpeg -version
.venv/bin/python - <<'PY'
import mlx_audio
print("mlx_audio ok")
PY
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
