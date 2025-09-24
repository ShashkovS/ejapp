import { spawn } from 'node:child_process';
import { setTimeout as wait } from 'node:timers/promises';
import http from 'node:http';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function spawnProc(cmd, args, opts) {
  const child = spawn(cmd, args, { stdio: 'inherit', ...opts });
  child.on('exit', (code) => {
    if (code) console.error(`${cmd} exited with code ${code}`);
  });
  return child;
}

async function waitFor(url, timeoutMs = 90_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(url, (res) => (res.statusCode && res.statusCode < 500 ? resolve() : reject(new Error(String(res.statusCode)))));
        req.on('error', reject);
        req.end();
      });
      return;
    } catch {
      /* retry */
    }
    await wait(150);
  }
  throw new Error(`Timeout waiting for ${url}`);
}

export default async function globalSetup() {
  const repoRoot = path.resolve(__dirname, '..', '..');

  // 1) backend (свежая БД, порт 18100)
  const backend = spawnProc(process.env.PYTHON || 'python', ['-m', 'uvicorn', 'backend.main:app', '--port', '18100', '--host', '127.0.0.1'], {
    cwd: repoRoot,
    env: { ...process.env, E2E: '1', PYTHONPATH: '.' },
  });
  await waitFor('http://127.0.0.1:18100/healthz');

  // 2) vite preview (порт 63343)
  const preview = spawnProc(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'preview:e2e'], {
    cwd: path.resolve(repoRoot, 'frontend'),
    env: process.env,
  });
  await waitFor('http://localhost:63343/');

  global.__E2E_PROCS__ = { backend, preview };
}
