import { cp, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { ROOT_DIR, SKILL_DIR } from './shared.js';

export const INSTALL_TARGETS = {
  codex: path.join(ROOT_DIR, '.agents', 'skills', 'meeting-auto-summary'),
  claude: path.join(ROOT_DIR, '.claude', 'skills', 'meeting-auto-summary'),
  opencode: path.join(ROOT_DIR, '.opencode', 'skill', 'meeting-auto-summary'),
  openclaw: path.join(ROOT_DIR, '.openclaw', 'skills', 'meeting-auto-summary')
};

export async function installProjectSkills(targets = Object.keys(INSTALL_TARGETS)) {
  const results = [];
  for (const target of targets) {
    const destination = INSTALL_TARGETS[target];
    if (!destination) {
      results.push({ target, ok: false, detail: 'Unknown target' });
      continue;
    }
    await mkdir(path.dirname(destination), { recursive: true });
    await rm(destination, { recursive: true, force: true });
    await cp(SKILL_DIR, destination, {
      recursive: true,
      filter: (source) => {
        const rel = path.relative(SKILL_DIR, source);
        if (!rel) return true;
        const first = rel.split(path.sep)[0];
        return !['.venv', 'model', 'tmp', '__pycache__'].includes(first) && !rel.endsWith('__pycache__');
      }
    });
    results.push({ target, ok: true, detail: destination });
  }
  return results;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const targets = process.argv.slice(2);
  const results = await installProjectSkills(targets.length ? targets : undefined);
  for (const result of results) {
    console.log(`${result.ok ? 'OK ' : 'NO '} ${result.target}: ${result.detail}`);
  }
}
