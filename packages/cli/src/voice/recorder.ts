/**
 * Microphone recorder using system arecord (Linux) or sox/rec (macOS).
 * Emits 'silence' when sustained silence is detected after speech.
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';

// RMS amplitude below this level is considered silence (0–32767 scale)
const SILENCE_THRESHOLD = 400;
// How long silence must persist (after speech) to auto-stop, in ms
const SILENCE_DURATION_MS = 1500;
// Minimum speech duration before silence detection kicks in, in ms
const MIN_SPEECH_MS = 300;

function rmsLevel(pcm: Buffer): number {
  if (pcm.length < 2) return 0;
  let sum = 0;
  const samples = Math.floor(pcm.length / 2);
  for (let i = 0; i < samples; i++) {
    const s = pcm.readInt16LE(i * 2);
    sum += s * s;
  }
  return Math.sqrt(sum / samples);
}

export class MicRecorder extends EventEmitter {
  private proc: ChildProcess | null = null;
  private chunks: Buffer[] = [];
  private _recording = false;
  private speechStartTime: number | null = null;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;

  start(): void {
    if (this._recording) return;

    this.chunks = [];
    this._recording = true;
    this.speechStartTime = null;
    this.silenceTimer = null;

    let cmd: string;
    let args: string[];

    if (process.platform === 'darwin') {
      // macOS: requires sox (`brew install sox`)
      cmd = 'rec';
      args = ['-q', '-r', '16000', '-c', '1', '-e', 'signed-integer', '-b', '16', '-t', 'raw', '-'];
    } else {
      // Linux: ALSA arecord
      cmd = 'arecord';
      args = ['-f', 'S16_LE', '-r', '16000', '-c', '1', '-t', 'raw', '-q', '-'];
    }

    this.proc = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'ignore'] });

    this.proc.stdout!.on('data', (chunk: Buffer) => {
      this.chunks.push(chunk);
      const rms = rmsLevel(chunk);

      if (rms > SILENCE_THRESHOLD) {
        // Speech detected — record start time, cancel pending silence timer
        if (!this.speechStartTime) {
          this.speechStartTime = Date.now();
        }
        if (this.silenceTimer) {
          clearTimeout(this.silenceTimer);
          this.silenceTimer = null;
        }
      } else if (this.speechStartTime) {
        // Silence after speech — start timer if we haven't yet
        const elapsed = Date.now() - this.speechStartTime;
        if (elapsed >= MIN_SPEECH_MS && !this.silenceTimer) {
          this.silenceTimer = setTimeout(() => {
            this.emit('silence');
          }, SILENCE_DURATION_MS);
        }
      }
    });

    this.proc.on('error', (err: Error) => {
      this._recording = false;
      this.emit('error', err);
    });

    this.proc.on('close', (code: number | null) => {
      if (code !== null && code !== 0 && code !== 143 /* SIGTERM */) {
        this.emit('error', new Error(`${cmd} exited with code ${code}`));
      }
    });
  }

  /**
   * Stop recording and return all captured PCM data as a single Buffer.
   */
  stop(): Buffer {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
    if (this.proc) {
      try { this.proc.kill('SIGTERM'); } catch { /* already dead */ }
      this.proc = null;
    }
    this._recording = false;
    return this.chunks.length > 0 ? Buffer.concat(this.chunks) : Buffer.alloc(0);
  }

  isRecording(): boolean {
    return this._recording;
  }
}
