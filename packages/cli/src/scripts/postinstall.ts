/**
 * Postinstall script: set up the Python engine environment.
 * Runs automatically via npm postinstall hook.
 */

import { spawnSync } from 'child_process';
import { existsSync } from 'fs';
import { join } from 'path';
import { getEnginePath } from '../utils/paths.js';

function run(cmd: string, args: string[], cwd: string): boolean {
  const result = spawnSync(cmd, args, { cwd, stdio: 'inherit' });
  return result.status === 0;
}

function capture(cmd: string, args: string[]): string | null {
  const result = spawnSync(cmd, args, { encoding: 'utf-8' });
  if (result.status !== 0 || result.error) return null;
  return (result.stdout || '').trim();
}

async function setup(): Promise<void> {
  const enginePath = getEnginePath();

  console.log('[talkto] Setting up Python engine...');

  // Check Python >= 3.11
  const versionOutput = capture('python3', ['--version']);
  if (!versionOutput) {
    console.error('[talkto] Error: python3 not found. Install Python 3.11+ and try again.');
    process.exit(1);
  }
  const match = versionOutput.match(/Python (\d+)\.(\d+)/);
  if (
    !match ||
    parseInt(match[1]) < 3 ||
    (parseInt(match[1]) === 3 && parseInt(match[2]) < 11)
  ) {
    console.error('[talkto] Error: Python 3.11+ is required.');
    console.error(`[talkto] Found: ${versionOutput}`);
    process.exit(1);
  }
  console.log(`[talkto] Found ${versionOutput}`);

  // Create virtual environment
  const venvPath = join(enginePath, '.venv');
  if (!existsSync(venvPath)) {
    console.log('[talkto] Creating virtual environment...');
    if (!run('python3', ['-m', 'venv', '.venv'], enginePath)) {
      console.error('[talkto] Failed to create virtual environment.');
      process.exit(1);
    }
  } else {
    console.log('[talkto] Virtual environment already exists, skipping creation.');
  }

  // Install engine dependencies
  console.log('[talkto] Installing engine dependencies (this may take a minute)...');
  const pip = join(venvPath, 'bin', 'pip');
  if (!run(pip, ['install', '-e', '.'], enginePath)) {
    console.error('[talkto] Failed to install engine dependencies.');
    console.error('[talkto] Retry manually:');
    console.error(`[talkto]   cd "${enginePath}" && .venv/bin/pip install -e .`);
    process.exit(1);
  }

  console.log('[talkto] Engine setup complete!');
  console.log('[talkto] To use OpenAI/Gemini models, run:');
  console.log(`[talkto]   "${pip}" install openai`);
}

setup();
