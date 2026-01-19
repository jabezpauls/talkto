CLI RAG Tool — Build Plan
Goal

Build an npm-installable CLI that:

Indexes files/directories (any format)

Runs a local or API-based RAG chatbot

Works offline by default

Is fast, predictable, and developer-friendly

Phase 0 — Product Decisions (Freeze These First)

Distribution

npm package: @fludigo/rag

Binary command: rag

Runtime split

Node.js → CLI, UX, config

Python → AI engine (RAG, embeddings, vector DB)

Defaults

Vector DB: FAISS (local)

Embeddings: nomic-embed-text (Ollama)

LLM: Ollama (local), OpenAI optional

Storage: ~/.rag/

Phase 1 — Repository & Tooling Setup (Day 1)
1.1 Repo structure
rag/
├── packages/
│   ├── cli/            # npm package
│   └── engine/         # python engine
├── README.md
└── .gitignore

1.2 CLI stack

Node 18+

TypeScript

Commander or Typer-like CLI

zx / execa (process control)

js-yaml (config)

1.3 Engine stack

Python 3.11

FAISS

Ollama

tree-sitter

pdfplumber

SQLite

Phase 2 — CLI Skeleton (Day 1–2)
Commands (must compile early)
rag init
rag index <path>
rag chat
rag config

CLI responsibilities

Parse args

Load config (.ragrc.yaml)

Validate environment (Python, Ollama)

Spawn engine

Render output (Rich-like)

Deliverable

rag init creates config + folders

No AI yet

Phase 3 — Python Engine Core (Day 2–4)
3.1 Engine contract (non-negotiable)

Engine accepts JSON commands via:

STDIN/STDOUT (v1)

Local HTTP (v2)

Example:

{ "action": "index", "path": "./src" }

3.2 File ingestion

Implement loaders:

Type	Loader
.md, .txt	Text
.py, .js, .ts	Code
.pdf	pdfplumber
.docx	python-docx

Rules:

.gitignore aware

Max file size cap (e.g. 5MB)

3.3 Chunking (quality critical)

Text

Recursive splitter

Token-aware

Overlap support

Code

tree-sitter

Function / class boundaries

Preserve metadata

Chunk schema:

{
  "id": "uuid",
  "content": "...",
  "metadata": {
    "file": "src/auth.py",
    "lines": "120–180",
    "language": "python"
  }
}

Phase 4 — Embeddings & Storage (Day 4–5)
4.1 Embeddings

Implement providers:

local → Ollama

openai → API

4.2 Vector store

FAISS index

SQLite metadata

Structure:

~/.rag/
├── indexes/
│   └── project_hash/
│       ├── vectors.faiss
│       └── meta.db

4.3 Incremental indexing

Hash file content

Skip unchanged files

Phase 5 — RAG Chat Engine (Day 6–7)
5.1 Retrieval

Query embedding

Top-K similarity search

Context assembly (token-bounded)

5.2 Prompt discipline

Hard rules:

Answer only from context

Cite sources

Say “I don’t know” when missing

5.3 LLM abstraction
class LLM:
    def generate(prompt, stream=False)


Providers:

Ollama

OpenAI

Phase 6 — CLI Chat UX (Day 7–8)
Features

Streaming tokens

/exit

/sources

/reindex

Example:

> How does login work?

Answer:
Login is implemented in auth/service.py using JWT...

Sources:
- auth/service.py:120–180

Phase 7 — Node ↔ Python Bridge (Day 8–9)
Engine control

Spawn engine process

Send JSON commands

Stream responses

Error handling

Engine crash recovery

Clear error messages

Debug mode

Phase 8 — Config & Profiles (Day 9)
.ragrc.yaml
index:
  include: [src, docs]
  exclude: [node_modules]

embedding:
  provider: local
  model: nomic-embed-text

llm:
  provider: ollama
  model: llama3.1:8b


CLI overrides:

rag chat --llm openai --model gpt-4.1-mini

Phase 9 — Packaging & Install Experience (Day 10)
npm install flow

Postinstall:

Check Python

Setup venv

Install engine deps

Trust checklist

No telemetry

No background services

Clear privacy statement

Phase 10 — MVP Quality Bar

Before release, ensure:

Works fully offline

Reindex < 2s for small repos

Deterministic answers

Handles 10k+ chunks

Clear failure modes

Phase 11 — Release Plan
Versioning

0.1.0 — MVP

0.2.0 — Incremental indexing + git awareness

0.3.0 — Agents + tools

README must include

Why this exists

Offline guarantee

Example screenshots

Comparison table

Optional v2 (Do NOT block v1)

Rust engine

Git commit-aware RAG

Multi-project chat

VS Code extension

Agent commands (/summarize, /refactor)

Final Advice (Important)

Do not over-abstract.
Do not chase LangChain parity.
Do not add UI.

Your moat is:

“npm-native, offline, deterministic RAG for developers.”
