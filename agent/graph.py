# agent/graph.py

import pathlib
from typing import TypedDict, Optional, Dict
from dotenv import load_dotenv
from langchain_core.globals import set_verbose, set_debug
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

from .prompt import *
from .states import *
from .tools import *
from .utility import *

_ = load_dotenv()
set_debug(True)
set_verbose(True)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=3,
    timeout=60
),

class AgentState(TypedDict):
  user_prompt: str
  intent_ir: Optional[IntentIR]
  architecture_ir: Optional[ArchitectureIR]
  system_schemas: Optional[SystemSchemas]
  validation_report: Optional[ValidationReport]
  repair_plan: Optional[RepairPlan]
  status: Optional[str]
  metrics: Dict[str, int]

def intent_extractor_node(state: AgentState) -> AgentState:
  print("\n--- [PASS 1] INTENT EXTRACTOR ---")
  new_state = dict(state)
  new_state.setdefault("metrics", {"repairs": 0, "retries": 0})

  resp = invoke_structured(llm, IntentIR, intent_extractor_prompt(new_state["user_prompt"]))
  new_state["intent_ir"] = resp
  new_state["status"] = "INTENT_EXTRACTED"
  return new_state

def architecture_designer_node(state: AgentState) -> AgentState:
  print("\n--- [PASS 2] ARCHITECTURE DESIGNER ---")
  new_state = dict(state)
  ir_json = new_state["intent_ir"].model_dump_json(indent=2)

  resp = invoke_structured(llm, ArchitectureIR, architecture_designer_prompt(ir_json))
  new_state["architecture_ir"] = resp
  new_state["status"] = "ARCHITECTURE_DESIGNED"
  return new_state

def schema_generator_node(state: AgentState) -> AgentState:
  print("\n--- [PASS 3] SCHEMA GENERATOR ---")
  new_state = dict(state)
  arch_json = new_state["architecture_ir"].model_dump_json(indent=2)

  resp = invoke_structured(llm, SystemSchemas, schema_generator_prompt(arch_json))
  new_state["system_schemas"] = resp
  new_state["status"] = "SCHEMAS_GENERATED"
  return new_state

def validator_node(state: AgentState) -> AgentState:
  print("\n--- [PASS 4] SCHEMA VALIDATOR ---")
  new_state = dict(state)
  schemas_json = new_state["system_schemas"].model_dump_json(indent=2)

  resp = invoke_structured(llm, ValidationReport, validator_prompt(schemas_json))
  new_state["validation_report"] = resp

  if resp.is_valid and resp.consistency_score > 90:
    new_state["status"] = "VALIDATION_PASSED"
  else:
    new_state["status"] = "VALIDATION_FAILED"
  return new_state

def repair_engine_node(state: AgentState) -> AgentState:
  print("\n--- [REPAIR] REPAIR ENGINE ---")
  new_state = dict(state)
  schemas_json = new_state["system_schemas"].model_dump_json(indent=2)
  report_json = new_state["validation_report"].model_dump_json(indent=2)

  resp = invoke_structured(llm, RepairPlan, repair_engine_prompt(schemas_json, report_json))
  new_state["repair_plan"] = resp
  new_state["metrics"]["repairs"] += 1

  new_state["status"] = "REPAIR_APPLIED"
  return new_state

def runtime_executor_node(state: AgentState) -> AgentState:
  print("\n--- [PASS 5] RUNTIME EXECUTOR ---")
  new_state = dict(state)
  new_state["status"] = "READY_FOR_COMPILATION"
  return new_state

graph = StateGraph(AgentState)

graph.add_node("intent_extractor", intent_extractor_node)
graph.add_node("architecture_designer", architecture_designer_node)
graph.add_node("schema_generator", schema_generator_node)
graph.add_node("validator", validator_node)
graph.add_node("repair_engine", repair_engine_node)
graph.add_node("runtime_executor", runtime_executor_node)

graph.set_entry_point("intent_extractor")
graph.add_edge("intent_extractor", "architecture_designer")
graph.add_edge("architecture_designer", "schema_generator")
graph.add_edge("schema_generator", "validator")

graph.add_conditional_edges(
  "validator",
  lambda s: "runtime_executor" if s.get("status") == "VALIDATION_PASSED" else "repair_engine",
  {"runtime_executor": "runtime_executor", "repair_engine": "repair_engine"}
)

graph.add_edge("repair_engine", "schema_generator")
graph.add_edge("runtime_executor", END)

agent = graph.compile()
