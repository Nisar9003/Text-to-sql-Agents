"""
Document Q&A module (RAG-lite).

Answers questions about the free-text content of uploaded PDFs by:
  1. Pulling stored text chunks from the 'documents' table
  2. Feeding them to the LLM as context (capped to a reasonable size)
  3. Asking the LLM to answer the question using only that context

This is "RAG-lite": no vector embeddings/similarity search, just stuffing
all available document text into context. This works well for the scale
of a single-user local app; if the documents table grows very large,
a proper vector store (Phase 5+) would be the next step.
"""
from llm_client import get_client, get_text, MODEL, LLMConfigError

MAX_CONTEXT_CHARS = 12000  # keeps prompt size (and cost) reasonable


def documents_table_has_content(conn) -> bool:
    """Returns True if the 'documents' table exists and has at least one row."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        return cur.fetchone()[0] > 0
    except Exception:
        return False


def _gather_context(conn) -> tuple[str, list[dict]]:
    """
    Pulls document chunks from the database and builds a context string,
    capped at MAX_CONTEXT_CHARS. Returns (context_text, sources_used).
    """
    cur = conn.cursor()
    cur.execute("SELECT filename, chunk_index, content FROM documents ORDER BY filename, chunk_index")
    all_chunks = cur.fetchall()

    context_parts = []
    sources = []
    total_len = 0

    for filename, chunk_index, content in all_chunks:
        block = f"[Source: {filename}, part {chunk_index + 1}]\n{content}"
        if total_len + len(block) > MAX_CONTEXT_CHARS:
            break
        context_parts.append(block)
        total_len += len(block)
        sources.append({"filename": filename, "chunk_index": chunk_index})

    return "\n\n---\n\n".join(context_parts), sources


def answer_from_documents(question: str, conn, conversation_context: str = "") -> tuple[str, list[dict]]:
    """
    Answers a question using the content of uploaded (unstructured) PDFs.

    Returns:
        (answer_text, sources) where sources is a list of {"filename", "chunk_index"}
        for the document chunks that were available to the LLM.
    """
    context_text, sources = _gather_context(conn)

    if not context_text:
        return "No document content has been uploaded yet.", []

    conversation_block = (
        f"\nConversation so far (for resolving follow-up references):\n{conversation_context}\n"
        if conversation_context else ""
    )

    system_prompt = f"""You answer questions using ONLY the following document excerpts.
If the answer is not contained in the excerpts, say clearly that you don't have that information —
do not make anything up. Mention the source filename when it is relevant to the answer.

Document excerpts:
{context_text}
{conversation_block}
The user's question may be in English, Urdu, or Roman Urdu. Understand the intent regardless of language,
and answer in the same language style the user used.
"""

    try:
        client = get_client()
    except LLMConfigError as e:
        return f"Could not answer: {str(e)}", []

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )
    answer_text = get_text(response).strip()
    return answer_text, sources