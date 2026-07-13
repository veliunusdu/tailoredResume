import json
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"
    IDLE = "idle"

class JobBase(BaseModel):
    id: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    date_posted: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    site: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    score: Optional[int] = None
    verdict: Optional[str] = None
    reason: Optional[str] = None
    tailored_resume: Optional[str] = None
    cover_letter: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []

class Job(JobBase):
    class Config:
        from_attributes = True

class LastDiscoveryStats(BaseModel):
    raw_scraped_count: int
    filtered_count: int
    scored_count: int
    strong_count: int
    maybe_count: int
    timestamp: float

class Stats(BaseModel):
    total: int
    strong: int
    maybe: int
    avg_score: float
    last_discovery: Optional[LastDiscoveryStats] = None

class ApplyResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    attempt_id: Optional[str] = None
    dry_run: Optional[bool] = None
    message: Optional[str] = None
    ai_patch_suggestion: Optional[str] = None

class ApplyStatus(BaseModel):
    id: str
    job_id: str
    status: JobStatus
    job_board: Optional[str] = None
    dry_run: Optional[bool] = None
    error_msg: Optional[str] = None
    screenshot: Optional[str] = None
    ai_patch_suggestion: Optional[str] = None
    applied_at: Optional[float] = None
    created_at: Optional[float] = None

    @field_validator("dry_run", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, int):
            return bool(v)
        return v

class SessionResponse(BaseModel):
    status: str
    platform: str
    message: Optional[str] = None

class JobPayload(BaseModel):
    title: str
    company_name: str
    raw_content: str
    source_platform: Optional[str] = "Manual Ingest"

class InterviewAnswerPayload(BaseModel):
    question: str
    answer: str

class TailorPayload(BaseModel):
    tone_style: str = "Professional"
