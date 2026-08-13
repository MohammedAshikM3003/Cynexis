"""
CYNEXIS — Intelligence Router Models
Structured models and enums for query routing classification and tool dispatch.
"""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class RouteCategory(str, Enum):
    """Routing categories supported by the CYNEXIS Intelligence Router."""
    LOCAL = "LOCAL"
    TIME = "TIME"
    DATE = "DATE"
    ROBOT_STATUS = "ROBOT_STATUS"
    VISION = "VISION"
    CALCULATOR = "CALCULATOR"
    LIVE_WEB = "LIVE_WEB"
    WEATHER = "WEATHER"
    LOCATION = "LOCATION"
    PROJECT_KNOWLEDGE = "PROJECT_KNOWLEDGE"
    ROBOT_COMMAND = "ROBOT_COMMAND"
    UNKNOWN = "UNKNOWN"


class RoutingResult(BaseModel):
    """
    Structured inspection result from the Intelligence Router.
    Enables deterministic, transparent decision tracking before execution.
    """
    route: RouteCategory = Field(..., description="Selected routing category")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Routing confidence score")
    reason: str = Field(default="", description="Human-readable rationale for the routing decision")
    extracted_params: dict[str, Any] = Field(default_factory=dict, description="Parameters parsed from query")
    handled_locally: bool = Field(default=True, description="True if no external network retrieval was required")
    direct_response: Optional[str] = Field(default=None, description="Pre-computed response if resolved deterministically")
    requires_llm_synthesis: bool = Field(default=False, description="True if retrieved context needs local LLM synthesis")
    augmented_context: Optional[str] = Field(default=None, description="Untrusted retrieved text to supply to LLM context")
    online_telemetry: Optional[dict[str, Any]] = Field(default=None, description="Detailed telemetry for online search retrieval")
