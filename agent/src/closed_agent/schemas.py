from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int
    question: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    name: str
    kind: str
    reason: str


class ChatResponse(BaseModel):
    status: Literal["answered", "needs_approval", "quota_exceeded"]
    answer: str
    citations: list[Citation] = []
    remaining_tokens: int | None = None
    approval_id: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    note: str = ""
