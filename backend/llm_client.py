"""
Shared LLM client module.

Provides a single place to configure the Anthropic client and model name,
used by sql_agent.py, router.py, and document_qa.py.
"""
import os
import anthropic

MODEL = "claude-sonnet-4-5"


class LLMConfigError(Exception):
    """Raised when the LLM client cannot be configured (e.g. missing API key)."""
    pass


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMConfigError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Please set your API key in the .env file or environment."
        )
    return anthropic.Anthropic(api_key=api_key)


def get_text(response) -> str:
    """Extracts concatenated text from an Anthropic messages.create() response."""
    return "".join(block.text for block in response.content if block.type == "text")