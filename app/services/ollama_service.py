import json
import os
import urllib.request
import urllib.error


OLLAMA_CHAT_URL = os.environ.get("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

SYSTEM_PROMPT = """You are DriveSense AI — a professional automotive diagnostics assistant.

You help users understand OBD-II trouble codes and vehicle symptoms.
Be accurate, practical, and structured.

When a user asks about a fault code (e.g., P0300, P0420), answer in this format:

1) What it means (plain English)
2) How serious it is (severity + can they drive?)
3) Most likely causes (ranked)
4) Quick checks the user can do (safe, simple)
5) Confirm tests (OBD live data / inspections)
6) Fix options + typical costs (rough ranges; state it varies)
7) What to do next (short step-by-step plan)

Rules:
- Ask at most 1–3 clarifying questions only if needed (engine type, symptoms, when it happens).
- Safety: If flashing CEL, heavy misfire, fuel smell, overheating, loud knocking, severe loss of power:
  advise to stop driving and get it checked.
- Keep answers concise but genuinely useful.
- No fluff. Use bullet points and short headings.
"""


def ollama_chat(user_message: str, history=None, model: str = None, timeout: int = 90) -> str:
    """
    Calls Ollama local model via /api/chat (no streaming).
    history: list of {"role": "user"/"assistant", "content": "..."}
    """
    if history is None:
        history = []
    if model is None:
        model = DEFAULT_MODEL

    # Keep conversation small for speed
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-10:]:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.35,
            "num_ctx": 4096
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            obj = json.loads(raw)
            content = (obj.get("message") or {}).get("content") or ""
            content = content.strip()
            return content if content else "I didn’t get a response. Try again."
    except urllib.error.URLError as e:
        raise RuntimeError(
            "Ollama is not reachable. Make sure it’s running:\n"
            "1) ollama serve\n"
            "2) ollama pull llama3\n"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}") from e