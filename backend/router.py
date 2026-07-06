"""
Router module.

Decides whether a user's question should be answered by:
  - "sql"        -> querying structured tables (employees, sales, uploaded data tables, etc.)
  - "document"    -> searching the free-text content of the 'documents' table
     (built from unstructured PDFs uploaded in Phase 2)
  - "unrelated"    -> the question has nothing to do with the schema or any uploaded
     documents (e.g. random pasted text, personal messages, unrelated topics).
     The agent should NOT try to force a SQL query in this case.
"""
from llm_client import get_client, get_text, MODEL, LLMConfigError


def classify_question(question: str, schema_context: str, has_documents: bool, conversation_context: str = "") -> str:
    """
    Returns "sql", "document", or "unrelated".

    This always makes a (cheap, short) LLM call so that questions/text that
    have nothing to do with the schema or documents are correctly caught,
    instead of forcing the SQL agent to hallucinate a query.
    """
    conversation_block = (
        f"\nConversation so far:\n{conversation_context}\n" if conversation_context else ""
    )
    document_note = (
        "There ARE uploaded documents available to search."
        if has_documents else
        "There are NO uploaded documents yet, so never classify as DOCUMENT."
    )

    system_prompt = f"""You are a routing assistant. Given a database schema and a user's message,
classify it into exactly ONE of these three categories:

- SQL: the message is a question that can be answered by querying the structured data tables below
  (counts, sums, filters, joins, sorting, listing rows, etc.)
- DOCUMENT: the message asks about the content/meaning of uploaded narrative documents
  (e.g. "what does the contract say about X", "summarize the report"). {document_note}
- UNRELATED: the message has nothing to do with the schema or any uploaded documents.
  This includes: random pasted paragraphs, personal messages/opinions/complaints about unrelated
  topics, greetings, general chit-chat, or any text that is not actually a question about this data.
  When in doubt about whether a long pasted block of text is really a question about the schema,
  prefer UNRELATED rather than inventing a forced interpretation.

Database schema:
{schema_context}
{conversation_block}
Respond with EXACTLY one word: SQL, DOCUMENT, or UNRELATED. No explanation, no punctuation.
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
    if "UNRELATED" in answer:
        return "unrelated"
    if "DOCUMENT" in answer:
        return "document"
    return "sql"
