"""Telecom triage agent powered by LangChain/LangGraph and Gemini."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from app.llm import LLMConfigError, get_llm
from app.prompts import SYSTEM_PROMPT
from app.schemas import (
    Category,
    Priority,
    ToolName,
    TriageDecision,
    TriageRequest,
    TriageResponse,
)
from app.tools import (
    lookup_customer_profile,
    lookup_knowledge,
    lookup_network_status,
)

logger = logging.getLogger("triage.agent")

MAX_LLM_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 3.0
# Gemini free tier allows only a few requests per minute; an instant retry just fails again.
RATE_LIMIT_BACKOFF_SECONDS = 15.0

# Used when the LLM fails twice: the ticket is never lost, it is flagged for a human.
FALLBACK_DECISION = TriageDecision(
    category=Category.OTHER,
    priority=Priority.P1,
    next_tool=ToolName.CUSTOMER_PROFILE,
    reasoning="Automatic triage was unavailable, so this ticket was routed for manual review.",
    why="Fallback decision after a model error or invalid model output.",
)


class CustomerNotFoundError(Exception):
    """Raised when the customer ID does not exist in the customer data."""


_triage_agent: CompiledStateGraph | None = None


def create_triage_agent() -> CompiledStateGraph:
    """Create (once) and return the triage agent.

    ``response_format`` makes the agent return a validated ``TriageDecision``
    in ``result["structured_response"]`` instead of free text we have to parse.
    """
    global _triage_agent
    if _triage_agent is None:
        _triage_agent = create_agent(
            model=get_llm(),
            tools=[],
            system_prompt=SYSTEM_PROMPT,
            response_format=TriageDecision,
        )
    return _triage_agent


def _build_user_input(request: TriageRequest) -> str:
    """Format a triage request into a prompt for the agent."""
    return (
        f"Customer ID: {request.customer_id}\n"
        f"Location: {request.location or 'Not provided'}\n"
        f"Complaint: {request.message}"
    )


def _invoke_llm(request: TriageRequest) -> TriageDecision:
    """One LLM call returning a validated decision (the seam tests patch)."""
    result = create_triage_agent().invoke(
        {"messages": [{"role": "user", "content": _build_user_input(request)}]}
    )
    structured = result.get("structured_response")
    if structured is None:
        raise ValueError("Agent returned no structured response.")
    return TriageDecision.model_validate(structured)


def _backoff_seconds(exc: Exception) -> float:
    """Wait longer after a rate-limit (429) error than after other errors."""
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return RATE_LIMIT_BACKOFF_SECONDS
    return RETRY_BACKOFF_SECONDS


def _decide(request: TriageRequest) -> tuple[TriageDecision, bool]:
    """Return ``(decision, used_fallback)``; retry once, then fall back."""
    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            decision = _invoke_llm(request)
            logger.info(
                "llm ok attempt=%d latency=%.2fs", attempt, time.perf_counter() - started
            )
            return decision, False
        except LLMConfigError:
            raise  # a setup problem, not a transient one: surface it
        except Exception as exc:
            logger.exception(
                "llm failed attempt=%d latency=%.2fs",
                attempt,
                time.perf_counter() - started,
            )
            if attempt < MAX_LLM_ATTEMPTS:
                time.sleep(_backoff_seconds(exc))
    return FALLBACK_DECISION, True


def _execute_selected_tool(
    decision: TriageDecision,
    request: TriageRequest,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Run the lookup the model selected."""
    if decision.next_tool is ToolName.CUSTOMER_PROFILE:
        return profile
    if decision.next_tool is ToolName.NETWORK_STATUS:
        # No location in the form? Use the city on the customer's account.
        city = request.location or str(profile.get("city", ""))
        return lookup_network_status(city)
    if decision.next_tool is ToolName.KNOWLEDGE:
        return lookup_knowledge(decision.category.value)
    return {}


def run_triage(request: TriageRequest) -> TriageResponse:
    """Triage one complaint end to end."""
    # Cheap local check first: don't spend an LLM call on an unknown customer.
    profile = lookup_customer_profile(request.customer_id)
    if "error" in profile:
        raise CustomerNotFoundError(request.customer_id)

    started = time.perf_counter()
    decision, used_fallback = _decide(request)
    tool_result = _execute_selected_tool(decision, request, profile)

    logger.info(
        "triage customer=%s category=%s priority=%s tool=%s fallback=%s total=%.2fs",
        request.customer_id,
        decision.category.value,
        decision.priority.value,
        decision.next_tool.value,
        used_fallback,
        time.perf_counter() - started,
    )
    return TriageResponse(
        **decision.model_dump(),
        tool_result=tool_result,
        needs_human_review=used_fallback,
    )
