# agent/prompt.py

def intent_extractor_prompt(user_prompt: str) -> str:
  return f"""
You are the INTENT EXTRACTOR compiler pass. Convert the raw user prompt into a structured IntentIR.

IMPORTANT:
Roles are HUMAN ACTOR TYPES only.

Examples of VALID roles:
- student
- instructor
- admin
- customer

Examples of INVALID roles:
- create_courses
- track_progress
- approve_courses

Features/actions must NEVER appear inside the roles list.

RULES:
- Never invent features not requested or logically required.
- Identify all implicit user roles strictly based on the human actor types above.
- If the prompt is vague, populate the 'assumptions' field explicitly.
- Output valid JSON only matching the schema.

User request:
{user_prompt}
"""

def architecture_designer_prompt(intent_ir: str) -> str:
  return f"""
You are the ARCHITECTURE DESIGNER compiler pass.
Based on the IntentIR below, generate a CONCISE System Architecture IR.

STRUCTURAL MINIMUMS:
For multi-user SaaS or web systems, you MUST include:
- At least one User entity (e.g., 'User', 'Account').
- At least one domain content entity (e.g., 'Course', 'Product', 'Ticket').
- At least one relationship entity if users interact with content (e.g., 'Enrollment', 'Order').

STRICT LIMITS:
- Entities : maximum 6  (only core domain tables)
- Pages    : maximum 8  (group related actions into one page)
- Workflows: maximum 5  (only the primary user journeys)

RULES:
- Entities must represent physical database tables later. Use PascalCase.
- Pages must align with target users; include `allowed_roles`.
- Workflows must connect Pages and Entities.

Intent IR:
{intent_ir}
"""

def db_schema_prompt(architecture_ir: str) -> str:
    return f"""
You are the DB SCHEMA compiler pass.
Generate ONLY the `db_schema` (list of TableSchema objects) for the architecture below.

RULES:
- Every Entity becomes exactly one TableSchema. Use snake_case for field names.
- Include standard fields: id (integer, required), created_at (datetime, required).
- Add only fields that are logically necessary — do not pad.
- Output a JSON array of TableSchema objects only.

Architecture IR:
{architecture_ir}
"""

def api_schema_prompt(architecture_ir: str, db_schema_json: str) -> str:
  return f"""
You are the API SCHEMA compiler pass.
Generate ONLY the `api_schema` (list of EndpointSchema objects).

RULES:
- Every `request_fields` entry MUST be a field name that exists in the DB schema below.
- Include standard CRUD endpoints for each DB table.
- DELETE endpoints MUST return at least one response field (e.g., ["message"]). Do not leave response_fields empty for DELETE.
- Every endpoint MUST declare `allowed_roles` from this list only: roles found in the Architecture IR.
- Use RESTful routes: /resource, /resource/{{id}}.

DB Schema (for field reference):
{db_schema_json}

Architecture IR:
{architecture_ir}
"""

def auth_schema_prompt(architecture_ir: str) -> str:
    return f"""
You are the AUTH SCHEMA compiler pass.
Generate ONLY the `auth_schema` (a single AuthSchema object).

RULES:
- `roles` must match exactly the roles declared in the Architecture IR — no new roles.
- `permissions` maps each role to a list of allowed HTTP method+route strings (e.g. "GET /users").
- Be explicit and complete.
- Output a single AuthSchema JSON object only.

Architecture IR:
{architecture_ir}
"""

def ui_schema_prompt(architecture_ir: str, api_schema_json: str, db_schema_json: str) -> str:
    return f"""
You are the UI SCHEMA compiler pass.
Generate ONLY the `ui_schema` (list of UISchema objects — one per Page in the Architecture IR).

RULES:
- One UISchema per Page.
- Each UIComponent's `bound_endpoint` MUST be a "METHOD /route" string that exists in the API schema below.
- Each UIComponent's `fields` list MUST only contain field names from the DB schema below.
- `state_variables` should reflect what the page needs in client state.
- Output a JSON array of UISchema objects only.

API Schema (for endpoint reference):
{api_schema_json}

DB Schema (for field reference):
{db_schema_json}

Architecture IR:
{architecture_ir}
"""

def validator_prompt(schemas: str, deterministic_summary: str) -> str:
    return f"""
You are the SCHEMA VALIDATOR engine. Perform a semantic cross-layer consistency check.

IMPORTANT: Deterministic rule-based checks have ALREADY been run. Their findings are below.
Your job is to catch SEMANTIC issues the rules cannot detect (e.g. business logic mismatches,
missing workflows, role privilege escalation risks).

Deterministic Check Summary:
{deterministic_summary}

CHECKLIST:
1. Do all API `request_fields` map to a specific `TableField` in the DB?
2. Do all UI `components` bind to an existing EndpointSchema?
3. Are `AuthSchema` roles applied correctly and securely across the API?
4. Are there missing CRUD endpoints for any DB table?
5. Do workflows make logical sense given the entities and pages?

Output a ValidationReport.
- If perfectly consistent (and deterministic checks passed), set `is_valid` to true and `consistency_score` to 100.
- If you find issues, output them with specific `target_layer` fixes.
- Weight your `consistency_score` based on the deterministic findings too.

System Schemas:
{schemas}
"""

def repair_engine_prompt(schemas: str, validation_report: str, target_layer: str) -> str:
    return f"""
You are the REPAIR ENGINE. The Schema Validator found inconsistencies in the {target_layer} layer.
Generate a RepairPlan targeting ONLY the {target_layer} layer.

RULES:
- Do NOT modify layers not mentioned in the validation issues.
- Each patch must be atomic: one operation on one target.
- Operations allowed: 'add_field', 'remove_field', 'add_endpoint', 'add_role', 'bind_component'.
- The `target_table_or_route` must match an existing table name or API route exactly.

Current Schemas:
{schemas}

Validation Report:
{validation_report}
"""

def db_repair_prompt(schemas: str, issues: str) -> str:
    return f"""
You are the DB REPAIR specialist. Fix ONLY database schema issues.
Generate a RepairPlan with `target_layer` = "DB".

Issues to fix:
{issues}

Current Schemas:
{schemas}
"""

def api_repair_prompt(schemas: str, issues: str) -> str:
    return f"""
You are the API REPAIR specialist. Fix ONLY API endpoint schema issues.
Generate a RepairPlan with `target_layer` = "API".

Issues to fix:
{issues}

Current Schemas:
{schemas}
"""

def auth_repair_prompt(schemas: str, issues: str) -> str:
    return f"""
You are the AUTH REPAIR specialist. Fix ONLY authentication/authorization schema issues.
Generate a RepairPlan with `target_layer` = "Auth".

Issues to fix:
{issues}

Current Schemas:
{schemas}
"""

def ui_repair_prompt(schemas: str, issues: str) -> str:
    return f"""
You are the UI REPAIR specialist. Fix ONLY UI schema binding issues.
Generate a RepairPlan with `target_layer` = "UI".

Issues to fix:
{issues}

Current Schemas:
{schemas}
"""
