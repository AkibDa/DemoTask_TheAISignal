# agent/graph.py

import json
from typing import TypedDict, Optional, Dict, List
from dotenv import load_dotenv
from langchain_core.globals import set_verbose, set_debug
from langgraph.graph import StateGraph, END

from .prompt import (
    intent_extractor_prompt,
    architecture_designer_prompt,
    db_schema_prompt,
    api_schema_prompt,
    auth_schema_prompt,
    ui_schema_prompt,
    validator_prompt,
    repair_engine_prompt,
    db_repair_prompt,
    api_repair_prompt,
    auth_repair_prompt,
    ui_repair_prompt,
)
from .states import (
    IntentIR, ArchitectureIR, SystemSchemas,
    TableSchema, EndpointSchema, UISchema, AuthSchema,
    ValidationReport, RepairPlan, RuntimeReport,
    DeterministicCheckResult,
)
from .tools import (
    run_deterministic_checks,
    deterministic_consistency_score,
    run_runtime_simulation,
)
from .config import invoke_with_retry

_ = load_dotenv()
set_debug(False)
set_verbose(False)


def _call(schema, prompt: str, label: str = ""):
  """Single wrapper for tracing local model calls."""
  if label:
    print(f"    → {label} [⚡ Local/Ollama]…")
  return invoke_with_retry(schema, prompt)


def _log(state: dict, msg: str) -> None:
  state.setdefault("pipeline_log", []).append(msg)
  print(msg)


def _apply_patches(schemas: SystemSchemas, plan: RepairPlan) -> None:
  """Deterministically mutates the schema state based on LLM patch instructions."""
  from .states import EndpointSchema, TableField

  valid_ops = {"add_field", "remove_field", "add_endpoint", "remove_endpoint", "add_role", "remove_role",
               "bind_component", "bind_role_to_endpoint"}

  for patch in plan.patches:
    op = patch.operation.lower()
    target = patch.target_table_or_route

    if op not in valid_ops:
      print(f"    [PATCH WARNING] LLM tried to use unsupported operation: '{op}'")
      continue

    if op == "remove_role":
      if target in schemas.auth_schema.roles:
        schemas.auth_schema.roles.remove(target)
    elif op == "add_role":
      if patch.field_name and patch.field_name not in schemas.auth_schema.roles:
        schemas.auth_schema.roles.append(patch.field_name)

    elif op == "add_field":
      for table in schemas.db_schema:
        if table.table_name.lower() == target.lower():
          if not any(f.name == patch.field_name for f in table.fields):
            table.fields.append(TableField(
              name=patch.field_name,
              type=patch.field_type or "string",
              required=False
            ))
    elif op == "remove_field":
      for table in schemas.db_schema:
        if table.table_name.lower() == target.lower():
          table.fields = [f for f in table.fields if f.name != patch.field_name]

    elif op == "add_endpoint":
      parts = target.split(" ")
      method = parts[0].upper() if len(parts) > 1 else "GET"
      route = parts[1] if len(parts) > 1 else target

      if not any(e.method == method and e.route == route for e in schemas.api_schema):
        schemas.api_schema.append(EndpointSchema(
          method=method,
          route=route,
          description=patch.reason,
          request_fields=[],
          response_fields=["message"],
          allowed_roles=[]
        ))
    elif op == "remove_endpoint":
      parts = target.split(" ")
      if len(parts) == 2:
        schemas.api_schema = [e for e in schemas.api_schema if not (e.method == parts[0] and e.route == parts[1])]

    elif op == "bind_component":
      for page in schemas.ui_schema:
        if page.page_route == target:
          for comp in page.components:
            if comp.name == patch.field_name:
              comp.bound_endpoint = patch.field_type

    elif op == "bind_role_to_endpoint":
      parts = target.split(" ")
      if len(parts) >= 2:
        method = parts[0].upper()
        route = parts[1]
        for ep in schemas.api_schema:
          if ep.method == method and ep.route == route:
            if patch.field_name and patch.field_name not in ep.allowed_roles:
              ep.allowed_roles.append(patch.field_name)

def _sanitize_roles(roles: list[str]) -> list[str]:
    """Deterministically strips actions/verbs from role arrays."""
    invalid_prefixes = (
      "create", "track", "approve", "manage", "view",
      "edit", "delete", "update", "enroll", "process"
    )
    clean_roles = set()

    for r in roles:
      r_lower = r.lower().strip()

      if "_" in r_lower or " " in r_lower:
        continue

      if any(r_lower.startswith(prefix) for prefix in invalid_prefixes):
        continue

      if len(r_lower) > 2:
        clean_roles.add(r_lower)

    if not clean_roles:
      return ["admin", "user"]

    return list(clean_roles)

class AgentState(TypedDict):
    user_prompt: str
    intent_ir: Optional[IntentIR]
    architecture_ir: Optional[ArchitectureIR]
    system_schemas: Optional[SystemSchemas]
    validation_report: Optional[ValidationReport]
    deterministic_check: Optional[DeterministicCheckResult]
    repair_plan: Optional[RepairPlan]
    repair_history: List[str]
    runtime_report: Optional[RuntimeReport]
    status: Optional[str]
    metrics: Dict[str, int]
    pipeline_log: List[str]
    previous_score: int
    escalate_repair: bool


def intent_extractor_node(state: AgentState) -> AgentState:
  new_state = dict(state)
  new_state.setdefault("metrics", {"repairs": 0, "retries": 0})
  new_state.setdefault("pipeline_log", [])
  new_state.setdefault("repair_history", [])
  _log(new_state, "\n--- [PASS 1] INTENT EXTRACTOR ---")

  resp = _call(IntentIR, intent_extractor_prompt(new_state["user_prompt"]), "extracting intent")
  new_state["intent_ir"] = resp
  new_state["status"] = "INTENT_EXTRACTED"
  _log(new_state, f"✓ Intent: {resp.app_type} | roles={resp.roles} | assumptions={len(resp.assumptions)}")
  return new_state

def intent_sanitizer_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 1.5] INTENT SANITIZER ---")

    ir = new_state["intent_ir"]
    original_roles = ir.roles.copy()

    ir.roles = _sanitize_roles(ir.roles)

    if set(ir.roles) != set(original_roles):
      _log(new_state, f"  ⚠ Sanitized dirty roles: {original_roles} -> {ir.roles}")
    else:
      _log(new_state, f"  ✓ Roles are clean: {ir.roles}")

    new_state["intent_ir"] = ir
    new_state["status"] = "INTENT_SANITIZED"

    return new_state

def architecture_designer_node(state: AgentState) -> AgentState:
  new_state = dict(state)
  _log(new_state, "\n--- [PASS 2] ARCHITECTURE DESIGNER ---")
  ir_json = new_state["intent_ir"].model_dump_json(indent=2)

  # Route to cheap local model
  resp: ArchitectureIR = _call(
    ArchitectureIR, architecture_designer_prompt(ir_json), "designing architecture"
  )

  resp.entities = resp.entities[:6]
  resp.pages = resp.pages[:8]
  resp.workflows = resp.workflows[:5]

  new_state["architecture_ir"] = resp
  new_state["status"] = "ARCHITECTURE_DESIGNED"
  _log(new_state, (
    f"✓ Architecture: {len(resp.entities)} entities | "
    f"{len(resp.pages)} pages | {len(resp.workflows)} workflows"
  ))
  return new_state

def schema_generator_node(state: AgentState) -> AgentState:
  new_state = dict(state)
  arch_json = new_state["architecture_ir"].model_dump_json(indent=2)

  repair_target = None
  if new_state.get("repair_plan"):
    repair_target = new_state["repair_plan"].target_layer
    _log(new_state, f"\n--- [PASS 3] SCHEMA GENERATOR (Targeted Patch: {repair_target}) ---")
  else:
    _log(new_state, "\n--- [PASS 3] SCHEMA GENERATOR (split calls) ---")

  existing_schemas = new_state.get("system_schemas")

  from pydantic import BaseModel
  class _DBOnly(BaseModel):
    db_schema: List[TableSchema]

  class _AuthOnly(BaseModel):
    auth_schema: AuthSchema

  class _APIOnly(BaseModel):
    api_schema: List[EndpointSchema]

  class _UIOnly(BaseModel):
    ui_schema: List[UISchema]

  if not existing_schemas or repair_target in ("DB", "Cross-Layer"):
    db_result = _call(_DBOnly, db_schema_prompt(arch_json), "generating DB schema")
    db_schema = db_result.db_schema
    _log(new_state, f"  ✓ DB: {len(db_schema)} tables (Regenerated)")
  else:
    db_schema = existing_schemas.db_schema
    _log(new_state, "  ✓ DB: [Cached]")

  if not existing_schemas or repair_target in ("Auth", "Cross-Layer"):
    auth_result = _call(_AuthOnly, auth_schema_prompt(arch_json), "generating Auth schema")
    auth_schema = auth_result.auth_schema
    _log(new_state, f"  ✓ Auth: {len(auth_schema.roles)} roles (Regenerated)")
  else:
    auth_schema = existing_schemas.auth_schema
    _log(new_state, "  ✓ Auth: [Cached]")

  db_json = json.dumps([t.model_dump() for t in db_schema], indent=2)

  if not existing_schemas or repair_target in ("API", "Cross-Layer"):
    api_result = _call(_APIOnly, api_schema_prompt(arch_json, db_json), "generating API schema")
    api_schema = api_result.api_schema
    _log(new_state, f"  ✓ API: {len(api_schema)} endpoints (Regenerated)")
  else:
    api_schema = existing_schemas.api_schema
    _log(new_state, "  ✓ API: [Cached]")

  api_json = json.dumps([e.model_dump() for e in api_schema], indent=2)

  if not existing_schemas or repair_target in ("UI", "Cross-Layer"):
    ui_result = _call(_UIOnly, ui_schema_prompt(arch_json, api_json, db_json), "generating UI schema")
    ui_schema = ui_result.ui_schema
    _log(new_state, f"  ✓ UI: {len(ui_schema)} pages (Regenerated)")
  else:
    ui_schema = existing_schemas.ui_schema
    _log(new_state, "  ✓ UI: [Cached]")

  new_state["system_schemas"] = SystemSchemas(
    db_schema=db_schema,
    api_schema=api_schema,
    ui_schema=ui_schema,
    auth_schema=auth_schema,
  )

  new_state["repair_plan"] = None
  new_state["status"] = "SCHEMAS_GENERATED"
  return new_state

def validator_node(state: AgentState) -> AgentState:
  new_state = dict(state)
  _log(new_state, "\n--- [PASS 4] SCHEMA VALIDATOR ---")
  schemas = new_state["system_schemas"]

  det_check = run_deterministic_checks(schemas)
  new_state["deterministic_check"] = det_check
  det_score = deterministic_consistency_score(det_check)
  _log(new_state, f"  [DET] Score: {det_score}/100 | passed={det_check.passed}")

  det_summary = (
    f"Deterministic score: {det_score}/100\n"
    f"Missing API fields  : {det_check.missing_api_fields or 'none'}\n"
    f"UI binding errors   : {det_check.ui_binding_errors or 'none'}\n"
    f"Auth role errors    : {det_check.auth_role_errors or 'none'}\n"
    f"Missing DB tables   : {det_check.missing_db_tables or 'none'}"
  )
  resp: ValidationReport = _call(
    ValidationReport,
    validator_prompt(schemas.model_dump_json(indent=2), det_summary),
    "running semantic validation"
  )
  resp.deterministic_check = det_check

  blended = int((det_score * 0.8) + (resp.consistency_score * 0.2))
  resp.consistency_score = blended
  new_state["validation_report"] = resp

  current_score = blended
  previous_score = new_state.get("previous_score", 0)

  new_state["escalate_repair"] = False
  repairs = new_state.get("metrics", {}).get("repairs", 0)

  if repairs > 0 and current_score <= previous_score:
    _log(new_state, f"  ⚠ Score stalled at {current_score}. Escalating next repair to Cross-Layer.")
    new_state["escalate_repair"] = True

  new_state["previous_score"] = current_score

  if resp.is_valid and blended > 75 and det_check.passed:
    new_state["status"] = "VALIDATION_PASSED"
    _log(new_state, f"✓ Validation PASSED (score={blended})")
  else:
    new_state["status"] = "VALIDATION_FAILED"
    _log(new_state, f"✗ Validation FAILED (score={blended}, issues={len(resp.issues)})")

  return new_state

def _dominant_layer(state: AgentState) -> str:
    det = state.get("deterministic_check")
    if det:
        if det.missing_db_tables:   return "DB"
        if det.missing_api_fields:  return "API"
        if det.auth_role_errors:    return "Auth"
        if det.ui_binding_errors:   return "UI"
    report = state.get("validation_report")
    if report and report.issues:
        order = {"high": 0, "medium": 1, "low": 2}
        top = sorted(report.issues, key=lambda i: order.get(i.severity, 3))[0]
        return top.layer
    return "Cross-Layer"

def repair_engine_node(state: AgentState) -> AgentState:
  new_state = dict(state)
  if new_state.get("escalate_repair"):
    target = "Cross-Layer"
    new_state["escalate_repair"] = False  # reset flag
    _log(new_state, f"\n--- [REPAIR] ESCALATION TRIGGERED → layer: {target} ---")
  else:
    target = _dominant_layer(new_state)
    _log(new_state, f"\n--- [REPAIR] APPLYING PATCHES → layer: {target} ---")

  schemas = new_state["system_schemas"]
  schemas_json = schemas.model_dump_json(indent=2)
  report_json = new_state["validation_report"].model_dump_json(indent=2)
  det = new_state.get("deterministic_check")

  issues_str = report_json
  if det:
    layer_issues = {
      "DB": det.missing_db_tables,
      "API": det.missing_api_fields,
      "Auth": det.auth_role_errors,
      "UI": det.ui_binding_errors,
    }.get(target, [])
    if layer_issues:
      issues_str = "\n".join(layer_issues)

  prompt_map = {
    "DB": db_repair_prompt(schemas_json, issues_str),
    "API": api_repair_prompt(schemas_json, issues_str),
    "Auth": auth_repair_prompt(schemas_json, issues_str),
    "UI": ui_repair_prompt(schemas_json, issues_str),
  }
  prompt = prompt_map.get(target, repair_engine_prompt(schemas_json, report_json, target))

  resp: RepairPlan = _call(RepairPlan, prompt, f"generating patches for {target}")

  _apply_patches(schemas, resp)

  new_state["system_schemas"] = schemas
  new_state["repair_plan"] = resp
  new_state["metrics"]["repairs"] += 1

  entry = (
    f"Repair #{new_state['metrics']['repairs']}: "
    f"Layer={target} | Applied {len(resp.patches)} Patches | {resp.explanation[:80]}"
  )
  new_state["repair_history"].append(entry)
  new_state["status"] = "REPAIR_APPLIED"
  _log(new_state, f"✓ {entry}")

  return new_state

def runtime_executor_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 5] RUNTIME EXECUTOR ---")

    runtime_report = run_runtime_simulation(new_state["system_schemas"])
    new_state["runtime_report"] = runtime_report

    _log(new_state, (
        f"✓ Runtime: {runtime_report.passed}/{runtime_report.total_endpoints} "
        f"endpoints PASS ({runtime_report.success_rate}%)"
    ))
    for r in runtime_report.results:
        if r.status == "FAIL":
            _log(new_state, f"  ⚠ FAIL [{r.method} {r.route}] → {r.detail}")

    cur = new_state.get("status", "")
    if cur == "VALIDATION_PASSED":
        new_state["status"] = "COMPILATION_COMPLETE"
    _log(new_state, f"\n🏁 Compilation finished → {new_state['status']}")
    return new_state


def validation_router(state: AgentState) -> str:
  if state.get("status") == "VALIDATION_PASSED":
    return "runtime_executor"

  repairs = state.get("metrics", {}).get("repairs", 0)

  if repairs >= 3:
    return "runtime_executor"

  return "repair_engine"

def schema_sync_node(state: AgentState) -> AgentState:
  new_state = dict(state)
  _log(new_state, "\n--- [SYNC] SYNCHRONIZING DEPENDENCIES ---")
  schemas = new_state["system_schemas"]

  valid_db_fields = {f.name.lower() for t in schemas.db_schema for f in t.fields}
  valid_endpoints = {f"{e.method.upper()} {e.route}" for e in schemas.api_schema}
  valid_roles = set(schemas.auth_schema.roles)

  for ep in schemas.api_schema:
    ep.request_fields = [f for f in ep.request_fields if f.lower() in valid_db_fields]
    ep.allowed_roles = [r for r in ep.allowed_roles if r in valid_roles]

  for page in schemas.ui_schema:
    for comp in page.components:
      if comp.bound_endpoint and comp.bound_endpoint not in valid_endpoints:
        comp.bound_endpoint = "UNBOUND"
      comp.fields = [f for f in comp.fields if f.lower() in valid_db_fields]

  new_state["system_schemas"] = schemas
  new_state["status"] = "SCHEMAS_SYNCHRONIZED"
  _log(new_state, "  ✓ Downstream dependencies resolved and cleaned.")

  return new_state

graph = StateGraph(AgentState)
graph.add_node("intent_extractor",      intent_extractor_node)
graph.add_node("intent_sanitizer",      intent_sanitizer_node)
graph.add_node("architecture_designer", architecture_designer_node)
graph.add_node("schema_generator",      schema_generator_node)
graph.add_node("validator",             validator_node)
graph.add_node("repair_engine",         repair_engine_node)
graph.add_node("schema_sync",           schema_sync_node)
graph.add_node("runtime_executor",      runtime_executor_node)

graph.set_entry_point("intent_extractor")
graph.add_edge("intent_extractor",      "intent_sanitizer")
graph.add_edge("intent_sanitizer",      "architecture_designer")
graph.add_edge("architecture_designer", "schema_generator")
graph.add_edge("schema_generator",      "validator")

graph.add_conditional_edges(
    "validator", validation_router,
    {"runtime_executor": "runtime_executor", "repair_engine": "repair_engine"},
)

graph.add_edge("repair_engine", "schema_sync")
graph.add_edge("schema_sync", "validator")
graph.add_edge("runtime_executor", END)

agent = graph.compile()
