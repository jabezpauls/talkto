/**
 * Text-to-speech speaker.
 *
 * Engine priority:
 *   1. Piper TTS (neural, good quality) — requires prior download via `talkto setup --voice`
 *   2. espeak-ng / espeak (system TTS, robotic but zero setup)
 *
 * All playback is non-blocking: sentences are queued and spoken sequentially.
 */

import { existsSync } from 'fs';
import { spawn, ChildProcess, spawnSync } from 'child_process';
import { getPiperPaths } from './setup.js';

type TTSEngine = 'piper' | 'espeak-ng' | 'espeak' | 'none';

export class Speaker {
  private engine: TTSEngine = 'none';
  private piperBinary = '';
  private piperModel = '';
  private queue: string[] = [];
  private active: ChildProcess | null = null;
  private _speaking = false;

  /**
   * Detect the best available TTS engine.
   */
  async init(): Promise<void> {
    const { binary, model } = getPiperPaths();

    if (existsSync(binary) && existsSync(model)) {
      this.engine = 'piper';
      this.piperBinary = binary;
      this.piperModel = model;
      return;
    }

    if (spawnSync('which', ['espeak-ng'], { encoding: 'utf-8' }).status === 0) {
      this.engine = 'espeak-ng';
      return;
    }

    if (spawnSync('which', ['espeak'], { encoding: 'utf-8' }).status === 0) {
      this.engine = 'espeak';
      return;
    }

    // No TTS engine — voice mode will still work for input but output will be silent
    this.engine = 'none';
  }

  get engineName(): TTSEngine {
    return this.engine;
  }

  /**
   * Queue a piece of text for speaking. Non-blocking.
   */
  speak(text: string): void {
    const trimmed = text.trim();
    if (!trimmed || this.engine === 'none') return;
    this.queue.push(trimmed);
    if (!this._speaking) {
      void this._processQueue();
    }
  }

  /**
   * Stop current speech and clear pending queue.
   */
  stop(): void {
    this.queue = [];
    if (this.active) {
      try { this.active.kill('SIGTERM'); } catch { /* ignore */ }
      this.active = null;
    }
    this._speaking = false;
  }

  isSpeaking(): boolean {
    return this._speaking;
  }

  private async _processQueue(): Promise<void> {
    if (this.queue.length === 0) {
      this._speaking = false;
      return;
    }
    this._speaking = true;
    const text = this.queue.shift()!;

    await this._speakOne(text);
    await this._processQueue();
  }

  private _speakOne(text: string): Promise<void> {
    return new Promise((resolve) => {
      let proc: ChildProcess;

      if (this.engine === 'piper') {
        // piper reads from stdin, emits raw PCM on stdout; pipe to aplay
        const aplay = spawn('aplay', ['-r', '22050', '-f', 'S16_LE', '-c', '1', '-q'], {
          stdio: ['pipe', 'ignore', 'ignore'],
        });

        proc = spawn(
          this.piperBinary,
          ['--model', this.piperModel, '--output-raw', '--quiet'],
          { stdio: ['pipe', 'pipe', 'ignore'] }
        );

        proc.stdout!.pipe(aplay.stdin!);
        proc.stdin!.write(text);
        proc.stdin!.end();

        this.active = proc;

        proc.on('close', () => {
          try { aplay.stdin?.destroy(); } catch { /* ignore */ }
          resolve();
        });
        aplay.on('close', () => { /* aplay finishes after piper */ });

      } else {
        // espeak-ng / espeak — accepts text directly
        const cmd = this.engine as 'espeak-ng' | 'espeak';
        proc = spawn(cmd, [text], { stdio: ['ignore', 'ignore', 'ignore'] });
        this.active = proc;
        proc.on('close', resolve);
        proc.on('error', resolve);  // if espeak not found, skip silently
      }
    });
  }
}
