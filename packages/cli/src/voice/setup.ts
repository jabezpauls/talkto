/**
 * Voice model setup: download whisper model and piper TTS binary/model.
 * Called by `talkto setup --voice`.
 */

import { existsSync, mkdirSync, createWriteStream, chmodSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';
import { spawnSync } from 'child_process';
import ora from 'ora';

// ── Path helpers ─────────────────────────────────────────────────────────────

export function getVoicePath(): string {
  return join(homedir(), '.talkto', 'voice');
}

export function getWhisperModelPath(): string {
  return join(getVoicePath(), 'whisper', 'ggml-tiny.en.bin');
}

export function getPiperPaths(): { binary: string; model: string; modelConfig: string } {
  const dir = join(getVoicePath(), 'piper');
  return {
    binary: join(dir, 'piper'),
    model: join(dir, 'en_US-lessac-medium.onnx'),
    modelConfig: join(dir, 'en_US-lessac-medium.onnx.json'),
  };
}

// ── Download URLs ─────────────────────────────────────────────────────────────

const WHISPER_MODEL_URL =
  'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin';

function getPiperArchiveUrl(): string {
  if (process.platform === 'darwin') {
    const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64';
    return `https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_macos_${arch}.tar.gz`;
  }
  const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64';
  return `https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_${arch}.tar.gz`;
}

const PIPER_VOICE_URL =
  'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx';
const PIPER_VOICE_CONFIG_URL =
  'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json';

// ── Status check ─────────────────────────────────────────────────────────────

export async function isVoiceReady(): Promise<{
  whisper: boolean;
  piper: boolean;
  espeak: boolean;
}> {
  const whisper = existsSync(getWhisperModelPath());
  const { binary, model } = getPiperPaths();
  const piper = existsSync(binary) && existsSync(model);
  const espeak =
    spawnSync('which', ['espeak-ng'], { encoding: 'utf-8' }).status === 0 ||
    spawnSync('which', ['espeak'], { encoding: 'utf-8' }).status === 0;
  return { whisper, piper, espeak };
}

// ── Download helpers ──────────────────────────────────────────────────────────

async function downloadFile(url: string, dest: string, label: string): Promise<void> {
  const spinner = ora(`Downloading ${label}...`).start();
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} for ${url}`);
    }

    const total = Number(response.headers.get('content-length') ?? 0);
    let received = 0;

    const out = createWriteStream(dest);

    // Stream with progress
    const reader = response.body!.getReader();
    const nodeStream = new Readable({
      async read() {
        const { done, value } = await reader.read();
        if (done) {
          this.push(null);
        } else {
          received += value.byteLength;
          if (total > 0) {
            const pct = Math.round((received / total) * 100);
            spinner.text = `Downloading ${label}... ${pct}%`;
          }
          this.push(Buffer.from(value));
        }
      },
    });

    await pipeline(nodeStream, out);
    spinner.succeed(`Downloaded ${label}`);
  } catch (err) {
    spinner.fail(`Failed to download ${label}: ${err}`);
    throw err;
  }
}

async function downloadPiperBinary(): Promise<void> {
  const piperDir = join(getVoicePath(), 'piper');
  mkdirSync(piperDir, { recursive: true });

  const archiveUrl = getPiperArchiveUrl();
  const archivePath = join(piperDir, 'piper.tar.gz');

  await downloadFile(archiveUrl, archivePath, 'piper binary');

  const spinner = ora('Extracting piper...').start();
  const result = spawnSync('tar', ['xzf', archivePath, '-C', piperDir, '--strip-components=1'], {
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    spinner.fail('Failed to extract piper archive');
    throw new Error('tar extraction failed');
  }

  // Make binary executable
  const { binary } = getPiperPaths();
  if (existsSync(binary)) {
    chmodSync(binary, 0o755);
  }

  // Clean up archive
  spawnSync('rm', ['-f', archivePath]);
  spinner.succeed('Piper binary ready');
}

// ── Main setup function ───────────────────────────────────────────────────────

export async function voiceSetup(): Promise<void> {
  console.log('');
  console.log('Setting up voice models...');
  console.log('');

  const status = await isVoiceReady();

  // 1. Whisper model (~75 MB)
  if (status.whisper) {
    console.log('  ✓ Whisper model already downloaded');
  } else {
    const whisperDir = join(getVoicePath(), 'whisper');
    mkdirSync(whisperDir, { recursive: true });
    await downloadFile(WHISPER_MODEL_URL, getWhisperModelPath(), 'whisper tiny.en model (~75 MB)');
  }

  // 2. Piper binary + voice model (~75 MB total)
  const { binary, model, modelConfig } = getPiperPaths();
  if (existsSync(binary)) {
    console.log('  ✓ Piper binary already downloaded');
  } else {
    await downloadPiperBinary();
  }

  if (existsSync(model)) {
    console.log('  ✓ Piper voice model already downloaded');
  } else {
    const piperDir = join(getVoicePath(), 'piper');
    mkdirSync(piperDir, { recursive: true });
    await downloadFile(PIPER_VOICE_URL, model, 'piper voice model (~60 MB)');
    await downloadFile(PIPER_VOICE_CONFIG_URL, modelConfig, 'piper voice config');
  }

  // Summary
  console.log('');
  console.log('  Voice setup complete!');
  if (!status.espeak && !existsSync(binary)) {
    console.log('  Note: No TTS engine found. Install espeak-ng as fallback:');
    console.log('    sudo apt install espeak-ng   (Debian/Ubuntu)');
    console.log('    brew install espeak           (macOS)');
  }
  console.log('');
  console.log('  Use voice mode with: talkto <path> --voice');
  console.log('');
}
