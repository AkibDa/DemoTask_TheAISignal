# agent/prompt.py

def intent_extractor_prompt(user_prompt: str) -> str:
    return f"""
You are the INTENT EXTRACTOR compiler pass. Convert the raw user prompt into a structured IntentIR.

RULES:
- Never invent features not requested or logically required.
- Identify all implicit user roles.
- If the prompt is vague, populate the 'assumptions' field explicitly (e.g. "Assuming JWT auth", "Assuming Stripe for payments").
- Output valid JSON only matching the schema.

User request:
{user_prompt}
"""

def architecture_designer_prompt(intent_ir: str) -> str:
    return f"""
You are the ARCHITECTURE DESIGNER compiler pass.
Based on the following IntentIR, generate the System Architecture IR (Entities, Pages, Workflows).

RULES:
- Entities must represent physical database tables later.
- Pages must align with the target users; include `allowed_roles` for each page.
- Workflows must connect Pages and Entities.
- Maintain deterministic entity naming (PascalCase for Entities).

Intent IR:
{intent_ir}
"""

def schema_generator_prompt(architecture_ir: str) -> str:
    return f"""
You are the SCHEMA GENERATOR compiler pass.
Translate the Architecture IR into strict, interconnected system schemas (DB, API, UI, Auth).

CRITICAL RULES:
1. DB: Every Entity in the Architecture IR must become a TableSchema. Use snake_case for field names.
2. API: Every endpoint's `request_fields` MUST exactly match field names that exist in at least one DB TableSchema.
3. API: Every endpoint MUST declare `allowed_roles` drawn only from the AuthSchema roles list.
4. UI: Every UIComponent MUST have a `bound_endpoint` referencing an existing "METHOD /route" string (e.g. "POST /auth/login").
5. UI: Every UIComponent `fields` list MUST only contain field names that exist in the DB schema.
6. Auth: Every role declared in AuthSchema MUST be referenced in at least one API endpoint's `allowed_roles`.

Failure to follow these rules will trigger the repair engine.

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
