/**
 * VoiceManager — orchestrates microphone recording, Whisper transcription,
 * and TTS playback for the talkto voice mode.
 *
 * Usage in the chat loop:
 *   const voice = new VoiceManager();
 *   await voice.init();
 *   const text = await voice.listen();   // blocks until user finishes speaking
 *   // send text through handleQuery ...
 *   // Inside handleQuery's token callback:
 *   voice.feedToken(token);
 *   // After stream ends:
 *   voice.flushSpeech();
 */

import chalk from 'chalk';
import { MicRecorder } from './recorder.js';
import { Transcriber } from './transcriber.js';
import { Speaker } from './speaker.js';

// Sentence-boundary regex: split after '. ', '! ', '? ', or newline
const SENTENCE_END = /([.!?])\s+|[\n]/;

export class VoiceManager {
  private recorder = new MicRecorder();
  private transcriber: Transcriber;
  private speaker = new Speaker();
  private sentenceBuffer = '';
  private initialised = false;

  constructor(whisperModelPath?: string) {
    this.transcriber = new Transcriber(whisperModelPath);
  }

  // ── Lifecycle ───────────────────────────────────────────────────────────────

  async init(): Promise<void> {
    await this.transcriber.init();
    await this.speaker.init();
    this.initialised = true;

    const eng = this.speaker.engineName;
    const ttsNote = eng === 'none'
      ? chalk.yellow(' (no TTS engine found — responses will be text only)')
      : chalk.gray(` (TTS: ${eng})`);
    process.stderr.write(chalk.gray('[voice] Whisper model loaded') + ttsNote + '\n');
  }

  get isInitialised(): boolean {
    return this.initialised;
  }

  dispose(): void {
    this.recorder.stop();
    this.speaker.stop();
    this.transcriber.dispose();
    this.initialised = false;
  }

  // ── Voice input ─────────────────────────────────────────────────────────────

  /**
   * Wait for the user to press Space, record until silence or Space again,
   * transcribe, and return the text.  Returns '' if nothing was captured,
   * or '__quit__' if the user pressed Q.
   */
  async listen(): Promise<string> {
    // Stop any ongoing TTS so it does not bleed into the mic
    this.speaker.stop();

    // 1. Wait for Space keypress
    process.stdout.write(chalk.yellow('\n  [mic] Press SPACE to talk, Q to quit\n'));
    const key = await this._waitForKey([' ', 'q', 'Q', '\u0003']);
    if (key === 'q' || key === 'Q' || key === '\u0003') {
      return '__quit__';
    }

    // 2. Start recording
    process.stdout.write(chalk.red('  [mic] Recording... (press SPACE to stop)\n'));

    return new Promise<string>((resolve) => {
      let stopped = false;

      const doStop = async () => {
        if (stopped) return;
        stopped = true;
        const pcm = this.recorder.stop();

        if (pcm.length < 3200) {
          // Less than 0.1 s of audio — probably accidental press
          process.stdout.write(chalk.gray('  [mic] Too short, try again\n'));
          resolve('');
          return;
        }

        process.stdout.write(chalk.gray('  [mic] Transcribing...\n'));
        try {
          const text = await this.transcriber.transcribe(pcm);
          resolve(text);
        } catch (err) {
          process.stderr.write(chalk.red(`  [voice] Transcription error: ${err}\n`));
          resolve('');
        }
      };

      // Auto-stop on silence
      this.recorder.once('silence', doStop);
      this.recorder.once('error', (err: Error) => {
        process.stderr.write(chalk.red(`  [voice] Recorder error: ${err.message}\n`));
        resolve('');
      });

      this.recorder.start();

      // Allow Space (or Q) to stop manually
      this._waitForKey([' ', 'q', 'Q', '\u0003']).then((k) => {
        if (k === 'q' || k === 'Q' || k === '\u0003') {
          this.recorder.stop();
          resolve('__quit__');
          return;
        }
        doStop();
      });
    });
  }

  // ── Voice output ────────────────────────────────────────────────────────────

  /**
   * Feed a streaming token into the TTS sentence buffer.
   * When a sentence boundary is detected the sentence is spoken.
   */
  feedToken(token: string): void {
    this.sentenceBuffer += token;
    this._drainSentences(false);
  }

  /**
   * Speak any remaining text in the buffer (call after the stream ends).
   */
  flushSpeech(): void {
    this._drainSentences(true);
  }

  private _drainSentences(flush: boolean): void {
    let buf = this.sentenceBuffer;

    if (flush) {
      if (buf.trim()) {
        this.speaker.speak(buf);
      }
      this.sentenceBuffer = '';
      return;
    }

    // Drain complete sentences
    let match: RegExpExecArray | null;
    while ((match = SENTENCE_END.exec(buf)) !== null) {
      const end = match.index + match[0].length;
      const sentence = buf.slice(0, end).trim();
      buf = buf.slice(end);
      if (sentence) {
        this.speaker.speak(sentence);
      }
    }

    // Also flush if the buffer is growing large (handles run-on responses)
    if (buf.length > 300) {
      this.speaker.speak(buf.trim());
      buf = '';
    }

    this.sentenceBuffer = buf;
  }

  // ── Utilities ───────────────────────────────────────────────────────────────

  /**
   * Wait for one of the specified keys in raw terminal mode.
   */
  private _waitForKey(keys: string[]): Promise<string> {
    return new Promise((resolve) => {
      const cleanup = (key: string) => {
        process.stdin.removeListener('data', onData);
        process.stdin.setRawMode(false);
        process.stdin.pause();
        resolve(key);
      };

      const onData = (data: Buffer | string) => {
        const ch = Buffer.isBuffer(data) ? data.toString('utf-8') : data;
        for (const k of keys) {
          if (ch === k || ch.startsWith(k)) {
            cleanup(k);
            return;
          }
        }
      };

      process.stdin.setRawMode(true);
      process.stdin.resume();
      process.stdin.on('data', onData);
    });
  }

  stop(): void {
    this.recorder.stop();
    this.speaker.stop();
  }
}
