// Configuration types

export interface RagConfig {
  index: IndexConfig;
  embedding: EmbeddingConfig;
  llm: LLMConfig;
  storage: StorageConfig;
}

export interface IndexConfig {
  include: string[];
  exclude: string[];
  maxFileSize: number; // bytes
}

export interface EmbeddingConfig {
  provider: 'local' | 'openai';
  model: string;
}

export interface LLMConfig {
  provider: 'ollama' | 'openai';
  model: string;
}

export interface StorageConfig {
  path: string;
}

// Protocol types for Node-Python communication

export interface BaseRequest {
  id: string;
  action: string;
  timestamp: string;
}

export interface IndexRequest extends BaseRequest {
  action: 'index';
  path: string;
  options: {
    include?: string[];
    exclude?: string[];
    force?: boolean;
  };
}

export interface QueryRequest extends BaseRequest {
  action: 'query';
  query: string;
  options: {
    topK?: number;
    stream?: boolean;
  };
}

export interface ConfigRequest extends BaseRequest {
  action: 'config';
  operation: 'get' | 'set';
  key?: string;
  value?: unknown;
}

export interface HealthRequest extends BaseRequest {
  action: 'health';
}

export type EngineRequest = IndexRequest | QueryRequest | ConfigRequest | HealthRequest;

export interface BaseResponse {
  id: string;
  status: 'success' | 'error' | 'streaming';
  timestamp: string;
}

export interface IndexResponse extends BaseResponse {
  action: 'index';
  data?: {
    filesProcessed: number;
    filesSkipped: number;
    chunksCreated: number;
    duration: number;
    errors: Array<{ file: string; error: string }>;
  };
  error?: string;
}

export interface QueryResponse extends BaseResponse {
  action: 'query';
  data?: {
    answer: string;
    sources: Array<{
      file: string;
      lines?: string;
      relevance: number;
      snippet: string;
    }>;
    hasAnswer: boolean;
  };
  error?: string;
}

export interface StreamChunk extends BaseResponse {
  status: 'streaming';
  data: {
    type: 'token' | 'source' | 'done';
    content?: string;
    source?: {
      file: string;
      lines?: string;
      relevance: number;
    };
  };
}

export interface ErrorResponse extends BaseResponse {
  status: 'error';
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export type EngineResponse = IndexResponse | QueryResponse | StreamChunk | ErrorResponse;

// Chunk types

export interface ChunkMetadata {
  file: string;
  lines?: string;
  language: string;
  chunkType: 'text' | 'code' | 'function' | 'class';
  contentHash: string;
  indexedAt: string;
}

export interface Chunk {
  id: string;
  content: string;
  metadata: ChunkMetadata;
}
