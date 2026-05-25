# agent/graph.py

from typing import TypedDict, Optional, Dict, List
from dotenv import load_dotenv
from langchain_core.globals import set_verbose, set_debug
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

from .prompt import (
    intent_extractor_prompt,
    architecture_designer_prompt,
    schema_generator_prompt,
    validator_prompt,
    repair_engine_prompt,
    db_repair_prompt,
    api_repair_prompt,
    auth_repair_prompt,
    ui_repair_prompt,
)
from .states import (
    IntentIR, ArchitectureIR, SystemSchemas,
    ValidationReport, RepairPlan, RuntimeReport,
    DeterministicCheckResult,
)
from .tools import (
    run_deterministic_checks,
    deterministic_consistency_score,
    run_runtime_simulation,
)
from .utility import invoke_structured

_ = load_dotenv()
set_debug(False)
set_verbose(True)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=3,
    timeout=60,
)

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

def _log(state: dict, msg: str) -> None:
    state.setdefault("pipeline_log", []).append(msg)
    print(msg)

def intent_extractor_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    new_state.setdefault("metrics", {"repairs": 0, "retries": 0})
    new_state.setdefault("pipeline_log", [])
    new_state.setdefault("repair_history", [])
    _log(new_state, "\n--- [PASS 1] INTENT EXTRACTOR ---")

    resp = invoke_structured(llm, IntentIR, intent_extractor_prompt(new_state["user_prompt"]))
    new_state["intent_ir"] = resp
    new_state["status"] = "INTENT_EXTRACTED"
    _log(new_state, f"✓ Intent extracted: {resp.app_type} | roles={resp.roles} | assumptions={len(resp.assumptions)}")
    return new_state

def architecture_designer_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 2] ARCHITECTURE DESIGNER ---")
    ir_json = new_state["intent_ir"].model_dump_json(indent=2)

    resp = invoke_structured(llm, ArchitectureIR, architecture_designer_prompt(ir_json))
    new_state["architecture_ir"] = resp
    new_state["status"] = "ARCHITECTURE_DESIGNED"
    _log(new_state, f"✓ Architecture: {len(resp.entities)} entities | {len(resp.pages)} pages | {len(resp.workflows)} workflows")
    return new_state

def schema_generator_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 3] SCHEMA GENERATOR ---")
    arch_json = new_state["architecture_ir"].model_dump_json(indent=2)

    resp = invoke_structured(llm, SystemSchemas, schema_generator_prompt(arch_json))
    new_state["system_schemas"] = resp
    new_state["status"] = "SCHEMAS_GENERATED"
    _log(new_state, (
        f"✓ Schemas: {len(resp.db_schema)} tables | "
        f"{len(resp.api_schema)} endpoints | "
        f"{len(resp.ui_schema)} UI pages | "
        f"{len(resp.auth_schema.roles)} roles"
    ))
    return new_state

def validator_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 4] SCHEMA VALIDATOR ---")
    schemas = new_state["system_schemas"]

    det_check = run_deterministic_checks(schemas)
    new_state["deterministic_check"] = det_check
    det_score = deterministic_consistency_score(det_check)
    _log(new_state, f"  [DET] Deterministic score: {det_score}/100 | passed={det_check.passed}")
    if not det_check.passed:
        _log(new_state, f"  [DET] Issues → API:{det_check.missing_api_fields} | UI:{det_check.ui_binding_errors} | Auth:{det_check.auth_role_errors}")

    det_summary = (
        f"Deterministic score: {det_score}/100\n"
        f"Missing API fields: {det_check.missing_api_fields or 'none'}\n"
        f"UI binding errors: {det_check.ui_binding_errors or 'none'}\n"
        f"Auth role errors: {det_check.auth_role_errors or 'none'}\n"
        f"Missing DB tables: {det_check.missing_db_tables or 'none'}"
    )
    schemas_json = schemas.model_dump_json(indent=2)
    resp: ValidationReport = invoke_structured(
        llm, ValidationReport, validator_prompt(schemas_json, det_summary)
    )
    resp.deterministic_check = det_check

    blended_score = int((det_score * 0.5) + (resp.consistency_score * 0.5))
    resp.consistency_score = blended_score
    new_state["validation_report"] = resp

    if resp.is_valid and blended_score > 90 and det_check.passed:
        new_state["status"] = "VALIDATION_PASSED"
        _log(new_state, f"✓ Validation PASSED (score={blended_score})")
    else:
        new_state["status"] = "VALIDATION_FAILED"
        _log(new_state, f"✗ Validation FAILED (score={blended_score}, issues={len(resp.issues)})")

    return new_state

def _classify_dominant_layer(state: AgentState) -> str:
    """Determine which schema layer needs repair most urgently."""
    det = state.get("deterministic_check")
    if det:
        if det.missing_db_tables:
            return "DB"
        if det.missing_api_fields:
            return "API"
        if det.auth_role_errors:
            return "Auth"
        if det.ui_binding_errors:
            return "UI"

    report = state.get("validation_report")
    if report and report.issues:
        severity_order = {"high": 0, "medium": 1, "low": 2}
        sorted_issues = sorted(report.issues, key=lambda i: severity_order.get(i.severity, 3))
        return sorted_issues[0].layer if sorted_issues else "Cross-Layer"

    return "Cross-Layer"

def repair_engine_node(state: AgentState) -> AgentState:
    """Dispatches repair to the appropriate layer-specific handler."""
    new_state = dict(state)
    target_layer = _classify_dominant_layer(new_state)
    _log(new_state, f"\n--- [REPAIR] REPAIR ENGINE → targeting layer: {target_layer} ---")

    schemas_json = new_state["system_schemas"].model_dump_json(indent=2)
    report_json = new_state["validation_report"].model_dump_json(indent=2)
    det = new_state.get("deterministic_check")

    issues_str = report_json
    if det:
        layer_issues = {
            "DB": det.missing_db_tables,
            "API": det.missing_api_fields,
            "Auth": det.auth_role_errors,
            "UI": det.ui_binding_errors,
        }.get(target_layer, [])
        if layer_issues:
            issues_str = "\n".join(layer_issues)

    prompt_map = {
        "DB":    db_repair_prompt(schemas_json, issues_str),
        "API":   api_repair_prompt(schemas_json, issues_str),
        "Auth":  auth_repair_prompt(schemas_json, issues_str),
        "UI":    ui_repair_prompt(schemas_json, issues_str),
    }
    prompt = prompt_map.get(target_layer, repair_engine_prompt(schemas_json, report_json, target_layer))

    resp: RepairPlan = invoke_structured(llm, RepairPlan, prompt)
    new_state["repair_plan"] = resp
    new_state["metrics"]["repairs"] += 1

    # Audit log
    repair_entry = (
        f"Repair #{new_state['metrics']['repairs']}: "
        f"Layer={target_layer} | Patches={len(resp.patches)} | {resp.explanation[:80]}"
    )
    new_state["repair_history"].append(repair_entry)
    new_state["status"] = "REPAIR_APPLIED"
    _log(new_state, f"✓ {repair_entry}")
    return new_state

def runtime_executor_node(state: AgentState) -> AgentState:
    new_state = dict(state)
    _log(new_state, "\n--- [PASS 5] RUNTIME EXECUTOR ---")
    schemas = new_state["system_schemas"]

    runtime_report = run_runtime_simulation(schemas)
    new_state["runtime_report"] = runtime_report

    _log(new_state, (
        f"✓ Runtime simulation: {runtime_report.passed}/{runtime_report.total_endpoints} endpoints PASS "
        f"({runtime_report.success_rate}%)"
    ))

    if runtime_report.failed > 0:
        _log(new_state, f"  ⚠ {runtime_report.failed} endpoint(s) failed simulation")
        for r in runtime_report.results:
            if r.status == "FAIL":
                _log(new_state, f"    FAIL [{r.method} {r.route}] → {r.detail}")

    final_status = new_state.get("status", "UNKNOWN")
    if final_status == "VALIDATION_PASSED":
        new_state["status"] = "COMPILATION_COMPLETE"
    _log(new_state, f"\n🏁 Compilation finished → {new_state['status']}")
    return new_state

def validation_router(state: AgentState) -> str:
    if state.get("status") == "VALIDATION_PASSED":
        print("\n[ROUTER] Validation passed → runtime executor")
        return "runtime_executor"

    repairs_attempted = state.get("metrics", {}).get("repairs", 0)
    if repairs_attempted >= 3:
        print(f"\n[ROUTER] ⛔ Circuit breaker tripped — max repairs ({repairs_attempted}) reached")
        state["status"] = "VALIDATION_FAILED_MAX_RETRIES"
        return "runtime_executor"

    print(f"\n[ROUTER] Validation failed — initiating repair cycle {repairs_attempted + 1}/3 ...")
    return "repair_engine"

graph = StateGraph(AgentState)

graph.add_node("intent_extractor",        intent_extractor_node)
graph.add_node("architecture_designer",   architecture_designer_node)
graph.add_node("schema_generator",        schema_generator_node)
graph.add_node("validator",               validator_node)
graph.add_node("repair_engine",           repair_engine_node)
graph.add_node("runtime_executor",        runtime_executor_node)

graph.set_entry_point("intent_extractor")
graph.add_edge("intent_extractor",      "architecture_designer")
graph.add_edge("architecture_designer", "schema_generator")
graph.add_edge("schema_generator",      "validator")

graph.add_conditional_edges(
    "validator",
    validation_router,
    {
        "runtime_executor": "runtime_executor",
        "repair_engine":    "repair_engine",
    },
)

graph.add_edge("repair_engine",    "schema_generator")
graph.add_edge("runtime_executor", END)

agent = graph.compile()
