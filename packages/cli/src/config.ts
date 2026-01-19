import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import yaml from 'js-yaml';
import { getDefaultStoragePath } from './utils/paths.js';

export interface TalktoConfig {
  embedding?: {
    provider?: string;
    model?: string;
  };
  llm?: {
    provider?: string;
    model?: string;
  };
}

const DEFAULT_CONFIG: TalktoConfig = {
  embedding: {
    provider: 'ollama',
    model: 'nomic-embed-text',
  },
  llm: {
    provider: 'ollama',
    model: 'llama3.1:8b',
  },
};

/**
 * Get the global config file path
 */
export function getConfigPath(): string {
  return join(getDefaultStoragePath(), 'config.yaml');
}

/**
 * Load config from ~/.talkto/config.yaml
 */
export function loadGlobalConfig(): TalktoConfig {
  const configPath = getConfigPath();

  if (!existsSync(configPath)) {
    return DEFAULT_CONFIG;
  }

  try {
    const content = readFileSync(configPath, 'utf-8');
    const userConfig = yaml.load(content) as TalktoConfig;

    // Merge with defaults
    return {
      embedding: { ...DEFAULT_CONFIG.embedding, ...userConfig?.embedding },
      llm: { ...DEFAULT_CONFIG.llm, ...userConfig?.llm },
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

/**
 * Save config to ~/.talkto/config.yaml
 */
export function saveGlobalConfig(config: TalktoConfig): void {
  const storagePath = getDefaultStoragePath();
  const configPath = getConfigPath();

  if (!existsSync(storagePath)) {
    mkdirSync(storagePath, { recursive: true });
  }

  const content = yaml.dump(config, { indent: 2 });
  writeFileSync(configPath, content, 'utf-8');
}

/**
 * Generate example config content
 */
export function getExampleConfig(): string {
  return `# talkto configuration
# Location: ~/.talkto/config.yaml

# Embedding provider for indexing
embedding:
  provider: ollama          # ollama or openai
  model: nomic-embed-text   # Model name

# LLM provider for chat
llm:
  provider: ollama          # ollama or openai
  model: llama3.1:8b        # Model name

# For OpenAI, set OPENAI_API_KEY environment variable
`;
}
