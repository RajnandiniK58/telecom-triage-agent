"""Pydantic models: API request/response and the LLM's structured output."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator



class Category(str, Enum):
    SIM_REPLACEMENT = "SIM Replacement"
    PORTING = "Porting"
    RECHARGE_FAILURE = "Recharge Failure"
    BILLING_ISSUES = "Billing Issues"
    NETWORK_ISSUES = "Network Issues"
    ROAMING = "Roaming"
    SMS_ISSUES = "SMS Issues"
    OTHER = "Other"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class ToolName(str, Enum):
    CUSTOMER_PROFILE = "lookup_customer_profile"
    NETWORK_STATUS = "lookup_network_status"
    KNOWLEDGE = "lookup_knowledge"


class TriageRequest(BaseModel):
    """Input payload for telecom ticket triage requests."""

    customer_id: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=3, max_length=2000)
    location: Optional[str] = Field(default=None, max_length=100)

    @field_validator("customer_id", "message", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("customer_id")
    @classmethod
    def _normalise_id(cls, value: str) -> str:
        return value.upper()

    @field_validator("location", mode="before")
    @classmethod
    def _blank_location_is_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class TriageDecision(BaseModel):
    """What the LLM must return. Enums make invalid values impossible."""

    category: Category
    priority: Priority
    next_tool: ToolName
    secondary_issues: list[Category] = Field(
        default_factory=list,
        description="Other distinct problems in the complaint; empty if it has only one.",
    )
    reasoning: str = Field(
        description="Step-by-step triage analysis based ONLY on the complaint text."
    )
    why: str = Field(
        description="One or two sentences justifying the category, priority and tool."
    )

    @field_validator("secondary_issues", mode="before")
    @classmethod
    def _none_means_empty(cls, value: Any) -> Any:
        """Some models send null instead of an empty list."""
        return [] if value is None else value

    @model_validator(mode="after")
    def _clean_secondary(self) -> "TriageDecision":
        """Drop duplicates and the main category from secondary_issues."""
        seen: list[Category] = []
        for issue in self.secondary_issues:
            if issue != self.category and issue not in seen:
                seen.append(issue)
        self.secondary_issues = seen
        return self
class TriageResponse(BaseModel):
    """Structured output returned after triaging a support ticket."""

    category: Category
    priority: Priority
    next_tool: ToolName
    secondary_issues: list[Category] = Field(default_factory=list)
    reasoning: str
    why: str
    tool_result: dict[str, Any] = Field(default_factory=dict)
    needs_human_review: bool = False