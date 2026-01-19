import { spawn, ChildProcess } from 'child_process';
import { createInterface, Interface } from 'readline';
import { EventEmitter } from 'events';
import { join } from 'path';
import { existsSync } from 'fs';
import { randomUUID } from 'crypto';
import { getEnginePath } from '../utils/paths.js';

interface PendingRequest {
  resolve: (response: unknown) => void;
  reject: (error: Error) => void;
  timeout: NodeJS.Timeout;
}

interface EngineResponse {
  id: string;
  status: 'success' | 'error' | 'streaming';
  data?: unknown;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export class EngineBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private readline: Interface | null = null;
  private pending: Map<string, PendingRequest> = new Map();
  private enginePath: string;
  private ready: boolean = false;

  constructor(enginePath?: string) {
    super();
    this.enginePath = enginePath || getEnginePath();
  }

  async start(): Promise<void> {
    // Find Python executable
    const venvPython = join(this.enginePath, '.venv', 'bin', 'python');
    const systemPython = 'python3';
    const pythonExe = existsSync(venvPython) ? venvPython : systemPython;

    const mainScript = join(this.enginePath, 'main.py');

    if (!existsSync(mainScript)) {
      throw new Error(`Engine not found at ${mainScript}`);
    }

    this.process = spawn(pythonExe, [mainScript], {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: this.enginePath,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
    });

    this.readline = createInterface({
      input: this.process.stdout!,
      terminal: false,
    });

    this.readline.on('line', (line) => {
      try {
        const response = JSON.parse(line) as EngineResponse;
        this.handleResponse(response);
      } catch {
        this.emit('log', `[engine] ${line}`);
      }
    });

    this.process.stderr?.on('data', (data) => {
      this.emit('log', `[engine:stderr] ${data.toString().trim()}`);
    });

    this.process.on('exit', (code) => {
      this.emit('exit', code);
      this.rejectAllPending(new Error(`Engine exited with code ${code}`));
    });

    this.process.on('error', (error) => {
      this.emit('error', error);
      this.rejectAllPending(error);
    });

    // Wait for ready signal
    await this.waitForReady();
  }

  private async waitForReady(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Engine startup timeout'));
      }, 30000);

      const handler = (response: EngineResponse) => {
        if (response.id === 'ready') {
          clearTimeout(timeout);
          this.ready = true;
          this.removeListener('response', handler);
          resolve();
        }
      };

      this.on('response', handler);
    });
  }

  async send<T>(request: Record<string, unknown>): Promise<T> {
    if (!this.ready) {
      throw new Error('Engine not ready');
    }

    return new Promise((resolve, reject) => {
      const id = randomUUID();
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Request timeout (60s)'));
      }, 60000);

      this.pending.set(id, { resolve: resolve as (r: unknown) => void, reject, timeout });

      const message = JSON.stringify({
        ...request,
        id,
        timestamp: new Date().toISOString(),
      }) + '\n';

      this.process?.stdin?.write(message);
    });
  }

  async sendStreaming(
    request: Record<string, unknown>,
    onChunk: (chunk: unknown) => void
  ): Promise<void> {
    if (!this.ready) {
      throw new Error('Engine not ready');
    }

    const id = randomUUID();

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.removeListener('response', handler);
        reject(new Error('Streaming timeout (300s)'));
      }, 300000);

      const handler = (response: EngineResponse) => {
        if (response.id !== id) return;

        if (response.status === 'streaming') {
          onChunk(response.data);
          if ((response.data as { type?: string })?.type === 'done') {
            clearTimeout(timeout);
            this.removeListener('response', handler);
            resolve();
          }
        } else if (response.status === 'error') {
          clearTimeout(timeout);
          this.removeListener('response', handler);
          reject(new Error(response.error?.message || 'Unknown error'));
        } else if (response.status === 'success') {
          // Non-streaming response to streaming request
          clearTimeout(timeout);
          this.removeListener('response', handler);
          onChunk({ type: 'done', data: response.data });
          resolve();
        }
      };

      this.on('response', handler);

      const message = JSON.stringify({
        ...request,
        id,
        timestamp: new Date().toISOString(),
      }) + '\n';

      this.process?.stdin?.write(message);
    });
  }

  private handleResponse(response: EngineResponse): void {
    this.emit('response', response);

    const pending = this.pending.get(response.id);
    if (pending && response.status !== 'streaming') {
      clearTimeout(pending.timeout);
      this.pending.delete(response.id);

      if (response.status === 'error') {
        pending.reject(new Error(response.error?.message || 'Unknown error'));
      } else {
        pending.resolve(response.data);
      }
    }
  }

  private rejectAllPending(error: Error): void {
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timeout);
      pending.reject(error);
    }
    this.pending.clear();
  }

  async stop(): Promise<void> {
    this.ready = false;
    this.process?.kill();
    this.readline?.close();
    this.rejectAllPending(new Error('Engine stopped'));
  }
}
