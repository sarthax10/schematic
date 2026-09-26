"""LLM client. Default backend is a local Ollama server; any OpenAI-compatible server
(LM Studio, llama.cpp's server, vLLM, a hosted API) works too.

No GPU is required anywhere: Ollama uses a GPU when it finds one and falls back to the CPU
on its own. On CPU a 7-8B model is several times slower, so timeouts here are generous
(SCHEMATIC_LLM_TIMEOUT, default 30 min per call) rather than tuned for a GPU.

Configuration (environment):
  SCHEMATIC_LLM        "ollama:<model>" (default "ollama:qwen2.5:7b-instruct") or "openai:<model>"
  OLLAMA_HOST          default http://127.0.0.1:11434
  SCHEMATIC_LLM_BASE_URL / SCHEMATIC_LLM_API_KEY   for "openai:" backends
  SCHEMATIC_NUM_CTX    context window for Ollama (default 16384 — the design prompt is long)
  SCHEMATIC_EMBED_MODEL  Ollama embedding model for duplicate-topic detection (default nomic-embed-text)

    python -m pipeline.llm     # checks the configured backend answers
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import requests


class LLMError(RuntimeError):
    pass


def extract_json(text: str):
    """Parses the first JSON object in a reply (tolerating ```json fences and prose)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        chunk = text[start:end + 1]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            # Common small-model slips: trailing commas.
            return json.loads(re.sub(r",\s*([}\]])", r"\1", chunk))
    raise json.JSONDecodeError("no JSON object found", text, 0)


class LLM:
    def __init__(self, spec: str | None = None):
        spec = spec or os.environ.get("SCHEMATIC_LLM", "ollama:qwen2.5:7b-instruct")
        self.backend, _, self.model = spec.partition(":")
        if self.backend not in ("ollama", "openai") or not self.model:
            raise LLMError(f"SCHEMATIC_LLM must look like 'ollama:<model>' or 'openai:<model>', got {spec!r}")
        self.timeout = int(os.environ.get("SCHEMATIC_LLM_TIMEOUT", "1800"))
        self.ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.base_url = os.environ.get("SCHEMATIC_LLM_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
        self.api_key = os.environ.get("SCHEMATIC_LLM_API_KEY", "")
        self.num_ctx = int(os.environ.get("SCHEMATIC_NUM_CTX", "16384"))
        self.embed_model = os.environ.get("SCHEMATIC_EMBED_MODEL", "nomic-embed-text")
        self.calls = 0

    def __repr__(self):
        return f"{self.backend}:{self.model}"

    # ---- raw chat ------------------------------------------------------------------------
    def chat(self, system: str, user: str, *, schema: dict | None = None, json_mode: bool = True,
             temperature: float = 0.6, max_tokens: int = 4096) -> str:
        self.calls += 1
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            if self.backend == "ollama":
                body = {
                    "model": self.model, "messages": messages, "stream": False,
                    "options": {"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": max_tokens},
                }
                if schema is not None:
                    body["format"] = schema
                elif json_mode:
                    body["format"] = "json"
                r = requests.post(f"{self.ollama}/api/chat", json=body, timeout=self.timeout)
                r.raise_for_status()
                return r.json()["message"]["content"]
            body = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
            if schema is not None:
                body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
            elif json_mode:
                body["response_format"] = {"type": "json_object"}
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            raise LLMError(f"{self} request failed: {e}") from e

    def json(self, system: str, user: str, *, schema: dict | None = None, temperature: float = 0.6,
             max_tokens: int = 4096, retries: int = 2) -> dict:
        """Chat and parse JSON; on a malformed reply, retries with the parse error shown."""
        prompt = user
        last = None
        for attempt in range(retries + 1):
            reply = self.chat(system, prompt, schema=schema, temperature=temperature, max_tokens=max_tokens)
            try:
                out = extract_json(reply)
                if not isinstance(out, dict):
                    raise json.JSONDecodeError("top level is not an object", reply, 0)
                return out
            except json.JSONDecodeError as e:
                last = e
                prompt = f"{user}\n\nYour previous reply was not valid JSON ({e.msg}). Reply with ONLY the JSON object."
                time.sleep(0.5)
        raise LLMError(f"{self} returned invalid JSON after {retries + 1} attempts: {last}")

    # ---- embeddings (optional) ----------------------------------------------------------------
    def embed(self, text: str) -> list[float] | None:
        """Embedding for duplicate-topic detection; None if the backend/model isn't available
        (the library then falls back to keyword overlap alone)."""
        if self.backend != "ollama":
            return None
        try:
            r = requests.post(f"{self.ollama}/api/embed", json={"model": self.embed_model, "input": text}, timeout=120)
            if r.status_code != 200:
                return None
            vecs = r.json().get("embeddings") or []
            return vecs[0] if vecs else None
        except requests.RequestException:
            return None

    def health(self) -> tuple[bool, str]:
        try:
            if self.backend == "ollama":
                r = requests.get(f"{self.ollama}/api/tags", timeout=5)
                r.raise_for_status()
                names = [m["name"] for m in r.json().get("models", [])]
                if self.model not in names and f"{self.model}:latest" not in names:
                    return False, f"Ollama is running but model {self.model!r} isn't pulled. Run: ollama pull {self.model}"
                return True, f"Ollama OK, model {self.model} available ({len(names)} models installed)"
            r = requests.get(f"{self.base_url}/models", timeout=5, headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})
            r.raise_for_status()
            return True, f"OpenAI-compatible server OK at {self.base_url}"
        except requests.RequestException as e:
            where = self.ollama if self.backend == "ollama" else self.base_url
            return False, f"can't reach {self.backend} at {where}: {e.__class__.__name__}"


if __name__ == "__main__":
    llm = LLM()
    ok, msg = llm.health()
    print(f"{llm}: {msg}")
    sys.exit(0 if ok else 1)
