# agent/config.py

import os
import itertools
import threading
import time
from typing import List, Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

_raw_keys: List[str] = []
for _var in ("GOOGLE_API_KEY_1", "GOOGLE_API_KEY_2", "GOOGLE_API_KEY_3"):
    _k = os.getenv(_var, "").strip()
    if _k:
        _raw_keys.append(_k)

if not _raw_keys:
    _default = os.getenv("GOOGLE_API_KEY", "").strip()
    if _default:
        _raw_keys.append(_default)

if not _raw_keys:
    raise EnvironmentError(
        "No Google API key found. Set at least GOOGLE_API_KEY_1 (or GOOGLE_API_KEY) in your .env"
    )

print(f"[config] Loaded {len(_raw_keys)} API key(s) into rotation pool.")

_lock = threading.Lock()
_cycle = itertools.cycle(_raw_keys)

def _next_key() -> str:
    with _lock:
        return next(_cycle)

_RETRYABLE_CODES = {429, 503, 504}

def get_llm(timeout: int = 120) -> ChatGoogleGenerativeAI:
    """
    Returns a ChatGoogleGenerativeAI instance using the next key in the pool.
    Call this once per graph node so each call gets a fresh (possibly different) key.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=_next_key(),
        temperature=0,
        max_retries=2,
        timeout=timeout,
    )

def invoke_with_rotation(schema, prompt: str, max_attempts: int = 6, timeout: int = 120):
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        llm = get_llm(timeout=timeout)
        try:
            return llm.with_structured_output(schema).invoke(prompt)
        except Exception as exc:
            last_exc = exc
            exc_str = str(exc)
            is_retryable = any(
                marker in exc_str
                for marker in ("429", "503", "504", "DEADLINE_EXCEEDED",
                               "RESOURCE_EXHAUSTED", "rate", "quota", "timeout")
            )
            if not is_retryable:
                raise

            wait = min(2 ** attempt, 30)
            key_num = ((attempt - 1) % len(_raw_keys)) + 1
            print(
                f"  [key-pool] Attempt {attempt}/{max_attempts} failed "
                f"(key #{key_num}): {exc_str[:80]} — rotating key, "
                f"retrying in {wait}s…"
            )
            time.sleep(wait)

    raise RuntimeError(
        f"All {max_attempts} attempts failed across {len(_raw_keys)} key(s). "
        f"Last error: {last_exc}"
    )
