# agent/prompt.py

def intent_extractor_prompt(user_prompt: str) -> str:
    return f"""
You are the INTENT EXTRACTOR compiler pass. Convert the raw user prompt into a structured IntentIR.

RULES:
- Never invent features not requested or logically required.
- Identify all implicit user roles.
- If the prompt is vague, populate the 'assumptions' field explicitly.
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
- Pages must align with the target users.
- Workflows must connect Pages and Entities.
- Maintain deterministic entity naming (e.g., Use PascalCase for Entities).

Intent IR:
{intent_ir}
"""

def schema_generator_prompt(architecture_ir: str) -> str:
    return f"""
You are the SCHEMA GENERATOR compiler pass. 
Translate the Architecture IR into strict, interconnected system schemas (DB, API, UI, Auth).

CRITICAL RULES:
- API fields MUST match DB fields exactly.
- UI forms MUST map to API endpoints.
- Auth roles MUST be referenced in API and UI restrictions.
- Ensure 100% referential integrity across the schemas.

Architecture IR:
{architecture_ir}
"""

def validator_prompt(schemas: str) -> str:
    return f"""
You are the SCHEMA VALIDATOR engine. Perform a cross-layer consistency check on the generated schemas.

CHECKLIST:
1. Do all API `request_fields` map to a specific `TableField` in the DB?
2. Do all UI `components` map to an existing `EndpointSchema`?
3. Are `AuthSchema` roles applied correctly across the API?

Output a ValidationReport. If perfectly consistent, set `is_valid` to true and `consistency_score` to 100.
If you find mismatches, output issues with specific `target_layer` fixes.

System Schemas:
{schemas}
"""

def repair_engine_prompt(schemas: str, validation_report: str) -> str:
    return f"""
You are the REPAIR ENGINE. The Schema Validator found inconsistencies.
Target only the broken layers and generate a RepairPlan.

Current Schemas:
{schemas}

Validation Report:
{validation_report}
"""
