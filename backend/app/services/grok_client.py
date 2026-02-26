"""
grok_client.py — Groq LLM client via direct httpx REST calls.

Uses the Groq cloud API (https://api.groq.com) with the GROQ_API_KEY from .env.
We use httpx directly instead of the groq/openai SDKs to avoid Python 3.11
compatibility issues with those packages.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_API_KEY = os.getenv("GROQ_API_KEY", os.getenv("GROK_API_KEY", ""))
_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"


class _GrokCompletion:
    """Minimal chat completion wrapper over httpx — same interface as openai SDK."""

    def create(self, *, model: str = _DEFAULT_MODEL, messages: list, temperature: float = 0):
        headers = {
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Mimic openai response structure so callers don't need to change
        class _Msg:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.message = _Msg(content)

        class _Response:
            pass

        response = _Response()
        response.choices = [_Choice(data["choices"][0]["message"]["content"])]
        return response


class _GrokChat:
    def __init__(self):
        self.completions = _GrokCompletion()


class _GrokClient:
    def __init__(self):
        self.chat = _GrokChat()


# Single exported instance — used by intent_agent and any other agent needing LLM
grok_client = _GrokClient()