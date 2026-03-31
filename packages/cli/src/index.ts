import { Command } from 'commander';
import { resolve } from 'path';
import { existsSync, mkdirSync } from 'fs';
import { spawnSync } from 'child_process';
import chalk from 'chalk';
import ora from 'ora';
import * as readline from 'readline';
import { EngineBridge } from './engine/bridge.js';
import { getDefaultStoragePath, getIndexesPath } from './utils/paths.js';
import { loadGlobalConfig } from './config.js';
import type { IndexResponse, QueryResponse, StreamChunk } from './types/index.js';

// Load global config for defaults
const globalConfig = loadGlobalConfig();

// Constants used by setup command — must be declared before program.parse()
const OLLAMA_URL = 'http://localhost:11434';
const REQUIRED_EMBED_MODEL = 'nomic-embed-text';
const SUGGESTED_CHAT_MODEL = 'llama3.1:8b';

const program = new Command();

program
  .name('talkto')
  .description('Talk to your files - local RAG CLI')
  .version('0.1.0');

// Main command: talkto <path>
program
  .argument('<path>', 'Path to file or directory to talk to')
  .option('--reindex', 'Force reindex even if already indexed')
  .option('--llm <provider>', 'LLM provider (ollama, openai)', globalConfig.llm?.provider || 'ollama')
  .option('--model <model>', 'LLM model name', globalConfig.llm?.model || 'llama3.1:8b')
  .option('--embedding <provider>', 'Embedding provider (ollama, openai)', globalConfig.embedding?.provider || 'ollama')
  .option('--embedding-model <model>', 'Embedding model name', globalConfig.embedding?.model || 'nomic-embed-text')
  .option('-q, --query <question>', 'Ask a single question (non-interactive)')
  .option('--voice', 'Enable voice input/output mode (requires: talkto setup --voice)')
  .action(talkto);

// Config subcommand
program
  .command('config')
  .description('Show or edit global configuration')
  .option('--init', 'Create example config file')
  .action(configCommand);

// Indexes subcommand
program
  .command('indexes')
  .description('List and manage stored indexes')
  .option('--clean', 'Remove old indexes')
  .option('--older-than <days>', 'Remove indexes older than N days (default: 30)', '30')
  .option('--yes', 'Skip confirmation prompt')
  .action(indexesCommand);

// Setup / onboarding subcommand
program
  .command('setup')
  .description('Check Ollama status, installed models, and pull missing ones')
  .option('--voice', 'Download voice models (whisper ASR + piper TTS, ~150 MB)')
  .action(setupCommand);

program.parse();

interface IndexRecord {
  hash: string;
  last_indexed: string | null;
  chunk_count: number;
  file_count: number;
}

async function indexesCommand(options: {
  clean?: boolean;
  olderThan: string;
  yes?: boolean;
}): Promise<void> {
  const bridge = new EngineBridge();
  try {
    await bridge.start();
  } catch (error) {
    console.error(chalk.red(`Failed to start engine: ${error}`));
    process.exit(1);
  }

  try {
    const result = await bridge.send<{ indexes: IndexRecord[] }>({
      action: 'list_indexes',
    });

    const indexes = result?.indexes ?? [];

    if (indexes.length === 0) {
      console.log(chalk.gray('No indexes found in ~/.talkto/indexes/'));
      return;
    }

    console.log(chalk.bold('\nStored indexes:'));
    console.log('');
    for (const idx of indexes) {
      const date = idx.last_indexed
        ? new Date(idx.last_indexed).toLocaleDateString()
        : 'unknown';
      console.log(
        `  ${chalk.cyan(idx.hash)}  last indexed: ${date}  ` +
        `${idx.chunk_count} chunks  ${idx.file_count} files`
      );
    }
    console.log('');

    if (!options.clean) {
      return;
    }

    // Filter indexes older than N days
    const days = parseInt(options.olderThan, 10);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);

    const toDelete = indexes.filter((idx) => {
      if (!idx.last_indexed) return true;
      return new Date(idx.last_indexed) < cutoff;
    });

    if (toDelete.length === 0) {
      console.log(chalk.green(`No indexes older than ${days} days found.`));
      return;
    }

    console.log(chalk.yellow(`Found ${toDelete.length} index(es) older than ${days} days:`));
    for (const idx of toDelete) {
      const date = idx.last_indexed
        ? new Date(idx.last_indexed).toLocaleDateString()
        : 'unknown';
      console.log(`  ${chalk.red(idx.hash)}  (${date})`);
    }
    console.log('');

    if (!options.yes) {
      const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
      const answer = await new Promise<string>((resolve) => {
        rl.question('Delete these indexes? [y/N] ', resolve);
      });
      rl.close();
      if (answer.toLowerCase() !== 'y') {
        console.log(chalk.gray('Cancelled.'));
        return;
      }
    }

    for (const idx of toDelete) {
      await bridge.send({ action: 'delete_index', options: { hash: idx.hash } });
      console.log(chalk.green(`Deleted: ${idx.hash}`));
    }
  } finally {
    await bridge.stop();
  }
}

// ---------------------------------------------------------------------------
// talkto setup — Ollama onboarding
// ---------------------------------------------------------------------------

interface OllamaModel {
  name: string;
  size: number;
}

async function checkOllama(): Promise<OllamaModel[] | null> {
  try {
    const res = await fetch(`${OLLAMA_URL}/api/tags`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return null;
    const data = await res.json() as { models: OllamaModel[] };
    return data.models ?? [];
  } catch {
    return null;
  }
}

function ollamaPull(model: string): boolean {
  console.log(chalk.gray(`  Pulling ${model} (this may take a while)...\n`));
  const result = spawnSync('ollama', ['pull', model], { stdio: 'inherit' });
  return result.status === 0;
}

async function setupCommand(options: { voice?: boolean }): Promise<void> {
  console.log('');
  console.log(chalk.bold.cyan('  talkto setup'));
  console.log(chalk.gray('  ─────────────────────────────────────'));
  console.log('');

  // ── 1. Ollama running? ──────────────────────────────────────────────────
  const spinner = ora('Checking Ollama...').start();
  const models = await checkOllama();

  if (models === null) {
    spinner.fail(chalk.red('Ollama is not running'));
    console.log('');
    console.log(chalk.bold('  Install Ollama:'));
    console.log(chalk.gray('    https://ollama.com/download'));
    console.log('');
    console.log(chalk.bold('  Then start it:'));
    console.log(chalk.gray('    ollama serve'));
    console.log('');
    console.log(chalk.gray('  Once Ollama is running, re-run: ') + chalk.cyan('talkto setup'));
    console.log('');
    process.exit(1);
  }

  const modelNames = models.map((m) => m.name);
  spinner.succeed(chalk.green(`Ollama is running`) + chalk.gray(`  (${models.length} model(s) installed)`));
  console.log('');

  // ── 2. Show installed models ────────────────────────────────────────────
  if (models.length > 0) {
    console.log(chalk.bold('  Installed models:'));
    for (const m of models) {
      const sizeMB = Math.round(m.size / 1024 / 1024);
      const sizeStr = sizeMB > 1024
        ? `${(sizeMB / 1024).toFixed(1)} GB`
        : `${sizeMB} MB`;
      console.log(`    ${chalk.cyan(m.name.padEnd(35))} ${chalk.gray(sizeStr)}`);
    }
    console.log('');
  } else {
    console.log(chalk.yellow('  No models installed yet.'));
    console.log('');
  }

  // ── 3. Embedding model check ────────────────────────────────────────────
  const hasEmbed = modelNames.some((n) => n.startsWith(REQUIRED_EMBED_MODEL));

  if (hasEmbed) {
    console.log(`  ${chalk.green('✔')} Embedding model: ${chalk.cyan(REQUIRED_EMBED_MODEL)}`);
  } else {
    console.log(`  ${chalk.red('✘')} Embedding model: ${chalk.cyan(REQUIRED_EMBED_MODEL)} — not installed`);
    console.log(chalk.gray('    (Required for indexing files)'));
    console.log('');

    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const answer = await new Promise<string>((resolve) => {
      rl.question(chalk.yellow(`  Pull ${REQUIRED_EMBED_MODEL} now? [Y/n] `), resolve);
    });
    rl.close();
    console.log('');

    if (answer.trim().toLowerCase() !== 'n') {
      const ok = ollamaPull(REQUIRED_EMBED_MODEL);
      if (ok) {
        console.log(`  ${chalk.green('✔')} ${REQUIRED_EMBED_MODEL} installed`);
      } else {
        console.log(chalk.red(`  Failed to pull ${REQUIRED_EMBED_MODEL}.`));
        console.log(chalk.gray(`  Try manually: ollama pull ${REQUIRED_EMBED_MODEL}`));
      }
    } else {
      console.log(chalk.gray(`  Skipped. Run later: ollama pull ${REQUIRED_EMBED_MODEL}`));
    }
    console.log('');
  }

  // ── 4. Chat model check ─────────────────────────────────────────────────
  const chatModels = modelNames.filter((n) => !n.startsWith(REQUIRED_EMBED_MODEL));

  if (chatModels.length > 0) {
    const display = chatModels.slice(0, 3).join(', ');
    const extra = chatModels.length > 3 ? ` +${chatModels.length - 3} more` : '';
    console.log(`  ${chalk.green('✔')} Chat model(s): ${chalk.cyan(display)}${chalk.gray(extra)}`);
  } else {
    console.log(`  ${chalk.yellow('⚠')}  No chat models installed`);
    console.log(chalk.gray(`    talkto defaults to: ${SUGGESTED_CHAT_MODEL}`));
    console.log(chalk.gray(`    Install it:  ollama pull ${SUGGESTED_CHAT_MODEL}`));
    console.log(chalk.gray(`    Smaller alt: ollama pull phi3`));
  }

  // ── 5. Summary ──────────────────────────────────────────────────────────
  console.log('');
  console.log(chalk.bold('  ─────────────────────────────────────'));

  const ready = hasEmbed && chatModels.length > 0;
  if (ready) {
    console.log(`  ${chalk.green.bold('Ready!')}  Try:`);
    console.log(`    ${chalk.cyan('talkto ./my-project')}`);
    console.log(`    ${chalk.cyan('talkto ./docs -q "What is the API?"')}`);
  } else {
    console.log(`  ${chalk.yellow('Almost there.')}  Install the missing model(s) above, then run:`);
    console.log(`    ${chalk.cyan('talkto setup')}`);
  }
  console.log('');

  // ── 6. Voice setup (optional) ────────────────────────────────────────────
  if (options.voice) {
    const { voiceSetup } = await import('./voice/setup.js');
    await voiceSetup();
  }
}

// ---------------------------------------------------------------------------

async function configCommand(options: { init?: boolean }): Promise<void> {
  const { getConfigPath, getExampleConfig, loadGlobalConfig } = await import('./config.js');
  const configPath = getConfigPath();

  if (options.init) {
    const { writeFileSync, existsSync, mkdirSync } = await import('fs');
    const { dirname } = await import('path');

    if (!existsSync(dirname(configPath))) {
      mkdirSync(dirname(configPath), { recursive: true });
    }

    writeFileSync(configPath, getExampleConfig(), 'utf-8');
    console.log(chalk.green(`Created config file: ${configPath}`));
    return;
  }

  // Show current config
  console.log(chalk.bold('Configuration'));
  console.log(chalk.gray(`File: ${configPath}`));
  console.log('');

  const config = loadGlobalConfig();
  console.log(chalk.cyan('Embedding:'));
  console.log(`  Provider: ${config.embedding?.provider}`);
  console.log(`  Model:    ${config.embedding?.model}`);
  console.log('');
  console.log(chalk.cyan('LLM:'));
  console.log(`  Provider: ${config.llm?.provider}`);
  console.log(`  Model:    ${config.llm?.model}`);
  console.log('');
  console.log(chalk.gray(`Run 'talkto config --init' to create a config file`));
}

interface TalktoOptions {
  reindex?: boolean;
  llm: string;
  model: string;
  embedding: string;
  embeddingModel: string;
  query?: string;
  voice?: boolean;
}

async function talkto(targetPath: string, options: TalktoOptions): Promise<void> {
  const absPath = resolve(targetPath);

  // Verify path exists
  if (!existsSync(absPath)) {
    console.error(chalk.red(`Error: Path does not exist: ${absPath}`));
    process.exit(1);
  }

  // Ensure storage directories exist
  const storagePath = getDefaultStoragePath();
  const indexesPath = getIndexesPath();

  if (!existsSync(storagePath)) {
    mkdirSync(storagePath, { recursive: true });
  }
  if (!existsSync(indexesPath)) {
    mkdirSync(indexesPath, { recursive: true });
  }

  // Start engine
  const spinner = ora('Starting engine...').start();
  const bridge = new EngineBridge();

  try {
    await bridge.start();

    // Send configuration to engine (merge CLI options with global config)
    await bridge.send({
      action: 'config',
      options: {
        operation: 'set_all',
        config: {
          embedding: {
            provider: options.embedding,
            model: options.embeddingModel,
            api_key: globalConfig.embedding?.api_key,
            base_url: globalConfig.embedding?.base_url,
          },
          llm: {
            provider: options.llm,
            model: options.model,
            api_key: globalConfig.llm?.api_key,
            base_url: globalConfig.llm?.base_url,
          },
        },
      },
    });

    spinner.succeed('Engine ready');
  } catch (error) {
    spinner.fail('Failed to start engine');
    console.error(chalk.red(String(error)));
    process.exit(1);
  }

  // Index the path
  spinner.start(`Indexing ${chalk.cyan(absPath)}...`);

  try {
    const indexResult = await bridge.send<IndexResponse['data']>({
      action: 'index',
      path: absPath,
      options: {
        force: options.reindex || false,
      },
    });

    if (indexResult && indexResult.errors && indexResult.errors.length > 0) {
      const firstError = indexResult.errors[0].error;
      if (firstError.includes('Ollama')) {
        spinner.fail('Ollama is not running');
        console.log('');
        console.log(chalk.yellow('To use talkto, you need Ollama running locally:'));
        console.log(chalk.gray('  1. Install Ollama: https://ollama.com/download'));
        console.log(chalk.gray('  2. Pull the embedding model: ollama pull nomic-embed-text'));
        console.log(chalk.gray('  3. Pull a chat model: ollama pull llama3.1:8b'));
        console.log(chalk.gray('  4. Run talkto again'));
      } else {
        spinner.fail(`Indexing failed with ${indexResult.errors.length} error(s)`);
        for (const err of indexResult.errors) {
          console.log(chalk.red(`  • ${err.error}`));
        }
      }
      await bridge.stop();
      process.exit(1);
    } else if (indexResult && indexResult.filesProcessed > 0) {
      spinner.succeed(
        `Indexed ${chalk.green(indexResult.filesProcessed)} files ` +
        `(${indexResult.chunksCreated} chunks, ${indexResult.filesSkipped} skipped)`
      );
    } else if (indexResult && indexResult.filesSkipped > 0) {
      spinner.succeed(`Already indexed (${indexResult.filesSkipped} files up to date)`);
    } else {
      spinner.warn('No files found to index');
    }
  } catch (error) {
    spinner.fail('Indexing failed');
    console.error(chalk.red(String(error)));
    await bridge.stop();
    process.exit(1);
  }

  // Single query mode
  if (options.query) {
    console.log('');
    await handleQuery(bridge, options.query);
    await bridge.stop();
    process.exit(0);
  }

  // Interactive chat mode
  console.log('');
  console.log(chalk.bold(`Talking to ${chalk.cyan(targetPath)}`));
  console.log('');

  // ── Voice mode ────────────────────────────────────────────────────────────
  if (options.voice) {
    const { VoiceManager } = await import('./voice/index.js');
    const voice = new VoiceManager();
    let voiceReady = false;

    try {
      await voice.init();
      voiceReady = true;
    } catch (err) {
      console.error(chalk.red(`Voice init failed: ${err}`));
      console.log(chalk.gray('Run "talkto setup --voice" to download required models.'));
      console.log(chalk.gray('Falling back to text mode...\n'));
    }

    if (voiceReady) {
      console.log(chalk.gray('Voice mode active. Press SPACE to talk, Q to quit.'));

      const voiceLoop = async (): Promise<void> => {
        const text = await voice.listen();

        if (text === '__quit__') {
          voice.dispose();
          console.log('');
          console.log(chalk.gray('Goodbye!'));
          await bridge.stop();
          process.exit(0);
        }

        if (!text) {
          voiceLoop();
          return;
        }

        await handleQuery(bridge, text, voice);
        voiceLoop();
      };

      voiceLoop();
      return;
    }
    // Fall through to text mode if voice init failed
  }

  // ── Text mode (default) ───────────────────────────────────────────────────
  console.log(chalk.gray('Type your questions. Use Ctrl+C or type "exit" to quit.'));
  console.log('');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const prompt = (): void => {
    rl.question(chalk.cyan('> '), async (input) => {
      const trimmed = input.trim();

      if (!trimmed) {
        prompt();
        return;
      }

      // Exit commands
      if (['exit', 'quit', 'q', '/exit', '/quit', '/q'].includes(trimmed.toLowerCase())) {
        rl.close();
        return;
      }

      // Handle query with streaming
      await handleQuery(bridge, trimmed);
      prompt();
    });
  };

  rl.on('close', async () => {
    console.log('');
    console.log(chalk.gray('Goodbye!'));
    await bridge.stop();
    process.exit(0);
  });

  prompt();
}

async function handleQuery(
  bridge: EngineBridge,
  query: string,
  voice?: import('./voice/index.js').VoiceManager
): Promise<void> {
  const sources: Array<{ file: string; lines?: string }> = [];

  console.log('');
  process.stdout.write(chalk.bold(''));

  try {
    await bridge.sendStreaming(
      {
        action: 'query',
        query,
        options: { stream: true, topK: 5 },
      },
      (chunk: unknown) => {
        const c = chunk as StreamChunk['data'];
        if (c.type === 'token' && c.content) {
          process.stdout.write(c.content);
          voice?.feedToken(c.content);
        } else if (c.type === 'source' && c.source) {
          sources.push(c.source);
        }
      }
    );
    voice?.flushSpeech();

    console.log('');

    if (sources.length > 0) {
      console.log('');
      console.log(chalk.gray('Sources:'));
      for (const source of sources) {
        const lines = source.lines ? `:${source.lines}` : '';
        console.log(chalk.gray(`  • ${source.file}${lines}`));
      }
    }
    console.log('');
  } catch (error) {
    console.log('');
    console.error(chalk.red(`Error: ${error}`));
    console.log('');
  }
}
