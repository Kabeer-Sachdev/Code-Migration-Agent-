"""
Pydantic models for all API request / response contracts.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────────────────────

class StartMigrationRequest(BaseModel):
    api_key: str = Field(default="", description="Ollama API key (optional for local Ollama)")
    model: str   = Field(
        default="llama2",
        description="Ollama model name",
    )


# ── Response Models ───────────────────────────────────────────────────────────

class JobCreatedResponse(BaseModel):
    job_id: str
    message: str = "Migration job created"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    current_step: str
    error: Optional[str] = None


class JavaFileResponse(BaseModel):
    filename: str
    content: str


class MigrationResultResponse(BaseModel):
    job_id: str
    status: str
    analysis: Dict[str, Any]
    java_files: List[JavaFileResponse]
    test_files: List[JavaFileResponse]
    pom_xml: str
    application_yml: str
    notes: Dict[str, Any]
    total_java_files: int
    total_test_files: int


class ErrorResponse(BaseModel):
    detail: str
