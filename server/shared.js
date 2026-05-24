import { access, constants, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const SKILL_DIR = path.join(ROOT_DIR, 'skills', 'meeting-auto-summary');
export const LOCAL_STATE_DIR = path.join(ROOT_DIR, '.meeting-auto-summary');
export const SETTINGS_PATH = path.join(LOCAL_STATE_DIR, 'settings.json');
export const LANGUAGE_CONFIG_PATH = path.join(ROOT_DIR, 'config', 'languages.json');

export const MEDIA_EXTENSIONS = new Set([
  '.wav',
  '.mp3',
  '.m4a',
  '.flac',
  '.aac',
  '.ogg',
  '.mp4',
  '.mov',
  '.mkv',
  '.webm',
  '.avi'
]);

export const GENERATED_FILENAMES = [
  'audio.wav',
  'transcript.md',
  'subtitles.srt',
  'subtitles.txt',
  'summary.md',
  'report.md'
];

export async function supportedLanguages() {
  try {
    return JSON.parse(await readFile(LANGUAGE_CONFIG_PATH, 'utf8'));
  } catch {
    return [
      { code: 'zh', label: '中文', asr: true, summary: true, translation: true },
      { code: 'en', label: 'English', asr: true, summary: true, translation: true }
    ];
  }
}

const DEFAULT_SETTINGS = {
  folders: [],
  recognitionLanguage: 'auto',
  outputLanguage: 'zh',
  translationTarget: 'en',
  speakerMode: 'diarize',
  asrModel: 'Qwen3-ASR-0.6B-6bit',
  installTargets: ['codex', 'claude', 'opencode'],
  scanDepth: 12
};

export async function exists(targetPath) {
  try {
    await access(targetPath, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

export async function readSettings() {
  await mkdir(LOCAL_STATE_DIR, { recursive: true });
  if (!(await exists(SETTINGS_PATH))) {
    await writeSettings(DEFAULT_SETTINGS);
    return { ...DEFAULT_SETTINGS };
  }

  const raw = await readFile(SETTINGS_PATH, 'utf8');
  const settings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  if (!settings.scanDepth || settings.scanDepth < DEFAULT_SETTINGS.scanDepth) {
    settings.scanDepth = DEFAULT_SETTINGS.scanDepth;
  }
  return settings;
}

export async function writeSettings(settings) {
  await mkdir(LOCAL_STATE_DIR, { recursive: true });
  const clean = {
    ...DEFAULT_SETTINGS,
    ...settings,
    folders: Array.from(new Set((settings.folders || []).map((folder) => path.resolve(expandHome(folder)))))
  };
  await writeFile(SETTINGS_PATH, `${JSON.stringify(clean, null, 2)}\n`, 'utf8');
  return clean;
}

export function expandHome(inputPath) {
  if (!inputPath || typeof inputPath !== 'string') return inputPath;
  if (inputPath === '~') return process.env.HOME || inputPath;
  if (inputPath.startsWith('~/')) return path.join(process.env.HOME || '', inputPath.slice(2));
  return inputPath;
}

export function isMediaFile(filePath) {
  return MEDIA_EXTENSIONS.has(path.extname(filePath).toLowerCase());
}

export function modelPath(settings) {
  return path.join(SKILL_DIR, 'model', settings.asrModel);
}

export function diarizationModelPath() {
  return path.join(SKILL_DIR, 'model', 'diar_sortformer_4spk-v1-fp16');
}

export function pythonPath() {
  return path.join(SKILL_DIR, '.venv', 'bin', 'python');
}
