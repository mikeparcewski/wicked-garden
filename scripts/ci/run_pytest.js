#!/usr/bin/env node
// Cross-platform pytest runner — tries each launcher in order, stops at the
// first one that has pytest importable, exits with pytest's own code.
// Avoids the ||  re-run problem: we probe for pytest before running it, so
// we never accidentally run the suite twice under different interpreters.
import { spawnSync } from 'child_process';
import { platform } from 'process';

// Each entry is [executable, ...prefixArgs] so 'py -3' spawns correctly.
const launchers = platform === 'win32'
  ? [['py', '-3'], ['python'], ['python3']]
  : [['python3'], ['python']];

for (const [cmd, ...prefix] of launchers) {
  const probe = spawnSync(cmd, [...prefix, '-c', 'import pytest'], { encoding: 'utf8' });
  if (probe.status !== 0 || probe.error) continue;
  const run = spawnSync(cmd, [...prefix, '-m', 'pytest', 'tests/', '-q'], { stdio: 'inherit' });
  process.exit(run.status ?? 1);
}
process.stderr.write('No Python with pytest found. Run: pip install pytest\n');
process.exit(1);
