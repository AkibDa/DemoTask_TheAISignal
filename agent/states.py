# agent/states.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class IntentIR(BaseModel):
    app_type: str = Field(description="The core type of application (e.g., 'E-commerce', 'SaaS', 'Internal Tool')")
    users: List[str] = Field(description="Target users of the system")
    roles: List[str] = Field(description="System roles (e.g., 'admin', 'guest')")
    features: List[str] = Field(description="Core functional requirements")
    business_rules: List[str] = Field(description="Strict rules the system must follow")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made if the prompt was vague")

class Entity(BaseModel):
    name: str = Field(description="Domain entity name (e.g., 'User', 'Order')")
    description: str

class Page(BaseModel):
    name: str
    route: str
    description: str

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

class UISchema(BaseModel):
    page_route: str
    components: List[str]
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

class ValidationReport(BaseModel):
    is_valid: bool
    consistency_score: int = Field(ge=0, le=100, description="Score of cross-layer consistency")
    issues: List[ValidationIssue]

class RepairPlan(BaseModel):
    target_layer: str
    modifications: List[str]
    explanation: str
