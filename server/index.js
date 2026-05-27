import { createReadStream, statSync } from 'node:fs';
import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { URL } from 'node:url';
import { checkEnvironment } from './check-env.js';
import { deployEnvironment } from './deploy-env.js';
import { installProjectSkills } from './install-project-skills.js';
import {
  diarizationModelPath,
  exists,
  expandHome,
  GENERATED_FILENAMES,
  isMediaFile,
  modelPath,
  pythonPath,
  readSettings,
  ROOT_DIR,
  SKILL_DIR,
  supportedLanguages,
  writeSettings
} from './shared.js';

const PORT = Number(process.env.PORT || 5177);
const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const jobs = new Map();

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.srt': 'text/plain; charset=utf-8',
  '.mp4': 'video/mp4',
  '.mov': 'video/quicktime',
  '.mkv': 'video/x-matroska',
  '.webm': 'video/webm',
  '.avi': 'video/x-msvideo',
  '.wav': 'audio/wav',
  '.mp3': 'audio/mpeg',
  '.m4a': 'audio/mp4',
  '.flac': 'audio/flac',
  '.aac': 'audio/aac',
  '.ogg': 'audio/ogg'
};

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);
    if (url.pathname.startsWith('/api/')) {
      await handleApi(req, res, url);
      return;
    }
    if (url.pathname === '/media') {
      await streamMedia(req, res, url);
      return;
    }
    if (url.pathname === '/download') {
      await downloadFile(res, url);
      return;
    }
    await serveStatic(res, url.pathname);
  } catch (error) {
    sendJson(res, 500, { error: error.message || String(error) });
  }
});

server.listen(PORT, () => {
  console.log(`Meeting Auto Summary console: http://localhost:${PORT}`);
});

async function handleApi(req, res, url) {
  if (req.method === 'GET' && url.pathname === '/api/settings') {
    sendJson(res, 200, {
      settings: await readSettings(),
      languages: await supportedLanguages(),
      modelVariants: modelVariants()
    });
    return;
  }

  if (req.method === 'PUT' && url.pathname === '/api/settings') {
    const body = await readBody(req);
    sendJson(res, 200, { settings: await writeSettings(body) });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/folders') {
    const body = await readBody(req);
    const folderPath = path.resolve(expandHome(body.path || ''));
    const folderStat = await stat(folderPath);
    if (!folderStat.isDirectory()) {
      sendJson(res, 400, { error: 'Path is not a directory' });
      return;
    }
    const settings = await readSettings();
    settings.folders = Array.from(new Set([...settings.folders, folderPath]));
    sendJson(res, 200, { settings: await writeSettings(settings) });
    return;
  }

  if (req.method === 'DELETE' && url.pathname === '/api/folders') {
    const body = await readBody(req);
    const settings = await readSettings();
    settings.folders = settings.folders.filter((folder) => folder !== body.path);
    sendJson(res, 200, { settings: await writeSettings(settings) });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/pick-folder') {
    const picked = await pickFolder();
    if (!picked) {
      sendJson(res, 200, { path: null });
      return;
    }
    const settings = await readSettings();
    settings.folders = Array.from(new Set([...settings.folders, picked]));
    sendJson(res, 200, { path: picked, settings: await writeSettings(settings) });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/scan') {
    const settings = await readSettings();
    const root = url.searchParams.get('root');
    const folders = root ? [path.resolve(expandHome(root))] : settings.folders;
    const tree = [];
    for (const folder of folders) {
      if (await exists(folder)) {
        tree.push(await scanFolder(folder, settings.scanDepth));
      }
    }
    sendJson(res, 200, { tree });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/artifacts') {
    const mediaPath = requireMediaPath(url);
    sendJson(res, 200, { artifacts: await listArtifacts(mediaPath) });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/speakers') {
    const mediaPath = requireMediaPath(url);
    sendJson(res, 200, await listSpeakers(mediaPath));
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/speakers') {
    const body = await readBody(req);
    const mediaPath = path.resolve(expandHome(body.mediaPath || ''));
    sendJson(res, 200, await renameSpeakers(mediaPath, body.speakers || []));
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/artifact') {
    const artifactPath = requirePath(url, 'path');
    sendJson(res, 200, { path: artifactPath, content: await readFile(artifactPath, 'utf8') });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/transcribe') {
    const body = await readBody(req);
    const job = await startTranscription(body);
    sendJson(res, 200, { job });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/jobs') {
    const mediaPath = url.searchParams.get('mediaPath')
      ? path.resolve(expandHome(url.searchParams.get('mediaPath')))
      : null;
    const jobsList = Array.from(jobs.values())
      .filter((job) => !mediaPath || job.mediaPath === mediaPath)
      .sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime());
    sendJson(res, 200, { jobs: jobsList.map(compactJob), job: jobsList[0] ? compactJob(jobsList[0]) : null });
    return;
  }

  if (req.method === 'GET' && url.pathname.startsWith('/api/jobs/')) {
    const id = decodeURIComponent(url.pathname.split('/').at(-1));
    const job = jobs.get(id);
    if (!job) {
      sendJson(res, 404, { error: 'Job not found' });
      return;
    }
    sendJson(res, 200, { job });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/check') {
    sendJson(res, 200, await checkEnvironment());
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/deploy-env') {
    sendJson(res, 200, { steps: await deployEnvironment() });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/install-skills') {
    const body = await readBody(req);
    sendJson(res, 200, { results: await installProjectSkills(body.targets || undefined) });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/download-models') {
    const body = await readBody(req);
    const job = await startModelDownload(body);
    sendJson(res, 200, { job });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/context') {
    const body = await readBody(req);
    sendJson(res, 200, { context: await buildAiContext(body.mediaPath, body.options || {}) });
    return;
  }

  sendJson(res, 404, { error: 'Not found' });
}

async function serveStatic(res, pathname) {
  const requested = pathname === '/' ? '/index.html' : pathname;
  const filePath = path.resolve(PUBLIC_DIR, `.${decodeURIComponent(requested)}`);
  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendJson(res, 403, { error: 'Forbidden' });
    return;
  }
  if (!(await exists(filePath))) {
    sendJson(res, 404, { error: 'Not found' });
    return;
  }
  const ext = path.extname(filePath).toLowerCase();
  res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
  createReadStream(filePath).pipe(res);
}

async function streamMedia(req, res, url) {
  const mediaPath = requireMediaPath(url);
  const mediaStat = await stat(mediaPath);
  const total = mediaStat.size;
  const range = req.headers.range;
  const ext = path.extname(mediaPath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  if (!range) {
    res.writeHead(200, {
      'Content-Length': total,
      'Content-Type': contentType,
      'Accept-Ranges': 'bytes'
    });
    createReadStream(mediaPath).pipe(res);
    return;
  }

  const [startRaw, endRaw] = range.replace(/bytes=/, '').split('-');
  const start = Number(startRaw);
  const end = endRaw ? Number(endRaw) : total - 1;
  if (Number.isNaN(start) || Number.isNaN(end) || start >= total) {
    res.writeHead(416, { 'Content-Range': `bytes */${total}` });
    res.end();
    return;
  }
  res.writeHead(206, {
    'Content-Range': `bytes ${start}-${end}/${total}`,
    'Accept-Ranges': 'bytes',
    'Content-Length': end - start + 1,
    'Content-Type': contentType
  });
  createReadStream(mediaPath, { start, end }).pipe(res);
}

async function downloadFile(res, url) {
  const filePath = requirePath(url, 'path');
  if (!(await exists(filePath))) {
    sendJson(res, 404, { error: 'File not found' });
    return;
  }
  const fileStat = await stat(filePath);
  if (!fileStat.isFile()) {
    sendJson(res, 400, { error: 'Path is not a file' });
    return;
  }
  const filename = path.basename(filePath).replace(/[^\w.\-() ]+/g, '_');
  const ext = path.extname(filePath).toLowerCase();
  res.writeHead(200, {
    'Content-Length': fileStat.size,
    'Content-Type': MIME_TYPES[ext] || 'application/octet-stream',
    'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(filename)}`
  });
  createReadStream(filePath).pipe(res);
}

async function scanFolder(folderPath, depth, currentDepth = 0) {
  let entries = [];
  try {
    entries = await readdir(folderPath, { withFileTypes: true });
  } catch {
    return { name: path.basename(folderPath) || folderPath, path: folderPath, folders: [], files: [], unreadable: true };
  }
  const folders = [];
  const files = [];

  for (const entry of entries) {
    if (GENERATED_FILENAMES.includes(entry.name) || entry.name === '.meeting-speakers.json') continue;
    const entryPath = path.join(folderPath, entry.name);
    if (entry.isDirectory()) {
      if (currentDepth < depth) {
        const child = await scanFolder(entryPath, depth, currentDepth + 1);
        folders.push(child);
      }
    } else if (entry.isFile() && isMediaFile(entryPath)) {
      try {
        const fileStat = await stat(entryPath);
        files.push({
          name: entry.name,
          path: entryPath,
          directory: folderPath,
          size: fileStat.size,
          modifiedAt: fileStat.mtime.toISOString(),
          kind: mediaKind(entryPath)
        });
      } catch {
        // Ignore files that disappear or cannot be read during a scan.
      }
    }
  }

  folders.sort((a, b) => a.name.localeCompare(b.name));
  files.sort((a, b) => a.name.localeCompare(b.name));
  return { name: path.basename(folderPath) || folderPath, path: folderPath, folders, files };
}

async function listArtifacts(mediaPath) {
  const artifacts = [];
  for (const dir of await artifactDirectories(mediaPath)) {
    const entries = await readdir(dir, { withFileTypes: true });
    const candidates = entries
      .filter((entry) => entry.isFile() && isGeneratedArtifact(entry.name))
      .map((entry) => path.join(dir, entry.name));
  for (const candidate of candidates) {
    const fileStat = await stat(candidate);
    artifacts.push({
      name: path.basename(candidate),
      path: candidate,
        directory: dir,
        location: dir === path.dirname(mediaPath) ? 'media' : 'tmp',
      size: fileStat.size,
      modifiedAt: fileStat.mtime.toISOString(),
      type: artifactType(candidate)
    });
  }
  }
  return artifacts.sort((a, b) => {
    if (a.location !== b.location) return a.location.localeCompare(b.location);
    return a.name.localeCompare(b.name);
  });
}

async function startTranscription(body) {
  const settings = await readSettings();
  const mediaPath = path.resolve(expandHome(body.mediaPath || ''));
  if (!(await exists(mediaPath)) || !isMediaFile(mediaPath)) {
    throw new Error('Media file does not exist or is not supported');
  }

  const speakerMode = body.speakerMode || settings.speakerMode;
  const args = [
    path.join(SKILL_DIR, 'run.py'),
    mediaPath,
    '--model',
    modelPath(settings),
    '--speaker-mode',
    speakerMode,
    '--output-dir',
    path.dirname(mediaPath),
    '--title',
    path.basename(mediaPath, path.extname(mediaPath))
  ];

  const language = body.recognitionLanguage || settings.recognitionLanguage;
  if (language && language !== 'auto') args.push('--language', language);
  if (speakerMode === 'diarize') {
    args.push(
      '--diarization-model',
      diarizationModelPath(),
      '--speaker-global-clustering'
    );
    if (body.speakerCount) args.push('--speaker-count', String(body.speakerCount));
  }

  const id = randomUUID();
  const job = {
    id,
    mediaPath,
    status: 'running',
    startedAt: new Date().toISOString(),
    endedAt: null,
    command: [pythonPath(), ...args],
    logs: []
  };
  jobs.set(id, job);

  const child = spawn(pythonPath(), args, { cwd: ROOT_DIR, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.on('data', (chunk) => pushLog(job, 'stdout', chunk));
  child.stderr.on('data', (chunk) => pushLog(job, 'stderr', chunk));
  child.on('error', (error) => {
    job.status = 'failed';
    job.endedAt = new Date().toISOString();
    pushLog(job, 'error', error.message);
  });
  child.on('close', (code) => {
    job.status = code === 0 ? 'completed' : 'failed';
    job.exitCode = code;
    job.endedAt = new Date().toISOString();
  });

  return compactJob(job);
}

async function startModelDownload(body) {
  const settings = await readSettings();
  const downloads = [];
  if (body.asr !== false) {
    downloads.push({
      repo: `mlx-community/${settings.asrModel}`,
      localDir: modelPath(settings)
    });
  }
  if (body.diarization) {
    downloads.push({
      repo: 'mlx-community/diar_sortformer_4spk-v1-fp16',
      localDir: diarizationModelPath()
    });
  }
  if (!downloads.length) throw new Error('No model selected for download');

  const id = randomUUID();
  const job = {
    id,
    mediaPath: null,
    status: 'running',
    startedAt: new Date().toISOString(),
    endedAt: null,
    command: ['huggingface-cli', 'download'],
    logs: []
  };
  jobs.set(id, job);
  runDownloadsSequentially(job, downloads);
  return compactJob(job);
}

async function runDownloadsSequentially(job, downloads) {
  for (const item of downloads) {
    pushLog(job, 'stdout', `Downloading ${item.repo}\n`);
    const code = await runDownload(job, item);
    if (code !== 0) {
      job.status = 'failed';
      job.exitCode = code;
      job.endedAt = new Date().toISOString();
      return;
    }
  }
  job.status = 'completed';
  job.exitCode = 0;
  job.endedAt = new Date().toISOString();
}

function runDownload(job, item) {
  return new Promise((resolve) => {
    const hfCommand = preferredHfCommand();
    job.command = [hfCommand, 'download', item.repo, '--local-dir', item.localDir];
    const child = spawn(hfCommand, ['download', item.repo, '--local-dir', item.localDir], {
      cwd: ROOT_DIR,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    child.stdout.on('data', (chunk) => pushLog(job, 'stdout', chunk));
    child.stderr.on('data', (chunk) => pushLog(job, 'stderr', chunk));
    child.on('error', (error) => {
      pushLog(job, 'error', error.message);
      resolve(127);
    });
    child.on('close', resolve);
  });
}

async function pickFolder() {
  if (process.platform === 'darwin') {
    const result = await runCommand('osascript', ['-e', 'POSIX path of (choose folder with prompt "选择会议媒体文件夹")']);
    return result.code === 0 ? result.stdout.trim().replace(/\/$/, '') : null;
  }
  if (process.platform === 'win32') {
    const script = [
      'Add-Type -AssemblyName System.Windows.Forms;',
      '$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;',
      '$dialog.Description = "Select meeting media folder";',
      'if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }'
    ].join(' ');
    const result = await runCommand('powershell.exe', ['-NoProfile', '-STA', '-Command', script]);
    return result.code === 0 ? result.stdout.trim() : null;
  }
  const zenity = await runCommand('zenity', ['--file-selection', '--directory', '--title=Select meeting media folder']);
  if (zenity.code === 0) return zenity.stdout.trim();
  const kdialog = await runCommand('kdialog', ['--getexistingdirectory', process.env.HOME || '.']);
  return kdialog.code === 0 ? kdialog.stdout.trim() : null;
}

function runCommand(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('close', (code) => resolve({ code, stdout, stderr }));
    child.on('error', (error) => resolve({ code: 127, stdout, stderr: error.message }));
  });
}

function preferredHfCommand() {
  const candidates = [
    path.join(SKILL_DIR, '.venv', 'bin', 'hf'),
    path.join(SKILL_DIR, '.venv', 'bin', 'huggingface-cli')
  ];
  for (const candidate of candidates) {
    if (syncExists(candidate)) return candidate;
  }
  return 'hf';
}

function syncExists(targetPath) {
  try {
    return Boolean(statSync(targetPath));
  } catch {
    return false;
  }
}

function pushLog(job, stream, chunk) {
  job.logs.push({
    stream,
    text: String(chunk),
    time: new Date().toISOString()
  });
  if (job.logs.length > 500) job.logs.shift();
}

async function buildAiContext(mediaPathInput, options) {
  const mediaPath = path.resolve(expandHome(mediaPathInput || ''));
  const artifacts = await listArtifacts(mediaPath);
  const contentParts = [];
  for (const artifact of artifacts) {
    if (!['transcript', 'subtitles_txt', 'summary', 'report'].includes(artifact.type)) continue;
    const content = await readFile(artifact.path, 'utf8');
    contentParts.push(`## ${artifact.name}\nPath: ${artifact.path}\n\n${content.trim()}`);
  }
  const targetLanguage = options.targetLanguage || 'zh';
  const translationTarget = options.translationTarget || 'en';
  return [
    '请使用 meeting-auto-summary skill 的输出继续处理这段会议媒体。',
    '',
    `媒体路径: ${mediaPath}`,
    `输出目录: ${(await artifactDirectories(mediaPath)).join(', ')}`,
    `目标总结语言: ${targetLanguage}`,
    `可选翻译目标: ${translationTarget}`,
    '',
    '请根据已有 transcript/subtitles 生成或更新 summary.md；如果需要正式报告，生成 report.md；如果需要翻译，保留原文件并创建带语言后缀的副本。',
    '',
    contentParts.join('\n\n')
  ].join('\n');
}

async function listSpeakers(mediaPath) {
  const artifacts = await listArtifacts(mediaPath);
  const dirs = Array.from(new Set(artifacts.map((artifact) => artifact.directory)));
  const ids = new Set();
  const maps = {};

  for (const artifact of artifacts) {
    if (!isTextArtifact(artifact)) continue;
    const content = await readFile(artifact.path, 'utf8');
    for (const match of content.matchAll(/\bSpeaker\s+\d+\b/g)) ids.add(match[0]);
  }

  for (const dir of dirs) {
    Object.assign(maps, await readSpeakerMap(dir));
  }

  const speakers = Array.from(ids)
    .sort(compareSpeakerId)
    .map((id) => ({ id, name: maps[id] || id }));

  for (const [id, name] of Object.entries(maps)) {
    if (!speakers.some((speaker) => speaker.id === id)) speakers.push({ id, name });
  }

  speakers.sort((a, b) => compareSpeakerId(a.id, b.id));
  return { speakers, directories: dirs };
}

async function renameSpeakers(mediaPath, speakers) {
  if (!(await exists(mediaPath)) || !isMediaFile(mediaPath)) {
    throw new Error('Media file does not exist or is not supported');
  }
  const artifacts = await listArtifacts(mediaPath);
  const dirs = Array.from(new Set(artifacts.map((artifact) => artifact.directory)));
  const previous = {};
  for (const dir of dirs) Object.assign(previous, await readSpeakerMap(dir));

  const next = {};
  for (const speaker of speakers) {
    if (!speaker.id) continue;
    const cleanName = String(speaker.name || speaker.id).trim() || speaker.id;
    next[speaker.id] = cleanName;
  }

  let changedFiles = 0;
  for (const artifact of artifacts) {
    if (!isTextArtifact(artifact)) continue;
    let content = await readFile(artifact.path, 'utf8');
    const original = content;
    for (const [id, newName] of Object.entries(next)) {
      const oldName = previous[id] || id;
      content = replaceSpeakerLabel(content, id, newName);
      if (oldName !== id) content = replaceSpeakerLabel(content, oldName, newName);
    }
    if (content !== original) {
      await writeFile(artifact.path, content, 'utf8');
      changedFiles += 1;
    }
  }

  for (const dir of dirs) {
    await writeSpeakerMap(dir, next);
  }
  return { speakers: Object.entries(next).map(([id, name]) => ({ id, name })), changedFiles };
}

async function artifactDirectories(mediaPath) {
  const mediaDir = path.dirname(mediaPath);
  const stem = path.basename(mediaPath, path.extname(mediaPath));
  const tmpDir = path.join(ROOT_DIR, 'tmp', stem);
  const candidates = [mediaDir, tmpDir];
  const dirs = [];
  for (const dir of candidates) {
    if (!dirs.includes(dir) && (await exists(dir))) dirs.push(dir);
  }
  return dirs;
}

async function readSpeakerMap(dir) {
  const filePath = path.join(dir, '.meeting-speakers.json');
  if (!(await exists(filePath))) return {};
  try {
    return JSON.parse(await readFile(filePath, 'utf8'));
  } catch {
    return {};
  }
}

async function writeSpeakerMap(dir, map) {
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, '.meeting-speakers.json'), `${JSON.stringify(map, null, 2)}\n`, 'utf8');
}

function replaceSpeakerLabel(content, from, to) {
  if (!from || from === to) return content;
  return content.replace(new RegExp(escapeRegExp(from), 'g'), to);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function isTextArtifact(artifact) {
  return ['transcript', 'subtitles_txt', 'subtitles_srt', 'summary', 'report'].includes(artifact.type);
}

function compareSpeakerId(a, b) {
  const aNumber = Number(String(a).match(/\d+/)?.[0] || Number.MAX_SAFE_INTEGER);
  const bNumber = Number(String(b).match(/\d+/)?.[0] || Number.MAX_SAFE_INTEGER);
  if (aNumber !== bNumber) return aNumber - bNumber;
  return String(a).localeCompare(String(b));
}

function isGeneratedArtifact(filename) {
  if (GENERATED_FILENAMES.includes(filename)) return true;
  return /^(transcript|subtitles|summary|report)-[a-z]{2,8}\.(md|srt|txt)$/i.test(filename);
}

function artifactType(filePath) {
  const name = path.basename(filePath);
  if (name.startsWith('transcript')) return 'transcript';
  if (name === 'subtitles.txt' || /^subtitles-[a-z]{2,8}\.txt$/i.test(name)) return 'subtitles_txt';
  if (name.startsWith('subtitles')) return 'subtitles_srt';
  if (name.startsWith('summary')) return 'summary';
  if (name.startsWith('report')) return 'report';
  if (name === 'audio.wav') return 'audio';
  return 'file';
}

function mediaKind(filePath) {
  return ['.mp4', '.mov', '.mkv', '.webm', '.avi'].includes(path.extname(filePath).toLowerCase()) ? 'video' : 'audio';
}

function modelVariants() {
  return [
    'Qwen3-ASR-0.6B-4bit',
    'Qwen3-ASR-0.6B-5bit',
    'Qwen3-ASR-0.6B-6bit',
    'Qwen3-ASR-0.6B-8bit',
    'Qwen3-ASR-0.6B-bf16',
    'Qwen3-ASR-1.7B-4bit',
    'Qwen3-ASR-1.7B-5bit',
    'Qwen3-ASR-1.7B-6bit',
    'Qwen3-ASR-1.7B-8bit',
    'Qwen3-ASR-1.7B-bf16'
  ];
}

async function readBody(req) {
  let raw = '';
  for await (const chunk of req) raw += chunk;
  if (!raw) return {};
  return JSON.parse(raw);
}

function sendJson(res, status, payload) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function requireMediaPath(url) {
  const mediaPath = requirePath(url, 'path');
  if (!isMediaFile(mediaPath)) throw new Error('Unsupported media path');
  return mediaPath;
}

function requirePath(url, name) {
  const value = url.searchParams.get(name);
  if (!value) throw new Error(`Missing ${name}`);
  return path.resolve(expandHome(value));
}

function compactJob(job) {
  return { ...job, logs: job.logs.slice(-80) };
}
