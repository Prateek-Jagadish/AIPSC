"""
services/llm/llm_client.py
───────────────────────────
Single GPT-4o caller used across the entire system.

All LLM calls in the project go through this module so that:
    - Retry logic is centralised
    - JSON parsing is consistent
    - Token usage is logged
    - Swapping models later requires changing only this file
"""

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from loguru import logger
import json
import re

from app.core.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ── Core Caller ───────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def call_llm(
    prompt: str,
    system: str = "You are a UPSC expert assistant.",
    model: str = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> str:
    """
    Calls GPT-4o and returns the raw text response.
    Low temperature (0.2) for consistent structured outputs.
    """
    response = await _client.chat.completions.create(
        model=model or settings.OPENAI_CHAT_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    usage   = response.usage

    logger.debug(
        f"LLM call | tokens: {usage.prompt_tokens}+{usage.completion_tokens}"
        f"={usage.total_tokens}"
    )

    return content.strip()


# ── JSON Caller ───────────────────────────────────────────────────────────────

async def call_llm_json(
    prompt: str,
    system: str = "You are a UPSC expert assistant. Always respond with valid JSON only.",
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> dict:
    """
    Calls GPT-4o and parses the response as JSON.
    Strips markdown code fences if the model adds them.
    Returns an empty dict on parse failure (never raises).
    """
    raw = await call_llm(
        prompt=prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        return _parse_json(raw)
    except Exception as e:
        logger.error(f"❌ JSON parse failed: {e}\nRaw response:\n{raw[:300]}")
        return {}


# ── JSON Parser ───────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """
    Robustly parses JSON from LLM output.
    Handles common LLM habits:
        - Wrapping in ```json ... ```
        - Leading/trailing whitespace
        - Extra text before or after the JSON object
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to extract the first {...} block
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM output: {cleaned[:200]}")
