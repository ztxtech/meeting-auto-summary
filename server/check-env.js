import { spawn } from 'node:child_process';
import { stat } from 'node:fs/promises';
import { campplusModelPath, diarizationModelPath, exists, modelPath, pythonPath, readSettings, SKILL_DIR } from './shared.js';

function run(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'], ...options });
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

async function dirOk(targetPath) {
  try {
    return (await stat(targetPath)).isDirectory();
  } catch {
    return false;
  }
}

export async function checkEnvironment() {
  const settings = await readSettings();
  const checks = [];

  const py = pythonPath();
  checks.push({
    id: 'venv',
    label: 'Python virtual environment',
    ok: await exists(py),
    detail: py
  });

  const ffmpeg = await run('ffmpeg', ['-version']);
  checks.push({
    id: 'ffmpeg',
    label: 'ffmpeg',
    ok: ffmpeg.code === 0,
    detail: ffmpeg.code === 0 ? ffmpeg.stdout.split('\n')[0] : 'ffmpeg is not available in PATH'
  });

  const hfBin = await preferredHfCommand();
  const hf = await run(hfBin, ['--help']);
  checks.push({
    id: 'huggingface',
    label: 'Hugging Face CLI',
    ok: hf.code === 0,
    detail: hf.code === 0 ? `${hfBin} is available` : 'Install huggingface_hub in the skill venv'
  });

  if (await exists(py)) {
    const runner = await run(py, [pathJoin(SKILL_DIR, 'run.py'), '--help']);
    checks.push({
      id: 'runner',
      label: 'Skill runner',
      ok: runner.code === 0,
      detail: runner.code === 0 ? 'run.py is available' : runner.stderr || runner.stdout
    });

    const mlx = await run(py, ['-c', 'import mlx_audio; print("mlx_audio ok")']);
    checks.push({
      id: 'mlx_audio',
      label: 'mlx-audio',
      ok: mlx.code === 0,
      detail: mlx.code === 0 ? 'mlx_audio import succeeded' : mlx.stderr || mlx.stdout
    });

    const campplusDeps = await run(py, ['-c', 'import funasr, torch; print("campplus deps ok")']);
    checks.push({
      id: 'campplus_deps',
      label: 'CAMPPlus dependencies',
      ok: campplusDeps.code === 0,
      detail: campplusDeps.code === 0
        ? 'funasr and torch import succeeded'
        : 'Optional: install funasr torch torchaudio to enable CAMPPlus speaker embeddings'
    });
  }

  checks.push({
    id: 'asr_model',
    label: 'ASR model',
    ok: await dirOk(modelPath(settings)),
    detail: modelPath(settings)
  });

  checks.push({
    id: 'diarization_model',
    label: 'Speaker diarization model',
    ok: await dirOk(diarizationModelPath()),
    detail: diarizationModelPath()
  });

  checks.push({
    id: 'campplus_model',
    label: 'CAMPPlus speaker model',
    ok: await dirOk(campplusModelPath()),
    detail: campplusModelPath()
  });

  return { checks, settings };
}

async function preferredHfCommand() {
  const venvHf = pathJoin(SKILL_DIR, '.venv', 'bin', 'hf');
  if (await exists(venvHf)) return venvHf;
  const venvLegacy = pathJoin(SKILL_DIR, '.venv', 'bin', 'huggingface-cli');
  if (await exists(venvLegacy)) return venvLegacy;
  return 'hf';
}

function pathJoin(...parts) {
  return parts.join('/');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const result = await checkEnvironment();
  for (const check of result.checks) {
    console.log(`${check.ok ? 'OK ' : 'NO '} ${check.label}: ${check.detail}`);
  }
}
