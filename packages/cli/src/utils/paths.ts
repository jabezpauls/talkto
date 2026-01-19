import { homedir } from 'os';
import { join, resolve } from 'path';
import { existsSync } from 'fs';

/**
 * Get the default storage path (~/.talkto)
 */
export function getDefaultStoragePath(): string {
  return join(homedir(), '.talkto');
}

/**
 * Get the indexes directory path
 */
export function getIndexesPath(storagePath?: string): string {
  return join(storagePath || getDefaultStoragePath(), 'indexes');
}

/**
 * Get the index path for a specific project
 */
export function getProjectIndexPath(projectPath: string, storagePath?: string): string {
  // Use a hash of the absolute path as the index directory name
  const absPath = resolve(projectPath);
  const hash = simpleHash(absPath);
  return join(getIndexesPath(storagePath), hash);
}

/**
 * Simple hash function for creating index directory names
 */
function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
}

/**
 * Find the config file by searching up from the current directory
 */
export function findConfigFile(startDir: string = process.cwd()): string | null {
  let currentDir = resolve(startDir);
  const root = resolve('/');

  while (currentDir !== root) {
    const configPath = join(currentDir, '.ragrc.yaml');
    if (existsSync(configPath)) {
      return configPath;
    }
    currentDir = resolve(currentDir, '..');
  }

  return null;
}

/**
 * Get the engine path (relative to CLI package)
 */
export function getEnginePath(): string {
  // In development, engine is at ../engine relative to cli
  // In production (npm install), engine is bundled with the package
  const devPath = resolve(__dirname, '../../..', 'engine');
  if (existsSync(devPath)) {
    return devPath;
  }

  // Fallback to same directory structure in installed package
  return resolve(__dirname, '../..', 'engine');
}
