"""
Data models for the Prompt Template Management system.

Defines the template schema, registration/update requests, and query responses.
Templates are the contract between business callers and the AI execution engine:
- Business callers register and update prompt templates.
- Business callers reference templates by ID and supply variables at generation time.
- The AI service manages storage, versioning, and rendering.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Template Variable Schema
# ------------------------------------------------------------------ #


class TemplateVariableSchema(BaseModel):
    """Schema definition for a single template variable."""

    type: str = Field(
        "string",
        description="Variable data type: 'string', 'number', 'boolean', 'object'.",
        examples=["string"],
    )
    required: bool = Field(
        True,
        description="Whether this variable must be provided at render time.",
    )
    default: Optional[Any] = Field(
        None,
        description="Default value used when the variable is not provided (only for optional variables).",
    )
    description: str = Field(
        "",
        description="Human-readable description of what this variable represents.",
    )


# ------------------------------------------------------------------ #
# Template Defaults
# ------------------------------------------------------------------ #


class TemplateDefaults(BaseModel):
    """Default generation parameters embedded in the template."""

    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature for this template.",
    )
    max_tokens: Optional[int] = Field(
        None,
        ge=1,
        le=4096,
        description="Default max tokens for this template.",
    )
    top_p: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Default nucleus sampling parameter.",
    )
    stop_sequences: Optional[List[str]] = Field(
        None,
        description="Default stop sequences for this template.",
    )


# ------------------------------------------------------------------ #
# Core Template Model
# ------------------------------------------------------------------ #


class PromptTemplate(BaseModel):
    """
    A prompt template managed by the AI Generation Service.

    Templates define the system-level prompt engineering (system_prompt) and a
    user_prompt_template with {{variable}} placeholders. Business callers
    provide variable values at generation time; the AI service renders the
    final prompt and executes it.
    """

    template_id: str = Field(
        ...,
        description="Unique template identifier. Assigned on registration.",
        examples=["tpl_chat_completion"],
    )
    name: str = Field(
        ...,
        description="Human-readable template name.",
        examples=["Chat Completion"],
    )
    description: str = Field(
        "",
        description="Detailed description of the template's purpose and usage.",
    )
    version: str = Field(
        "1.0.0",
        description="Semantic version of the template.",
    )
    owner: str = Field(
        ...,
        description="Service or team that owns this template.",
        examples=["ai-generation-service", "conversation-orchestrator"],
    )
    category: str = Field(
        "general",
        description="Template category for organization.",
        examples=["chat", "summarization", "proactive", "analysis", "safety"],
    )
    system_prompt: str = Field(
        ...,
        description="The system-level prompt. Managed by the AI service for safety and identity.",
    )
    user_prompt_template: str = Field(
        ...,
        description=(
            "The user prompt template with {{variable}} placeholders. "
            "Variables are filled by the business caller at generation time."
        ),
        examples=["{{user_prompt}}"],
    )
    variables: Dict[str, TemplateVariableSchema] = Field(
        default_factory=dict,
        description="Schema of variables accepted by this template.",
    )
    defaults: Optional[TemplateDefaults] = Field(
        None,
        description="Default generation parameters for this template.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for search and filtering.",
    )
    created_at: datetime = Field(
        ...,
        description="ISO 8601 timestamp of template creation.",
    )
    updated_at: datetime = Field(
        ...,
        description="ISO 8601 timestamp of last update.",
    )


# ------------------------------------------------------------------ #
# Registration Request
# ------------------------------------------------------------------ #


class TemplateRegisterRequest(BaseModel):
    """
    Request body for POST /api/v1/templates — register a new template.

    The business caller provides the template content; the AI service
    assigns a template_id and stores it.
    """

    name: str = Field(
        ...,
        description="Human-readable template name.",
        examples=["Custom Greeting"],
    )
    description: str = Field(
        "",
        description="Detailed description of the template's purpose.",
    )
    owner: str = Field(
        ...,
        description="Service or team registering this template.",
        examples=["conversation-orchestrator"],
    )
    category: str = Field(
        "general",
        description="Template category.",
        examples=["chat", "summarization", "proactive"],
    )
    system_prompt: str = Field(
        ...,
        description="The system-level prompt for this template.",
    )
    user_prompt_template: str = Field(
        ...,
        description="The user prompt template with {{variable}} placeholders.",
    )
    variables: Dict[str, TemplateVariableSchema] = Field(
        default_factory=dict,
        description="Schema of variables accepted by this template.",
    )
    defaults: Optional[TemplateDefaults] = Field(
        None,
        description="Default generation parameters.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for search and filtering.",
    )


# ------------------------------------------------------------------ #
# Update Request
# ------------------------------------------------------------------ #


class TemplateUpdateRequest(BaseModel):
    """
    Request body for PUT /api/v1/templates/{template_id} — update an existing template.

    Only the fields provided will be updated. The AI service bumps the
    version and updated_at timestamp automatically.
    """

    name: Optional[str] = Field(None, description="Updated template name.")
    description: Optional[str] = Field(None, description="Updated description.")
    system_prompt: Optional[str] = Field(None, description="Updated system prompt.")
    user_prompt_template: Optional[str] = Field(
        None, description="Updated user prompt template."
    )
    variables: Optional[Dict[str, TemplateVariableSchema]] = Field(
        None, description="Updated variable schema."
    )
    defaults: Optional[TemplateDefaults] = Field(
        None, description="Updated default generation parameters."
    )
    tags: Optional[List[str]] = Field(None, description="Updated tags.")


# ------------------------------------------------------------------ #
# Registration Response
# ------------------------------------------------------------------ #


class TemplateRegisterResponse(BaseModel):
    """
    Response body for POST /api/v1/templates.

    Returns the assigned template_id and the full variable schema so the
    caller knows exactly what variables to provide at generation time.
    """

    template_id: str = Field(
        ...,
        description="Assigned unique template identifier.",
        examples=["tpl_custom_greeting_a1b2c3"],
    )
    name: str = Field(
        ...,
        description="Template name.",
    )
    version: str = Field(
        ...,
        description="Template version.",
    )
    variables: Dict[str, TemplateVariableSchema] = Field(
        ...,
        description="Variable schema — callers must provide these at generation time.",
    )
    defaults: Optional[TemplateDefaults] = Field(
        None,
        description="Default generation parameters.",
    )
    message: str = Field(
        "Template registered successfully.",
        description="Status message.",
    )


# ------------------------------------------------------------------ #
# Query / List Responses
# ------------------------------------------------------------------ #


class TemplateListItem(BaseModel):
    """Summary item in a template listing."""

    template_id: str
    name: str
    description: str
    version: str
    owner: str
    category: str
    tags: List[str]
    updated_at: datetime


class TemplateListResponse(BaseModel):
    """Response body for GET /api/v1/templates."""

    templates: List[TemplateListItem] = Field(
        ...,
        description="List of available templates.",
    )
    total: int = Field(
        ...,
        description="Total number of templates.",
    )
