"""
RAG prompt templates with strict source discipline.
"""

RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based ONLY on the provided context.

CRITICAL RULES:
1. ONLY use information from the provided context to answer questions
2. If the context does not contain enough information, say "I don't have enough information in the indexed documents to answer this question."
3. ALWAYS cite your sources using [Source: filename] format
4. Do NOT make up or infer information not explicitly in the context
5. Be concise and direct in your answers

You are helping a developer understand their codebase and documentation."""


def build_context_prompt(question: str, context: str) -> str:
    """Build the user prompt with context"""
    return f"""Context from indexed documents:
---
{context}
---

Question: {question}

Answer based ONLY on the context above. Cite sources using [Source: filename] format."""
