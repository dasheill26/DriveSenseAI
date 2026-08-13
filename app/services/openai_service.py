import os
from typing import List, Dict, Optional

from openai import OpenAI


def chat_reply(user_message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found. Put it in .env and restart the server.")

    client = OpenAI(api_key=api_key)

    system_text = (
        "You are DriveSense AI, a helpful automotive diagnostics assistant. "
        "Answer any question the user asks. For vehicle/OBD questions, be practical and step-by-step. "
        "If the user asks about safety, mention when to stop driving (flashing CEL/misfire, overheating, loss of power). "
        "Keep replies clear and helpful."
    )

    msgs = [{"role": "system", "content": system_text}]

    if history:
        for m in history[-12:]:
            role = m.get("role")
            content = m.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                msgs.append({"role": role, "content": content.strip()})

    msgs.append({"role": "user", "content": user_message})

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=msgs
    )

    return resp.output_text.strip()