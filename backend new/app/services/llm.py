"""
app/services/llm.py -- Central async LLM utility for all agents.

All agents import `llm_chat` and `llm_json` from here.
Uses Groq API (llama-3.3-70b-versatile) via async httpx REST.
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_API_KEY       = os.getenv("GROQ_API_KEY", os.getenv("GROK_API_KEY", ""))
_BASE_URL      = "https://api.groq.com/openai/v1"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"


async def llm_chat(
    messages: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0.3,
    model: str = _DEFAULT_MODEL,
    json_mode: bool = False,
) -> str:
    """
    Call the Groq LLM and return the response content as a string.

    Args:
        messages: List of {"role": ..., "content": ...} dicts (without system msg).
        system_prompt: Optional system prompt prepended to messages.
        temperature: Sampling temperature (0 = deterministic).
        model: Model name.
        json_mode: If True, instructs the model to return valid JSON only.

    Returns:
        String content of the LLM response.
    """
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    if json_mode:
        # Append a reminder to ensure JSON output
        full_messages[-1]["content"] += "\n\nRespond ONLY with valid JSON. No markdown, no explanation."

    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        return f"[LLM Error: HTTP {e.response.status_code}]"
    except Exception as e:
        return f"[LLM Error: {str(e)}]"


async def llm_json(
    messages: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0,
    fallback: dict | None = None,
) -> dict:
    """
    Call LLM and parse the response as JSON.
    Returns `fallback` dict on parse failure.
    """
    raw = await llm_chat(
        messages,
        system_prompt=system_prompt,
        temperature=temperature,
        json_mode=True,
    )
    try:
        # Strip markdown code fences if model adds them
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return fallback or {"error": "LLM returned non-JSON", "raw": raw}
