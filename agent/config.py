# agent/config.py

import time
from typing import Optional
from langchain_ollama import ChatOllama


def get_llm() -> ChatOllama:
  return ChatOllama(
    model="qwen2.5-coder:1.5b",
    temperature=0,
  )


def invoke_with_retry(schema, prompt: str, max_attempts: int = 3):
  last_exc: Optional[Exception] = None
  for attempt in range(1, max_attempts + 1):
    llm = get_llm()

    try:
      return llm.with_structured_output(schema).invoke(prompt)
    except Exception as exc:
      last_exc = exc
      print(f"  [local-retry] Attempt {attempt}/{max_attempts} failed: {exc} — retrying...")
      time.sleep(2)

  raise RuntimeError(
    f"All {max_attempts} attempts failed on the local model. Last error: {last_exc}"
  )
