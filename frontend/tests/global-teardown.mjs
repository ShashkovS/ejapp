export default async function globalTeardown() {
  const procs = global.__E2E_PROCS__;
  if (!procs) return;
  for (const p of [procs.preview, procs.backend]) {
    try {
      p && p.kill('SIGTERM');
    } catch {}
  }
}
