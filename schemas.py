"""
Database Schemas for Lernify Road

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase of the class name.

Collections:
- User -> "user"
- Roadmap -> "roadmap"
- AssessmentAttempt -> "assessmentattempt"
"""

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class RoadmapStep(BaseModel):
    index: int = Field(..., ge=0, description="Step order index")
    title: str
    description: str
    youtube_url: Optional[str] = None
    assessment_question: Optional[str] = None
    assessment_options: Optional[List[str]] = None
    assessment_answer_index: Optional[int] = Field(None, ge=0)


class Roadmap(BaseModel):
    domain: str = Field(..., description="e.g., frontend, backend, ai, ml")
    title: str
    description: Optional[str] = None
    steps: List[RoadmapStep]
    is_active: bool = True


class User(BaseModel):
    name: str
    email: EmailStr
    password_hash: str
    domain: Optional[str] = Field(None, description="Chosen learning path domain")
    # progress map: {"frontend": {"completed": [0,1], "scores": {"0": 90}}}
    progress: Optional[dict] = Field(default_factory=dict)
    role: str = Field("student")
    is_active: bool = True


class AssessmentAttempt(BaseModel):
    user_id: str
    domain: str
    step_index: int = Field(..., ge=0)
    score: int = Field(..., ge=0, le=100)
    total: int = 100

