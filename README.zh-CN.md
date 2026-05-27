<h1 align="center">
  <img src="https://img.shields.io/badge/Meeting_Auto_Summary-Local_Media_Notes-7C3AED?style=for-the-badge&logo=openai&logoColor=white" alt="Meeting Auto Summary" />
</h1>

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

**Meeting Auto Summary** 是一个本地会议音视频处理 skill，用于把会议音频或视频转换成结构化产物：带说话人标签的转写稿、SRT 字幕、纯文本字幕、会议总结、正式报告，以及可选的翻译版本。

它内置基于 **Qwen3-ASR MLX** 的本地语音识别流程，以及轻量的 **Sortformer MLX 人声区分**模型。这个 skill 面向编码 Agent 工作流：Agent 会先检查本地环境，再询问缺失的输入/输出信息，运行转写脚本，最后在指定输出目录生成 `summary.md` / `report.md`。

<p align="center">
  <a href="#-快速开始"><img src="https://img.shields.io/badge/Quick_Start-Local-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#-安装-skill"><img src="https://img.shields.io/badge/Install-Skills-8B5CF6?style=for-the-badge" alt="Install"></a>
  <a href="#-支持的-agent"><img src="https://img.shields.io/badge/Agents-5-10B981?style=for-the-badge" alt="Agents"></a>
  <a href="#-输出文件"><img src="https://img.shields.io/badge/Outputs-Transcript%2FSubtitles%2FSummary-F59E0B?style=for-the-badge" alt="Outputs"></a>
</p>

---

## ✨ 功能

这个 skill 会在同一个输出目录下生成：

```text
audio.wav
transcript.md
subtitles.srt
subtitles.txt
summary.md
report.md                 # 用户需要正式报告时生成
transcript-<lang>.md       # 用户需要翻译时生成
subtitles-<lang>.srt
subtitles-<lang>.txt
summary-<lang>.md
report-<lang>.md
```

核心流程：

1. 检查 Python、ffmpeg、MLX Audio 和模型路径。
2. 确认交互语言；默认使用用户输入语言。
3. 如果缺少输入媒体路径或输出目录，先询问用户。
4. 询问是否需要翻译转写相关文件。
5. 运行本地 ASR 和可选人声区分。
6. 生成 `summary.md`，需要时生成 `report.md`。
7. 检查所有预期文件是否存在。

---

## 🚀 快速开始

在仓库根目录运行：

```bash
# 启动本地 Web 控制台
npm start
```

打开：

```text
http://localhost:5177
```

控制台进入后就是本地媒体库视图。通过顶部“管理文件夹”添加本地目录后，控制台会递归扫描子目录里的音视频文件，并可以用“按目录 / 所有媒体”和“文件夹 / 列表”两种方式浏览。进入媒体工作台后，左侧上方是自适应播放器，左侧下方是垂直时间轴字幕；视频拖动会自动定位字幕，点击字幕也会跳转到对应时间。右侧集中展示 `summary.md` / `report.md`、AI 上下文、说话人名称编辑、生成文件、转写和设置。

```bash
# 检查 runner
SKILL_DIR="skills/meeting-auto-summary"
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/run.py" --help

# 将音视频转写到输出目录
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/run.py" example/iShot_2026-05-22_14.54.02.mp4 \
  --model skills/meeting-auto-summary/model/Qwen3-ASR-0.6B-6bit \
  --speaker-mode diarize \
  --diarization-model skills/meeting-auto-summary/model/diar_sortformer_4spk-v1-fp16 \
  --speaker-global-clustering \
  --output-dir tmp/iShot_2026-05-22_14.54.02 \
  --title iShot_2026-05-22_14.54.02
```

启用 `--speaker-mode diarize` 时默认会执行全局说话人聚类：先用 Sortformer 流式切出说话时间段，再复用 Sortformer encoder 表征对整段音频的片段做全局聚类并重新编号，降低长视频里跨窗口 `Speaker 1` / `Speaker 2` 漂移的概率。可用 `--no-speaker-global-clustering` 关闭，或用 `--speaker-clustering-threshold` 调整合并阈值。

如果已知参会人数，可以加 `--speaker-count <人数>` 进行约束聚类。例如答辩场景里 1 名学生加 5 名老师可以传 `--speaker-count 6`。当前内置 Sortformer 是 4 speaker 模型，已知人数约束可以改善跨时段重编号，但不能保证每个真实人物都被稳定拆成独立标签。

然后让你的编码 Agent 使用 `$meeting-auto-summary`，根据生成的转写稿创建 `summary.md` 和可选翻译文件。

### Web 控制台说明

- 生成文件始终保存在所选媒体的同一目录。
- 页面也会读取仓库 `tmp/<媒体文件名>/` 下已有的 skill 输出，方便继续管理旧产物。
- “管理文件夹”支持系统原生目录选择器、手动添加路径、查看和移除已添加扫描目录。
- 媒体库会递归扫描子目录；默认扫描深度为 12，可在设置里调整。
- 文件夹浏览区会隐藏 `transcript.md`、`subtitles.srt`、`summary.md` 等生成文件。
- “文件”选项卡会显示当前媒体目录下的生成文件，并可直接预览文本内容或下载文件。
- Markdown 报告支持表格、代码块、Mermaid 图和 MathJax 公式渲染。
- “说话人”选项卡可以把 `Speaker 1`、`Speaker 2` 等改成真实姓名，并同步写回 `transcript.md`、`subtitles.srt`、`subtitles.txt`、`summary.md`、`report.md` 及翻译版本。
- 顶部 `A-` / `A+` 可以调整字幕和报告的全局文字大小。
- 设置当前只支持中文和英文；后续新增语言请扩展 `config/languages.json`。
- AI 总结和翻译 provider 预留在 `server/providers/`；当前版本先生成可复制到对话框的上下文，不直接调用外部模型。
- 项目级 skill 安装可以在控制台执行，也可以运行 `npm run install:project-skills`。
- 环境检查和 venv 部署可以在控制台执行，也可以运行 `npm run check` / `npm run deploy:env`。
- 对于 `.m4a` / `.aac` 等音频输入，转写前会先用 ffmpeg 转成真正的 16 kHz 单声道 PCM WAV，避免把压缩音频直接伪装成 `audio.wav`。

---

## 📦 安装 Skill

下面的命令会复制 skill 目录。假设你已经在本地 clone 了本仓库，并且模型已经位于：

```text
skills/meeting-auto-summary/model/
```

建议使用 `rsync` 而不是 `cp -R`，这样更新时可以干净地替换旧脚本文件，同时保留目录结构。

### 选择 Qwen3-ASR MLX 模型

这个 skill 可以使用任意本地 Qwen3-ASR MLX 模型目录。环境准备阶段，Agent 应该先检查你的 Mac 配置并给出推荐，但你仍然可以为了速度或内存余量主动选择更小的模型。

模型 collection：

```text
https://huggingface.co/collections/mlx-community/qwen3-asr
```

检查 Mac 配置：

```bash
system_profiler SPHardwareDataType | sed -n '1,30p'
sysctl -n hw.memsize
```

推荐默认值：

| Mac 内存 | 推荐模型 | 适用场景 |
|---|---|---|
| 8 GB | `mlx-community/Qwen3-ASR-0.6B-4bit` | 最稳妥的小模型 |
| 16 GB | `mlx-community/Qwen3-ASR-0.6B-6bit` | 平衡默认选择 |
| 24-36 GB | `mlx-community/Qwen3-ASR-1.7B-4bit` | 更好识别质量，内存压力适中 |
| 48 GB+ | `mlx-community/Qwen3-ASR-1.7B-6bit` | 更高质量 |
| 64 GB+ | `mlx-community/Qwen3-ASR-1.7B-8bit` 或 `mlx-community/Qwen3-ASR-1.7B-bf16` | 质量优先，速度和内存成本更高 |

安装所选模型：

```bash
SKILL_DIR="skills/meeting-auto-summary"
mkdir -p "$SKILL_DIR/model"
huggingface-cli download mlx-community/Qwen3-ASR-0.6B-6bit \
  --local-dir "$SKILL_DIR/model/Qwen3-ASR-0.6B-6bit"
```

可选版本：

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

人声区分模型：

```text
https://huggingface.co/mlx-community/diar_sortformer_4spk-v1-fp16
```

安装命令：

```bash
huggingface-cli download mlx-community/diar_sortformer_4spk-v1-fp16 \
  --local-dir "$SKILL_DIR/model/diar_sortformer_4spk-v1-fp16"
```

### Claude Code

Claude Code 的 skills 是包含 `SKILL.md` 的 Markdown skill 文件夹。项目级 skill 位于项目目录，用户级 skill 位于用户 Claude 目录。

用户级安装：

```bash
mkdir -p "$HOME/.claude/skills"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.claude/skills/meeting-auto-summary/"
```

项目级安装：

```bash
mkdir -p .claude/skills
rsync -a --delete skills/meeting-auto-summary/ .claude/skills/meeting-auto-summary/
```

### Codex

Codex skills 使用包含 `SKILL.md` 的文件夹。当前 OpenAI Codex 文档描述的项目级路径是 `.agents/skills`；本地 Codex 环境也支持 `$CODEX_HOME/skills` 或 `~/.codex/skills` 下的用户级 skill。

用户级安装：

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills"
rsync -a --delete skills/meeting-auto-summary/ "$CODEX_HOME/skills/meeting-auto-summary/"
```

项目级安装：

```bash
mkdir -p .agents/skills
rsync -a --delete skills/meeting-auto-summary/ .agents/skills/meeting-auto-summary/
```

### OpenCode

OpenCode 支持原生项目 skill 目录，很多设置中也兼容 Claude 风格的 skill 文件夹。

用户级安装：

```bash
mkdir -p "$HOME/.config/opencode/skill"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.config/opencode/skill/meeting-auto-summary/"
```

项目级安装：

```bash
mkdir -p .opencode/skill
rsync -a --delete skills/meeting-auto-summary/ .opencode/skill/meeting-auto-summary/
```

兼容项目级安装：

```bash
mkdir -p .claude/skills
rsync -a --delete skills/meeting-auto-summary/ .claude/skills/meeting-auto-summary/
```

### OpenClaw

OpenClaw 文档中有 workspace、personal 和 managed 多级 skill 位置。仓库专用流程建议用 workspace 安装；跨项目复用建议用 personal 安装。

用户级安装：

```bash
mkdir -p "$HOME/.openclaw/skills"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.openclaw/skills/meeting-auto-summary/"
```

项目级安装：

```bash
mkdir -p .openclaw/skills
rsync -a --delete skills/meeting-auto-summary/ .openclaw/skills/meeting-auto-summary/
```

### Hermes

Hermes skills 安装在 `~/.hermes/skills`。如果要项目级使用，可以把 skill 保留在仓库内，并配置 Hermes 的 external skill directories，或者把这个仓库作为 Hermes 可访问的 skill source。

用户级安装：

```bash
mkdir -p "$HOME/.hermes/skills"
rsync -a --delete skills/meeting-auto-summary/ "$HOME/.hermes/skills/meeting-auto-summary/"
```

项目级安装：

```bash
mkdir -p .hermes/skills
rsync -a --delete skills/meeting-auto-summary/ .hermes/skills/meeting-auto-summary/
```

如果你的 Hermes 版本只加载 `~/.hermes/skills`，请把它的 external skill directory 指向：

```text
<your-project>/.hermes/skills
```

---

## 🧰 环境

转写前必须完整安装环境。不要在 Python、MLX Audio、ffmpeg、Hugging Face 下载工具和所选模型全部检查通过之前启动长时间 ASR 任务。

依赖：

| 依赖 | 用途 |
|---|---|
| skill 本地 Python 虚拟环境 `$SKILL_DIR/.venv` | 运行转写脚本 |
| `mlx-audio` | ASR 和人声区分后端 |
| `ffmpeg` | 从视频抽取 16 kHz 单声道音频 |
| `Qwen3-ASR-0.6B-6bit` | 本地语音识别模型 |
| `diar_sortformer_4spk-v1-fp16` | 本地 MLX 人声区分模型和全局说话人聚类表征 |

检查：

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

缺少基础 Python 环境时安装：

```bash
SKILL_DIR="skills/meeting-auto-summary"
python3 -m venv "$SKILL_DIR/.venv"
"$SKILL_DIR/.venv/bin/python" -m pip install -U pip
"$SKILL_DIR/.venv/bin/python" -m pip install -U mlx-audio huggingface_hub
brew install ffmpeg
```

---

## 📁 输出文件

`--output-dir` 模式会写入：

| 文件 | 说明 |
|---|---|
| `audio.wav` | 抽取后的 16 kHz 单声道音频 |
| `transcript.md` | Markdown 转写稿，启用人声区分时带全局重编号后的 speaker 标签 |
| `subtitles.srt` | 纯 SRT 字幕，带时间轴 |
| `subtitles.txt` | 纯文本字幕式转写 |
| `summary.md` | Agent 生成的会议总结 |
| `report.md` | 可选正式报告 |

翻译版本使用 `-<suffix>`：

```text
summary-en.md
report-en.md
subtitles-en.srt
```

---

## 🧭 支持的 Agent

本仓库包含可移植的 `SKILL.md`，同一个文件夹可以复制到多个 Agent 生态中。

| Agent | 用户级路径 | 项目级路径 |
|---|---|---|
| Claude Code | `~/.claude/skills/meeting-auto-summary` | `.claude/skills/meeting-auto-summary` |
| Codex | `$CODEX_HOME/skills/meeting-auto-summary` 或 `~/.codex/skills/meeting-auto-summary` | `.agents/skills/meeting-auto-summary` |
| OpenCode | `~/.config/opencode/skill/meeting-auto-summary` | `.opencode/skill/meeting-auto-summary` |
| OpenClaw | `~/.openclaw/skills/meeting-auto-summary` | `.openclaw/skills/meeting-auto-summary` |
| Hermes | `~/.hermes/skills/meeting-auto-summary` | `.hermes/skills/meeting-auto-summary` 或 external skill dir |

---

## 📚 参考资料

- Claude Code skills: https://docs.claude.com/en/docs/claude-code/skills
- Codex skills: https://developers.openai.com/codex/skills
- OpenCode documentation: https://opencode.ai/docs
- OpenClaw skills: https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md
- Hermes skills: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md

---

## 📄 License

请遵循本仓库许可证，以及所使用上游模型文件的许可证。
