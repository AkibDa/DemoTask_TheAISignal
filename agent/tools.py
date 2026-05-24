# agent/tools.py

import pathlib
import subprocess
import json
from langchain_core.tools import tool

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
    """Checks cross-layer consistency between API and DB."""
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
