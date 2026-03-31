/**
 * Whisper ASR transcriber.
 * Uses @fugood/whisper.node (native binding for whisper.cpp) to transcribe
 * PCM audio buffers to text locally with no API calls.
 */

import { existsSync } from 'fs';
import { getWhisperModelPath } from './setup.js';

// Type stubs for @fugood/whisper.node — filled in at runtime via dynamic import
interface WhisperContext {
  transcribeData(
    audio: ArrayBuffer,
    options?: { language?: string; translate?: boolean }
  ): Promise<string>;
  free?(): void;
}

export class Transcriber {
  private ctx: WhisperContext | null = null;
  private readonly modelPath: string;

  constructor(modelPath?: string) {
    this.modelPath = modelPath ?? getWhisperModelPath();
  }

  /**
   * Load the whisper model. Call once before transcribing.
   * Takes ~0.5–1s; amortized across all subsequent transcriptions.
   */
  async init(): Promise<void> {
    if (!existsSync(this.modelPath)) {
      throw new Error(
        `Whisper model not found at ${this.modelPath}.\n` +
          'Run "talkto setup --voice" to download it.'
      );
    }

    let initWhisper: ((opts: { model: string; useGpu?: boolean }) => Promise<WhisperContext>) | null =
      null;

    try {
      // Dynamic import so the package is only loaded in voice mode
      const mod = await import('@fugood/whisper.node');
      initWhisper = (mod as { initWhisper?: typeof initWhisper }).initWhisper
        ?? (mod as { default?: { initWhisper?: typeof initWhisper } }).default?.initWhisper
        ?? null;
    } catch (err) {
      throw new Error(
        `Could not load @fugood/whisper.node: ${err}\n` +
          'Make sure it is installed: npm install @fugood/whisper.node'
      );
    }

    if (!initWhisper) {
      throw new Error('initWhisper not exported by @fugood/whisper.node — unexpected package shape');
    }

    this.ctx = await initWhisper({ model: this.modelPath, useGpu: false });
  }

  /**
   * Transcribe raw 16-bit signed integer PCM audio (16 kHz, mono) to text.
   * @param pcm  Buffer of Int16LE samples
   * @returns    Trimmed transcription string, or '' if nothing detected
   */
  async transcribe(pcm: Buffer): Promise<string> {
    if (!this.ctx) {
      throw new Error('Transcriber not initialised. Call init() first.');
    }
    if (pcm.length < 2) return '';

    // Convert Int16LE → Float32 (whisper.cpp expects float32 internally;
    // some bindings accept Int16 directly, but Float32 is universally safe)
    const samples = Math.floor(pcm.length / 2);
    const float32 = new Float32Array(samples);
    for (let i = 0; i < samples; i++) {
      float32[i] = pcm.readInt16LE(i * 2) / 32768.0;
    }

    const raw = await this.ctx.transcribeData(float32.buffer, { language: 'en' });

    // whisper.cpp often prefixes output with whitespace or '[BLANK_AUDIO]'
    const text = raw
      .replace(/\[BLANK_AUDIO\]/gi, '')
      .replace(/\(.*?\)/g, '')   // strip parenthetical artifacts
      .trim();

    return text;
  }

  dispose(): void {
    if (this.ctx?.free) {
      this.ctx.free();
    }
    this.ctx = null;
  }
}
