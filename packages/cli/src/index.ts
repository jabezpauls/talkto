import { Command } from 'commander';
import { resolve } from 'path';
import { existsSync, mkdirSync } from 'fs';
import chalk from 'chalk';
import ora from 'ora';
import * as readline from 'readline';
import { EngineBridge } from './engine/bridge.js';
import { getDefaultStoragePath, getIndexesPath } from './utils/paths.js';
import { loadGlobalConfig } from './config.js';
import type { IndexResponse, QueryResponse, StreamChunk } from './types/index.js';

// Load global config for defaults
const globalConfig = loadGlobalConfig();

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
  .action(talkto);

// Config subcommand
program
  .command('config')
  .description('Show or edit global configuration')
  .option('--init', 'Create example config file')
  .action(configCommand);

program.parse();

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

    // Send configuration to engine
    await bridge.send({
      action: 'config',
      options: {
        operation: 'set_all',
        config: {
          embedding: {
            provider: options.embedding,
            model: options.embeddingModel,
          },
          llm: {
            provider: options.llm,
            model: options.model,
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

async function handleQuery(bridge: EngineBridge, query: string): Promise<void> {
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
        } else if (c.type === 'source' && c.source) {
          sources.push(c.source);
        }
      }
    );

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
