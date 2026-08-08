import os
import re
import sys
from pathlib import Path

import httpx

# KIT_* bridge — honour config.load_config, keep localfree gemini fallback
sys.path.insert(0, str(Path(__file__).parents[2].resolve()))
from config import load_config

_kit_path, _kit_base_url, _kit_api_key, _kit_model, _kit_mem0 = load_config()

# LOCAL FREE GEMINI CONFIGURATION (V1BETA - GEMINI NATIVE)
LOCAL_URL = os.getenv("LOCAL_FREE_GEMINI_URL", "http://localhost:18000").replace("/v1", "")
API_KEY = os.getenv("LLM_API_KEY") or _kit_api_key or "localfreegemini"
MODEL_NAME = os.getenv("INTAKE_MODEL") or _kit_model or "gemini-3.1-flash-lite"

def clean_llm_response(text: str) -> str:
    """Strips <thought> tags and markdown code blocks."""
    if not text:
        return ""
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thought>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip markdown code blocks if the agent included them
    text = re.sub(r"^```[a-z]*\n", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"\n```$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    return text.strip()

async def call_gemini(prompt: str, system_prompt: str = "You are a senior Bazi engineer. Return ONLY the full updated Python code. No preamble, no explanation, no markdown.") -> str:
    # Build Gemini-native generateContent URL
    url = f"{LOCAL_URL}/v1/models/{MODEL_NAME}:generateContent?key={API_KEY}"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": 0.0
        }
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if "candidates" not in data:
                return f"ERROR: Invalid response structure: {data}"

            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return clean_llm_response(content)
    except Exception as e:
        return f"ERROR: {str(e)}"

def apply_diff(file_path: str, new_content: str):
    """Applies the update to the file."""
    if not new_content or len(new_content) < 10:
        print(f"  [!] Rejecting update for {file_path}: Content too small or empty.")
        return

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
