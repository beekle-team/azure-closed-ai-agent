from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int = 1
    question: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    name: str
    kind: str
    reason: str
    source: str = "graph"


class ChatResponse(BaseModel):
    status: Literal["answered", "needs_approval", "quota_exceeded", "skill_ran"]
    answer: str
    citations: list[Citation] = []
    remaining_tokens: int | None = None
    approval_id: str | None = None
    skill_id: str | None = None
    plan: list[str] = []


class ApprovalRequest(BaseModel):
    approved: bool
    note: str = ""


class SkillRunRequest(BaseModel):
    user_id: int = 1
    inputs: dict[str, str] = {}


class IngestRequest(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    kind: Literal["manual", "tacit"] = "tacit"
