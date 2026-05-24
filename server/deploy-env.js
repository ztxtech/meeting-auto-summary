import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { exists, pythonPath, SKILL_DIR } from './shared.js';

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
    child.on('close', (code) => resolve({ code, stdout, stderr, command: [command, ...args].join(' ') }));
    child.on('error', (error) => resolve({ code: 127, stdout, stderr: error.message, command: [command, ...args].join(' ') }));
  });
}

export async function deployEnvironment() {
  const steps = [];
  await mkdir(SKILL_DIR, { recursive: true });

  if (!(await exists(pythonPath()))) {
    const venv = await run('python3', ['-m', 'venv', path.join(SKILL_DIR, '.venv')]);
    steps.push({
      label: 'Create skill virtual environment',
      ok: venv.code === 0,
      detail: venv.stderr || venv.stdout || venv.command
    });
    if (venv.code !== 0) return steps;
  } else {
    steps.push({ label: 'Create skill virtual environment', ok: true, detail: `${pythonPath()} already exists` });
  }

  const pip = await run(pythonPath(), ['-m', 'pip', 'install', '-U', 'pip']);
  steps.push({ label: 'Upgrade pip', ok: pip.code === 0, detail: pip.stderr || pip.stdout });
  if (pip.code !== 0) return steps;

  const deps = await run(pythonPath(), ['-m', 'pip', 'install', '-U', 'mlx-audio', 'huggingface_hub']);
  steps.push({ label: 'Install Python dependencies', ok: deps.code === 0, detail: deps.stderr || deps.stdout });
  return steps;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const steps = await deployEnvironment();
  for (const step of steps) {
    console.log(`${step.ok ? 'OK ' : 'NO '} ${step.label}`);
    if (step.detail) console.log(step.detail.trim());
  }
}
