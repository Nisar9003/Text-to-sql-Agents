"""
Router module.

Decides whether a user's question should be answered by:
  - "sql"      -> querying structured tables (employees, sales, uploaded data tables, etc.)
  - "document" -> searching the free-text content of the 'documents' table
    (built from unstructured PDFs uploaded in Phase 2)
"""
from llm_client import get_client, get_text, MODEL, LLMConfigError


def classify_question(question: str, schema_context: str, has_documents: bool, conversation_context: str = "") -> str:
    """
    Returns "sql" or "document".

    If there are no documents stored yet, this always returns "sql"
    without making an LLM call (nothing to search).
    """
    if not has_documents:
        return "sql"

    conversation_block = (
        f"\nConversation so far:\n{conversation_context}\n" if conversation_context else ""
    )

    system_prompt = f"""You are a routing assistant. Given a database schema and a user's question,
decide whether the question should be answered by:
- SQL: querying structured data tables (counts, sums, filters, joins, sorting, listing rows)
- DOCUMENT: searching the free-text content of the 'documents' table, which holds text
  extracted from uploaded PDF reports/contracts/articles (e.g. "what does the contract say about X",
  "summarize the report", "according to the document...")

Database schema:
{schema_context}
{conversation_block}
Respond with EXACTLY one word: SQL or DOCUMENT. No explanation, no punctuation.
"""

    try:
        client = get_client()
    except LLMConfigError:
        return "sql"  # fail safe: default to SQL path if the LLM client can't be configured

    response = client.messages.create(
        model=MODEL,
        max_tokens=10,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )
    answer = get_text(response).strip().upper()
    return "document" if "DOCUMENT" in answer else "sql"