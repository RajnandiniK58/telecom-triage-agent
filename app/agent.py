"""Telecom triage agent powered by LangChain and Gemini."""

import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph.state import CompiledStateGraph

from app.llm import get_llm
from app.schemas import TriageRequest, TriageResponse
from app.tools import (
    lookup_customer_profile,
    lookup_knowledge,
    lookup_network_status,
)

SYSTEM_PROMPT = """You are a Telecom Support Triage Agent.

Your job is to analyze customer complaints and produce a structured triage decision.

Available tools:
- lookup_customer_profile: Look up account, plan, SIM status, and recent ticket history by customer_id.
- lookup_network_status: Check network outages and signal strength for a city.
- lookup_knowledge: Retrieve recommended actions for a known telecom topic.

Instructions:
1. Understand the telecom complaint from the customer message.
2. Determine the complaint category (for example: SIM Replacement, Porting, Recharge Failure, Billing Issues, Network Issues).
3. Assign priority as P0 (critical/urgent), P1 (high), or P2 (standard).
4. Decide which single tool is required to investigate this case.
5. Call ONLY that required tool. Never call unnecessary tools.
6. Use the tool result in your analysis.
7. Explain your reasoning clearly.

Priority guidance:
- P0: Service outage, blocked SIM with urgent impact, or complete loss of connectivity.
- P1: Billing disputes, porting delays, recharge failures, or account issues needing prompt action.
- P2: General inquiries or low-impact issues.

Respond with ONLY valid JSON in this exact format (no markdown, no extra text):
{{
    "category": "...",
    "priority": "...",
    "next_tool": "...",
    "reasoning": "...",
    "why": "..."
}}

Field rules:
- next_tool must be exactly one of: lookup_customer_profile, lookup_network_status, lookup_knowledge
- reasoning: step-by-step triage analysis including tool findings
- why: short justification for the category, priority, and tool choice
"""

_triage_agent: CompiledStateGraph | None = None


def _build_tools() -> list[StructuredTool]:
    """Register existing lookup functions as LangChain tools."""
    return [
        StructuredTool.from_function(
            func=lookup_customer_profile,
            name="lookup_customer_profile",
            description=(
                "Look up a customer profile by customer_id. "
                "Use for account status, SIM status, active plan, and recent ticket details."
            ),
        ),
        StructuredTool.from_function(
            func=lookup_network_status,
            name="lookup_network_status",
            description=(
                "Look up network status for a city. "
                "Use for outage, signal strength, and estimated resolution details."
            ),
        ),
        StructuredTool.from_function(
            func=lookup_knowledge,
            name="lookup_knowledge",
            description=(
                "Look up a telecom knowledge article by topic. "
                "Use for SIM Replacement, Porting, Recharge Failure, Billing Issues, or Network Issues."
            ),
        ),
    ]


def create_triage_agent() -> CompiledStateGraph:
    """Create and return the configured telecom triage agent."""
    global _triage_agent
    if _triage_agent is not None:
        return _triage_agent

    _triage_agent = create_agent(
        model=get_llm(),
        tools=_build_tools(),
        system_prompt=SYSTEM_PROMPT,
    )
    return _triage_agent


def _build_user_input(request: TriageRequest) -> str:
    """Format a triage request into a prompt for the agent."""
    location = request.location or "Not provided"
    return (
        f"Customer ID: {request.customer_id}\n"
        f"Location: {location}\n"
        f"Complaint: {request.message}"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse a JSON object from the agent's final response."""
    cleaned = text.strip()

    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if code_block_match:
        cleaned = code_block_match.group(1)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Agent response did not contain valid JSON output.")

    return json.loads(cleaned[start : end + 1])


def _extract_final_text(result: dict[str, Any]) -> str:
    """Get the final AI message text from the agent result."""
    messages = result.get("messages", [])
    for message in reversed(messages):
        if not isinstance(message, AIMessage) or not message.content:
            continue

        content = message.content
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    text_parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(str(block.get("text", "")))
            combined = "".join(text_parts).strip()
            if combined:
                return combined

    raise ValueError("Agent response did not contain a final AI message.")


def _parse_tool_content(observation: Any) -> dict[str, Any]:
    """Convert a tool observation into a dictionary."""
    if isinstance(observation, dict):
        return observation

    try:
        parsed = json.loads(observation)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"result": observation}


def _extract_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the selected tool result from the agent's message history."""
    messages = result.get("messages", [])
    tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
    if not tool_messages:
        return {}

    return _parse_tool_content(tool_messages[-1].content)


def run_triage(request: TriageRequest) -> dict[str, Any]:
    """Run the triage agent and return a structured response dictionary."""
    agent = create_triage_agent()
    result = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": _build_user_input(request)},
            ]
        }
    )

    parsed = _extract_json(_extract_final_text(result))
    response = TriageResponse.model_validate(parsed)
    output = response.model_dump()
    output["tool_result"] = _extract_tool_result(result)
    return output
