from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PII(BaseModel):
    full_name: str = Field(..., alias="[[FULL_NAME]]")
    email: str = Field(..., alias="[[EMAIL]]")
    phone: str = Field(..., alias="[[PHONE]]")
    linkedin: str = Field(..., alias="[[LINKEDIN]]")
    address: str = Field(..., alias="[[STREET_ADDRESS]]")


class Bullet(BaseModel):
    text: str
    keywords: List[str] = []
    weight: int = Field(default=5, ge=1, le=10)


class Experience(BaseModel):
    company: str
    role: str = ""
    bullets: List[Bullet]


class UserPreferences(BaseModel):
    target_roles: List[str] = []
    target_salary: Optional[str] = None
    location_preference: List[str] = []
    remote_preference: str = "Remote"  # Remote, Hybrid, On-site
    visa_sponsorship: bool = False
    target_keywords: List[str] = []


class MasterCV(BaseModel):
    pii: Dict[str, str]
    experience: List[Experience]
    skills: List[str]
    preferences: UserPreferences = Field(default_factory=UserPreferences)
