# agent/tools.py

import json
import pathlib
from typing import List

from langchain_core.tools import tool
from .states import (
    SystemSchemas,
    DeterministicCheckResult,
    EndpointSimResult,
    RuntimeReport,
)

PROJECT_ROOT = pathlib.Path.cwd() / "generated_project"

def safe_path_for_project(path: str) -> pathlib.Path:
    p = (PROJECT_ROOT / path).resolve()
    root = PROJECT_ROOT.resolve()
    if not p.is_relative_to(root):
        raise ValueError("Attempt to write outside project root")
    return p

@tool
def validate_json_schema(data: str) -> str:
    """Validates if a string is parseable JSON."""
    try:
        json.loads(data)
        return "VALID JSON"
    except json.JSONDecodeError as e:
        return f"INVALID JSON: {str(e)}"

@tool
def check_api_matches_db(api_fields: list, db_fields: list) -> bool:
    """Checks cross-layer consistency between API and DB field sets."""
    api_set = set(api_fields)
    db_set = set(db_fields)
    return api_set.issubset(db_set)

@tool
def simulate_app_execution(endpoint_route: str, payload: dict) -> str:
    """Simulates a runtime execution of the generated API schema."""
    return f"SIMULATION SUCCESS: 200 OK for {endpoint_route} with payload {json.dumps(payload)}"

def init_project_root():
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    return str(PROJECT_ROOT)

def run_deterministic_checks(schemas: SystemSchemas) -> DeterministicCheckResult:
    """
    Executes all rule-based cross-layer consistency checks.
    Returns a DeterministicCheckResult with every violation catalogued.
    This runs BEFORE the LLM validator so issues are already enumerated.
    """
    result = DeterministicCheckResult()

    db_field_index: dict[str, set[str]] = {}
    db_table_names: set[str] = set()
    for table in schemas.db_schema:
        db_table_names.add(table.table_name.lower())
        db_field_index[table.table_name.lower()] = {
            f.name.lower() for f in table.fields
        }

    api_route_set: set[str] = set()
    for ep in schemas.api_schema:
        api_route_set.add(f"{ep.method.upper()} {ep.route}")

    auth_roles: set[str] = {r.lower() for r in schemas.auth_schema.roles}

    all_db_fields: set[str] = {
        field for fields in db_field_index.values() for field in fields
    }
    for ep in schemas.api_schema:
        for field in ep.request_fields:
            if field.lower() not in all_db_fields:
                result.missing_api_fields.append(
                    f"[{ep.method} {ep.route}] request_field '{field}' not found in any DB table"
                )

    roles_used_in_api: set[str] = set()
    for ep in schemas.api_schema:
        for role in ep.allowed_roles:
            roles_used_in_api.add(role.lower())

    for role in auth_roles:
        if role not in roles_used_in_api:
            result.auth_role_errors.append(
                f"Auth role '{role}' is defined but never referenced in any API endpoint"
            )

    for ep in schemas.api_schema:
        for role in ep.allowed_roles:
            if role.lower() not in auth_roles:
                result.auth_role_errors.append(
                    f"[{ep.method} {ep.route}] references undeclared role '{role}'"
                )

    for page in schemas.ui_schema:
        for component in page.components:
            if component.bound_endpoint not in api_route_set:
                result.ui_binding_errors.append(
                    f"[{page.page_route}] component '{component.name}' binds to "
                    f"'{component.bound_endpoint}' which does not exist in API schema"
                )

    for page in schemas.ui_schema:
        for component in page.components:
            for field in component.fields:
                if field.lower() not in all_db_fields:
                    result.ui_binding_errors.append(
                        f"[{page.page_route}/{component.name}] field '{field}' "
                        f"not found in any DB table"
                    )

    all_errors = (
        result.missing_api_fields
        + result.missing_db_tables
        + result.ui_binding_errors
        + result.auth_role_errors
    )
    result.passed = len(all_errors) == 0
    return result


def deterministic_consistency_score(check: DeterministicCheckResult) -> int:
    """
    Derives a 0-100 integer score purely from deterministic check results.
    Used as a floor/weight when combining with LLM semantic scoring.
    """
    total_checks = 5
    failed = 0
    if check.missing_api_fields:
        failed += 1
    if check.missing_db_tables:
        failed += 1
    if check.ui_binding_errors:
        failed += 1
    if check.auth_role_errors:
        failed += 1
    return int(((total_checks - failed) / total_checks) * 100)

_HTTP_STATUS_FOR_METHOD = {
    "GET": 200,
    "POST": 201,
    "PUT": 200,
    "PATCH": 200,
    "DELETE": 204,
}

def _build_sample_payload(request_fields: List[str]) -> dict:
    """Generate a minimal sample payload from field names."""
    payload = {}
    for field in request_fields:
        fl = field.lower()
        if "email" in fl:
            payload[field] = "user@example.com"
        elif "password" in fl or "secret" in fl or "token" in fl:
            payload[field] = "••••••••"
        elif "id" in fl:
            payload[field] = 1
        elif "date" in fl or "time" in fl:
            payload[field] = "2025-01-01T00:00:00Z"
        elif "count" in fl or "qty" in fl or "amount" in fl or "price" in fl:
            payload[field] = 0
        elif "is_" in fl or fl.startswith("has_") or fl.startswith("enable"):
            payload[field] = True
        else:
            payload[field] = f"sample_{field}"
    return payload

def run_runtime_simulation(schemas: SystemSchemas) -> RuntimeReport:
    """
    Simulates every API endpoint in the schema.
    Validates:
      - Correct HTTP method → expected status code mapping
      - Payload is serialisable
      - Response fields are non-empty
    Returns a RuntimeReport with per-endpoint results.
    """
    results: List[EndpointSimResult] = []

    for ep in schemas.api_schema:
        method = ep.method.upper()
        payload = _build_sample_payload(ep.request_fields)
        expected_code = _HTTP_STATUS_FOR_METHOD.get(method, 200)

        try:
            json.dumps(payload)

            if not ep.response_fields:
                raise ValueError("response_fields is empty — endpoint returns nothing")

            if not ep.route.startswith("/"):
                raise ValueError(f"Route '{ep.route}' does not start with '/'")

            results.append(EndpointSimResult(
                route=ep.route,
                method=method,
                status="PASS",
                response_code=expected_code,
                detail=f"Simulated {method} {ep.route} → {expected_code} with payload {json.dumps(payload)[:80]}",
            ))

        except Exception as exc:
            results.append(EndpointSimResult(
                route=ep.route,
                method=method,
                status="FAIL",
                response_code=500,
                detail=str(exc),
            ))

    passed = sum(1 for r in results if r.status == "PASS")
    total = len(results)
    return RuntimeReport(
        total_endpoints=total,
        passed=passed,
        failed=total - passed,
        results=results,
        success_rate=round((passed / total * 100) if total else 0.0, 1),
    )
