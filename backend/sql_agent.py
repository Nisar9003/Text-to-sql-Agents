"""
SQL Agent module.

Uses the Claude API to convert a natural language question into a SQL
query, and applies safety checks so that no destructive query
(DELETE/DROP/UPDATE/INSERT) can ever be executed.

Also supports self-correction (correct_sql) and conversation memory
(conversation_context parameter) so follow-up questions work.
"""
import re

from llm_client import get_client, get_text, MODEL, LLMConfigError

# Only these keywords are allowed at the start of a query
ALLOWED_START = ("SELECT", "WITH")

# These keywords must never appear anywhere in the query (case-insensitive)
FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA", "VACUUM",
]

RULES_TEXT = """Rules:
- Only generate SELECT (or WITH...SELECT) queries. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or any write operation.
- Only use tables and columns that exist in the schema above.
- Return ONLY the raw SQL query, with no explanation, no markdown formatting, no comments.
- If the question is ambiguous, make a reasonable assumption and generate the best-guess query.
- If the question refers to something from the conversation history (e.g. "iska", "us mein se", "and also show..."), resolve it using that context.
- The user's question may be in English, Urdu, or Roman Urdu (Urdu written in English letters). Understand the intent regardless of language."""


class SQLGenerationError(Exception):
    """Raised when the LLM fails to produce a valid/safe SQL query."""
    pass


def _extract_sql(raw_text: str) -> str:
    """Extracts only the SQL from the LLM's response (even if wrapped in a markdown code block)."""
    text = raw_text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    return text.strip().rstrip(";").strip()


def validate_sql(sql: str) -> None:
    """Checks the query for safety. Raises SQLGenerationError if unsafe."""
    if not sql:
        raise SQLGenerationError("The LLM returned an empty SQL query.")

    upper_sql = sql.upper()

    if not upper_sql.startswith(ALLOWED_START):
        raise SQLGenerationError(
            f"Only SELECT/WITH queries are allowed. This query is not allowed: {sql}"
        )

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise SQLGenerationError(
                f"This query contains the forbidden keyword '{keyword}'. "
                "Only read-only (SELECT) queries are allowed."
            )

    if ";" in sql:
        raise SQLGenerationError("Multiple SQL statements are not allowed.")


def _call_llm(system_prompt: str, question: str) -> str:
    """Sends the system prompt + question to Claude and returns validated SQL."""
    try:
        client = get_client()
    except LLMConfigError as e:
        raise SQLGenerationError(str(e))

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )
    sql = _extract_sql(get_text(response))
    validate_sql(sql)
    return sql


def _conversation_block(conversation_context: str) -> str:
    if not conversation_context:
        return ""
    return f"\nConversation so far (for resolving follow-up references):\n{conversation_context}\n"


def generate_sql(question: str, schema_context: str, conversation_context: str = "") -> str:
    """Converts the user's natural language question into a SQL query (first attempt)."""
    system_prompt = f"""You are an expert SQL generator. You convert natural language questions
into SQLite SELECT queries based on the given database schema.

Database schema:
{schema_context}
{_conversation_block(conversation_context)}
{RULES_TEXT}
"""
    return _call_llm(system_prompt, question)


def correct_sql(question: str, schema_context: str, previous_sql: str, error_message: str, conversation_context: str = "") -> str:
    """Asks the LLM to fix a SQL query that failed, given the error message."""
    system_prompt = f"""You are an expert SQL generator. You convert natural language questions
into SQLite SELECT queries based on the given database schema.

Database schema:
{schema_context}
{_conversation_block(conversation_context)}
Your previous attempt at answering this question produced a SQL query that failed.

Previous SQL:
{previous_sql}

Error message:
{error_message}

Carefully analyze the error and the schema, then return a corrected SQL query that fixes the issue.

{RULES_TEXT}
"""
    return _call_llm(system_prompt, question)