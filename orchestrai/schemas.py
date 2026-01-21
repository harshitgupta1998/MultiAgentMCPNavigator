from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any


Role = Literal["research", "planner", "executor"]


class ResearchFinding(BaseModel):
    source: str = Field(..., description="Where the info came from")
    title: str
    url: Optional[str] = None
    summary: str


class ResearchPacket(BaseModel):
    query: str
    findings: List[ResearchFinding] = Field(default_factory=list)
    notes: Optional[str] = None


class PlanStep(BaseModel):
    step_id: int = Field(..., description="Sequential step number")
    action: str = Field(..., description="What needs to be done")
    tools: List[str] = Field(default_factory=list, description="Tools required")
    success_criteria: str = Field(..., description="How to know this step succeeded")

class TaskPlan(BaseModel):
    goal: str = Field(..., description="User objective")
    assumptions: List[str] = Field(default_factory=list)
    steps: List[PlanStep] = Field(..., min_length=1)
    risks: List[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    goal: str
    completed: bool
    outputs: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    final_answer: str
