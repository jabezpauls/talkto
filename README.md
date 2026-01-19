# talkto

A local RAG CLI that lets you chat with your files. Index any directory and ask questions about your code, docs, or notes.

## Features

- **Local-first**: Uses Ollama by default - no data leaves your machine
- **Fast indexing**: Incremental indexing skips unchanged files
- **Code-aware**: Tree-sitter chunking preserves function/class boundaries
- **Multiple formats**: `.py`, `.js`, `.ts`, `.md`, `.txt`, `.pdf`, `.docx`
- **Source citations**: Every answer includes file and line references
- **Configurable**: Use OpenAI, Gemini, or any OpenAI-compatible API

## Installation

```bash
git clone https://github.com/yourusername/cli-rag.git
cd cli-rag
npm install && npm run build

# Set up Python engine
cd packages/engine
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install openai  # Optional: for OpenAI/Gemini support
```

### Prerequisites

- Node.js 18+, Python 3.11+
- [Ollama](https://ollama.com/download) (for local mode)

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

## Usage

```bash
talkto ./my-project           # Talk to a directory
talkto ./docs/api.md          # Talk to a single file
talkto ./src --reindex        # Force reindex
talkto ./src -q "What does main do?"  # Single query mode
```

### Interactive Mode

```
$ talkto ./src

✔ Engine ready
✔ Indexed 42 files (156 chunks, 3 skipped)

Talking to ./src
Type your questions. Use Ctrl+C or type "exit" to quit.

> How does authentication work?

The authentication flow uses JWT tokens stored in httpOnly cookies...

Sources:
  • src/auth/middleware.ts:15-42
  • src/auth/jwt.ts:8-23
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--reindex` | Force reindex even if already indexed |
| `--llm <provider>` | LLM provider (ollama, openai) |
| `--model <model>` | LLM model name |
| `--embedding <provider>` | Embedding provider (ollama, openai) |
| `--embedding-model <model>` | Embedding model name |
| `-q, --query <question>` | Ask a single question (non-interactive) |

## Configuration

Create config: `talkto config --init`

Edit `~/.talkto/config.yaml`:

**Default (Ollama - fully local):**
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text

llm:
  provider: ollama
  model: llama3.1:8b
```

**OpenAI:**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-small
  api_key: sk-your-key-here

llm:
  provider: openai
  model: gpt-4o-mini
  api_key: sk-your-key-here
```

**Custom Gateway (OpenRouter, local proxy, etc.):**
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text

llm:
  provider: openai
  model: gemini-2.5-flash
  api_key: your-gateway-key
  base_url: http://localhost:8080/v1
```

CLI flags override config: `talkto ./src --llm openai --model gpt-4o`

## How It Works

1. **Indexing**: Files are chunked, embedded, and stored in a local FAISS index
2. **Querying**: Your question is embedded and matched against stored chunks
3. **Generation**: Relevant chunks are sent to the LLM with your question
4. **Citations**: Sources are tracked and displayed with the response

### Storage

```
~/.talkto/
├── config.yaml      # Global configuration
└── indexes/         # FAISS indexes (one per project)
    └── <hash>/
        ├── index.faiss
        └── metadata.db
```

## Supported File Types

| Type | Extensions |
|------|------------|
| Code | `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.go`, `.rs`, `.java` |
| Docs | `.md`, `.txt`, `.rst` |
| Office | `.pdf`, `.docx` |

## Commands

| Command | Description |
|---------|-------------|
| `talkto <path>` | Index and chat with files |
| `talkto config` | Show current configuration |
| `talkto config --init` | Create example config file |

## Troubleshooting

**"Ollama is not running"** - Run `ollama serve`

**"Model not found"** - Run `ollama pull <model-name>`

**"openai package not installed"**
```bash
cd packages/engine && source .venv/bin/activate && pip install openai
```

## License

MIT
