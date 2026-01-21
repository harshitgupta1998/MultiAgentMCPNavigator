from __future__ import annotations # Allows using types before they're defined

import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError
from langchain_openai import ChatOpenAI


class JudgeScore(BaseModel):
    success: int = Field(..., ge=0, le=5)
    plan_quality: int = Field(..., ge=0, le=5)
    reasoning_quality: int = Field(..., ge=0, le=5)
    notes: str


def _llm() -> ChatOpenAI:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, temperature=0)

def judge_run(
    goal: str,
    plan: Dict[str, Any],
    final_answer: str,
    trace: Optional[str] = None,
) -> JudgeScore:
    """
    LLM-as-judge for multi-agent orchestration quality.
    Returns a strict 0-5 score per dimension.
    """

    llm = _llm()

    prompt = (
        "You are a strict evaluator for a multi-agent tool orchestration system.\n"
        "Score from 0 to 5 (integers) for each category:\n"
        "- success: does the final answer satisfy the goal?\n"
        "- plan_quality: is the plan step-by-step, realistic, and correctly scoped?\n"
        "- tool_use_quality: are the selected tools appropriate and used sensibly?\n\n"
        "Return ONLY valid JSON that matches this schema exactly:\n"
        f"{JudgeScore.model_json_schema()}\n\n"
        f"GOAL:\n{goal}\n\n"
        f"PLAN (JSON):\n{plan}\n\n"
        f"FINAL ANSWER:\n{final_answer}\n\n"
    )

    if trace:
        prompt += f"TRACE:\n{trace[:6000]}\n"

    raw = llm.invoke(prompt).content

    try:
        return JudgeScore.model_validate_json(raw)
    except ValidationError:
        # If the judge returns extra text, try a second pass to coerce JSON-only
        fix_prompt = (
            "Return ONLY valid JSON for this schema. No markdown, no prose.\n"
            f"{JudgeScore.model_json_schema()}\n\n"
            f"Original response:\n{raw}"
        )
        raw2 = llm.invoke(fix_prompt).content
        return JudgeScore.model_validate_json(raw2)