# agent/states.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class IntentIR(BaseModel):
    app_type: str = Field(description="Core type of application (e.g. 'E-commerce', 'SaaS', 'Internal Tool')")
    users: List[str] = Field(description="Target users of the system")
    roles: List[str] = Field(description="System roles (e.g. 'admin', 'guest')")
    features: List[str] = Field(description="Core functional requirements")
    business_rules: List[str] = Field(description="Strict rules the system must follow")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made if the prompt was vague")

class Entity(BaseModel):
    name: str = Field(description="Domain entity name in PascalCase (e.g. 'User', 'Order')")
    description: str

class Page(BaseModel):
    name: str
    route: str
    description: str
    allowed_roles: List[str] = Field(default_factory=list, description="Roles allowed to access this page")

class Workflow(BaseModel):
    name: str
    steps: List[str]

class ArchitectureIR(BaseModel):
    entities: List[Entity]
    pages: List[Page]
    workflows: List[Workflow]

class TableField(BaseModel):
    name: str
    type: str
    required: bool

class TableSchema(BaseModel):
    table_name: str
    fields: List[TableField]

class EndpointSchema(BaseModel):
    method: str
    route: str
    description: str
    request_fields: List[str]
    response_fields: List[str]
    allowed_roles: List[str] = Field(default_factory=list, description="Roles permitted to call this endpoint")

class UIComponent(BaseModel):
    name: str = Field(description="Component name (e.g. 'LoginForm')")
    bound_endpoint: str = Field(description="API route this component calls (e.g. 'POST /auth/login')")
    fields: List[str] = Field(default_factory=list, description="Form fields or display fields used")

class UISchema(BaseModel):
    page_route: str
    components: List[UIComponent]
    state_variables: List[str]

class AuthSchema(BaseModel):
    roles: List[str]
    permissions: Dict[str, List[str]] = Field(description="Mapping of roles to allowed actions/routes")

class SystemSchemas(BaseModel):
    db_schema: List[TableSchema]
    api_schema: List[EndpointSchema]
    ui_schema: List[UISchema]
    auth_schema: AuthSchema

class ValidationIssue(BaseModel):
    severity: str = Field(description="'high', 'medium', or 'low'")
    layer: str = Field(description="'UI', 'API', 'DB', 'Auth', or 'Cross-Layer'")
    issue: str
    suggested_fix: str

class DeterministicCheckResult(BaseModel):
    """Results from rule-based Python validators (not LLM)."""
    missing_api_fields: List[str] = Field(default_factory=list)
    missing_db_tables: List[str] = Field(default_factory=list)
    ui_binding_errors: List[str] = Field(default_factory=list)
    auth_role_errors: List[str] = Field(default_factory=list)
    passed: bool = True

class ValidationReport(BaseModel):
    is_valid: bool
    consistency_score: int = Field(ge=0, le=100, description="Score of cross-layer consistency")
    issues: List[ValidationIssue]
    deterministic_check: Optional[DeterministicCheckResult] = None

class SchemaPatch(BaseModel):
    """An atomic, executable patch operation on a specific schema layer."""
    operation: str = Field(description="'add_field', 'remove_field', 'add_endpoint', 'add_role', 'bind_component'")
    target_table_or_route: str = Field(description="The table name or API route being patched")
    field_name: str = Field(default="", description="Field or component name being added/removed")
    field_type: str = Field(default="", description="Data type if adding a field")
    reason: str = Field(description="Why this patch is needed")

class RepairPlan(BaseModel):
    target_layer: str = Field(description="'DB', 'API', 'UI', 'Auth', or 'Cross-Layer'")
    patches: List[SchemaPatch] = Field(description="Structured atomic patch operations")
    explanation: str

class EndpointSimResult(BaseModel):
    route: str
    method: str
    status: str
    response_code: int
    detail: str

class RuntimeReport(BaseModel):
    total_endpoints: int
    passed: int
    failed: int
    results: List[EndpointSimResult]
    success_rate: float
