# agent/utility.py

from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage

def _retry_kwargs():
  return dict(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(min=1, max=8),
    reraise=True,
    retry=retry_if_exception_type((
      TimeoutError,
      OutputParserException,
      Exception,
    )),
  )

def _with_retry(func):
  return retry(**_retry_kwargs())(func)

@_with_retry
def invoke_structured(llm, schema, prompt: str):
  return llm.with_structured_output(schema).invoke(prompt)

def repair_structured_output(llm, schema, bad_output: str, error_msg: str):
  """Targeted repair for JSON schema failures."""
  repair_prompt = f"""
    You previously generated an invalid structured output. 
    ERROR: {error_msg}

    PREVIOUS OUTPUT:
    {bad_output}

    Fix the formatting/typing errors and return the valid structured output matching the schema.
    """
  return llm.with_structured_output(schema).invoke(repair_prompt)

@_with_retry
def invoke_messages(agent, messages: list):
  return agent.invoke({"messages": messages})
