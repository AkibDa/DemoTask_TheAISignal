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
from .config import invoke_with_rotation

_ = load_dotenv()
set_debug(False)
set_verbose(False)

def _call(schema, prompt: str, label: str = ""):
    """Single wrapper: key-rotation + a short label for tracing."""
    if label:
        print(f"    → {label}…")
    return invoke_with_rotation(schema, prompt, timeout=90)


def _log(state: dict, msg: str) -> None:
    state.setdefault("pipeline_log", []).append(msg)
    print(msg)

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

def architecture_designer_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 2] ARCHITECTURE DESIGNER ---")
    ir_json = new_state["intent_ir"].model_dump_json(indent=2)

    resp: ArchitectureIR = _call(
        ArchitectureIR, architecture_designer_prompt(ir_json), "designing architecture"
    )

    resp.entities  = resp.entities[:6]
    resp.pages     = resp.pages[:8]
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
    _log(new_state, "\n--- [PASS 3] SCHEMA GENERATOR (split calls) ---")
    arch_json = new_state["architecture_ir"].model_dump_json(indent=2)

    class _DBOnly(TypedDict):
        db_schema: List[TableSchema]

    from pydantic import BaseModel
    class DBOnly(BaseModel):
        db_schema: List[TableSchema]

    db_result: DBOnly = _call(DBOnly, db_schema_prompt(arch_json), "generating DB schema")
    db_json = json.dumps([t.model_dump() for t in db_result.db_schema], indent=2)
    _log(new_state, f"  ✓ DB: {len(db_result.db_schema)} tables")

    class AuthOnly(BaseModel):
        auth_schema: AuthSchema

    auth_result: AuthOnly = _call(AuthOnly, auth_schema_prompt(arch_json), "generating Auth schema")
    _log(new_state, f"  ✓ Auth: {len(auth_result.auth_schema.roles)} roles")

    class APIOnly(BaseModel):
        api_schema: List[EndpointSchema]

    api_result: APIOnly = _call(
        APIOnly,
        api_schema_prompt(arch_json, db_json),
        "generating API schema"
    )
    api_json = json.dumps([e.model_dump() for e in api_result.api_schema], indent=2)
    _log(new_state, f"  ✓ API: {len(api_result.api_schema)} endpoints")

    class UIOnly(BaseModel):
        ui_schema: List[UISchema]

    ui_result: UIOnly = _call(
        UIOnly,
        ui_schema_prompt(arch_json, api_json, db_json),
        "generating UI schema"
    )
    _log(new_state, f"  ✓ UI: {len(ui_result.ui_schema)} pages")

    new_state["system_schemas"] = SystemSchemas(
        db_schema=db_result.db_schema,
        api_schema=api_result.api_schema,
        ui_schema=ui_result.ui_schema,
        auth_schema=auth_result.auth_schema,
    )
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

    blended = int((det_score * 0.5) + (resp.consistency_score * 0.5))
    resp.consistency_score = blended
    new_state["validation_report"] = resp

    if resp.is_valid and blended > 90 and det_check.passed:
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
    target = _dominant_layer(new_state)
    _log(new_state, f"\n--- [REPAIR] REPAIR ENGINE → layer: {target} ---")

    schemas_json = new_state["system_schemas"].model_dump_json(indent=2)
    report_json  = new_state["validation_report"].model_dump_json(indent=2)
    det = new_state.get("deterministic_check")

    issues_str = report_json
    if det:
        layer_issues = {
            "DB":   det.missing_db_tables,
            "API":  det.missing_api_fields,
            "Auth": det.auth_role_errors,
            "UI":   det.ui_binding_errors,
        }.get(target, [])
        if layer_issues:
            issues_str = "\n".join(layer_issues)

    prompt_map = {
        "DB":   db_repair_prompt(schemas_json, issues_str),
        "API":  api_repair_prompt(schemas_json, issues_str),
        "Auth": auth_repair_prompt(schemas_json, issues_str),
        "UI":   ui_repair_prompt(schemas_json, issues_str),
    }
    prompt = prompt_map.get(target, repair_engine_prompt(schemas_json, report_json, target))

    resp: RepairPlan = _call(RepairPlan, prompt, f"repairing {target} layer")
    new_state["repair_plan"] = resp
    new_state["metrics"]["repairs"] += 1

    entry = (
        f"Repair #{new_state['metrics']['repairs']}: "
        f"Layer={target} | Patches={len(resp.patches)} | {resp.explanation[:80]}"
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
        print("\n[ROUTER] Validation passed → runtime executor")
        return "runtime_executor"

    repairs = state.get("metrics", {}).get("repairs", 0)
    if repairs >= 3:
        print(f"\n[ROUTER] ⛔ Circuit breaker — max repairs ({repairs}) reached")
        state["status"] = "VALIDATION_FAILED_MAX_RETRIES"
        return "runtime_executor"

    print(f"\n[ROUTER] Validation failed — repair cycle {repairs + 1}/3 …")
    return "repair_engine"

graph = StateGraph(AgentState)
graph.add_node("intent_extractor",      intent_extractor_node)
graph.add_node("architecture_designer", architecture_designer_node)
graph.add_node("schema_generator",      schema_generator_node)
graph.add_node("validator",             validator_node)
graph.add_node("repair_engine",         repair_engine_node)
graph.add_node("runtime_executor",      runtime_executor_node)

graph.set_entry_point("intent_extractor")
graph.add_edge("intent_extractor",      "architecture_designer")
graph.add_edge("architecture_designer", "schema_generator")
graph.add_edge("schema_generator",      "validator")
graph.add_conditional_edges(
    "validator", validation_router,
    {"runtime_executor": "runtime_executor", "repair_engine": "repair_engine"},
)
graph.add_edge("repair_engine",    "schema_generator")
graph.add_edge("runtime_executor", END)

agent = graph.compile()
