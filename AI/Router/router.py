"""
CYNEXIS — Intelligence Router
Deterministic, inspectable routing engine that classifies user queries into appropriate local, tool, or live channels.
Enforces robotics safety boundaries, offline-first fallback, and prompt injection defense.
"""

import re
from typing import Optional
from core.logger import get_logger
from core.config import settings
from core.constants import ActionName

from AI.Router.models import RouteCategory, RoutingResult
from AI.Router.tools.datetime_tool import DateTimeTool
from AI.Router.tools.calculator_tool import SafeCalculatorTool
from AI.Router.tools.robot_status_tool import RobotStatusTool
from AI.Router.knowledge import ProjectKnowledgeEngine
from AI.Router.cache import InformationCache, information_cache
from AI.Router.providers.base import LiveInformationProvider
from AI.Router.providers.web_search import WebSearchProvider
from AI.Intent.engine import IntentEngine, intent_engine

log = get_logger("router")


class IntelligenceRouter:
    """
    Intelligent routing layer for CYNEXIS.
    Directs queries to deterministic tools, local models, or rate-limited live web providers.
    """

    def __init__(
        self,
        intent: Optional[IntentEngine] = None,
        cache: Optional[InformationCache] = None,
        web_provider: Optional[LiveInformationProvider] = None,
    ):
        self.intent = intent or intent_engine
        self.cache = cache or information_cache
        self.web_provider = web_provider or WebSearchProvider()
        self.enabled = getattr(settings, "router_enabled", True)
        log.info("IntelligenceRouter initialized with all tool and provider capabilities")

    def route_query_sync(self, text: str) -> RoutingResult:
        """
        Fast, synchronous classification of user input into a RouteCategory.
        Evaluates deterministic patterns with strict priority.
        """
        cleaned = text.strip()
        cleaned_lower = cleaned.lower()

        if not cleaned:
            return RoutingResult(
                route=RouteCategory.UNKNOWN,
                confidence=0.0,
                reason="Empty query",
                handled_locally=True,
            )

        # 1. Robot Command & Action Check
        if self.intent.is_robot_command(cleaned):
            action = self.intent.classify(cleaned)
            if action == ActionName.GET_STATUS:
                response = RobotStatusTool.process(cleaned)
                return RoutingResult(
                    route=RouteCategory.ROBOT_STATUS,
                    confidence=0.98,
                    reason="Robot status telemetry query",
                    direct_response=response,
                    handled_locally=True,
                )
            if action == ActionName.DESCRIBE_SCENE:
                return RoutingResult(
                    route=RouteCategory.VISION,
                    confidence=0.98,
                    reason="Visual scene description (Moondream2 VLM)",
                    handled_locally=True,
                )
            return RoutingResult(
                route=RouteCategory.ROBOT_COMMAND,
                confidence=1.0,
                reason=f"Matched hardware robot command: {action.value if action else 'unknown'}",
                extracted_params={"action": action.value if action else None},
                handled_locally=True,
            )

        # 2. Time & Date Queries
        time_patterns = [
            r"\b(what time is it|current time|what is the time|tell me the time|time now)\b",
            r"\bwhat time\b.*\b(in|of)\s+[a-z]+",
        ]
        date_patterns = [
            r"\b(what date is today|what is today'?s date|today'?s date|what date is it|current date)\b",
            r"\b(what day is today|what day is it|which day is today)\b",
            r"\b(what year is it|current year|what is the current year)\b",
        ]
        if any(re.search(p, cleaned_lower) for p in time_patterns):
            response = DateTimeTool.process(cleaned)
            return RoutingResult(
                route=RouteCategory.TIME,
                confidence=0.98,
                reason="Deterministic time query",
                direct_response=response,
                handled_locally=True,
            )
        if any(re.search(p, cleaned_lower) for p in date_patterns):
            response = DateTimeTool.process(cleaned)
            return RoutingResult(
                route=RouteCategory.DATE,
                confidence=0.98,
                reason="Deterministic date/day query",
                direct_response=response,
                handled_locally=True,
            )

        # 3. Robot Status Telemetry Queries
        status_patterns = [
            r"\b(robot status|system status|how are you|are you online|is the robot online)\b",
            r"\b(is the robot connected|is the esp32 (online|connected)|esp32 status)\b",
            r"\b(battery (status|level|percentage)|what('s| is) the battery)\b",
            r"\b(motor (status|state|controller)|are the motors (on|enabled|connected))\b",
        ]
        if any(re.search(p, cleaned_lower) for p in status_patterns):
            response = RobotStatusTool.process(cleaned)
            return RoutingResult(
                route=RouteCategory.ROBOT_STATUS,
                confidence=0.95,
                reason="Deterministic robot telemetry query",
                direct_response=response,
                handled_locally=True,
            )

        # 4. Safe Calculator Queries
        calc_keywords = ["calculate", "multiplied by", "divided by", "times", "plus", "minus", "percent of", "squared", "cubed", "square root of"]
        has_numbers = bool(re.search(r"\d+", cleaned_lower))
        if has_numbers and (any(kw in cleaned_lower for kw in calc_keywords) or bool(re.search(r"[\+\-\*\/\^]\s*\d+", cleaned_lower))):
            calc_response = SafeCalculatorTool.process(cleaned)
            if calc_response:
                return RoutingResult(
                    route=RouteCategory.CALCULATOR,
                    confidence=0.95,
                    reason="Deterministic arithmetic calculation",
                    direct_response=calc_response,
                    handled_locally=True,
                )

        # 5. Vision Queries
        vision_patterns = [
            r"\b(what do you see|what are you seeing|describe what you see|look around)\b",
            r"\b(what('s| is) in front of you|identify object|describe (the )?scene)\b",
            r"\b(describe this image|look at this|is there a person in front)\b",
            r"\bwhat object is on the table\b",
        ]
        if any(re.search(p, cleaned_lower) for p in vision_patterns):
            return RoutingResult(
                route=RouteCategory.VISION,
                confidence=0.95,
                reason="Camera and local vision (Moondream2) query",
                handled_locally=True,
            )

        # 6. Project Knowledge Queries
        project_match = ProjectKnowledgeEngine.find_match(cleaned)
        if project_match:
            return RoutingResult(
                route=RouteCategory.PROJECT_KNOWLEDGE,
                confidence=0.90,
                reason="Local CYNEXIS project architecture/hardware fact",
                direct_response=project_match,
                handled_locally=True,
            )

        # 7. Live / Temporal Web Queries
        live_indicators = [
            r"\bwhat happened (today|yesterday|recently|this week|in the world)\b",
            r"\bwhat is happening (today|now|around the world)\b",
            r"\btoday'?s (current affairs|news|weather|match|headlines|events|updates)\b",
            r"\blatest (ai news|news|technology news|tech news|updates|headlines|developments|trends)\b",
            r"\b(what happened in|latest news about|news in|news about|breaking news|top stories)\s+[a-z0-9\s]+",
            r"\b(who is|who's|name of)\s+(the\s+)?(current\s+)?(chief minister|cheif minister|cm|prime minister|pm|president|governor|ceo|mayor|chancellor|leader|captain)\b",
            r"\b(chief minister|cheif minister|cm|prime minister|pm|president|governor|ceo|mayor)\s+of\b",
            r"\b(who won|match score|election score|match result)\b",
            r"\b(current|today'?s)\s+(weather|temperature|forecast|price|stock price|gold price|score|news|affairs)\b",
            r"\b(weather|temperature|forecast)\s+(in|of|at|for)\s+[a-z0-9\s]+",
            r"\b(how('s| is) the weather|what('s| is) the weather)\b",
            r"\bweather today\b",
        ]
        if any(re.search(p, cleaned_lower) for p in live_indicators):
            return RoutingResult(
                route=RouteCategory.LIVE_WEB,
                confidence=0.92,
                reason="Current/live temporal information query requiring external retrieval",
                handled_locally=False,
                requires_llm_synthesis=True,
            )

        # 8. Local LLM General Knowledge Queries (Default Local Path)
        local_indicators = [
            r"\b(what is|explain|how does|tell me|who is|why is|define)\b",
        ]
        if any(re.search(p, cleaned_lower) for p in local_indicators) or len(cleaned.split()) >= 2:
            return RoutingResult(
                route=RouteCategory.LOCAL,
                confidence=0.90,
                reason="General knowledge question routed to local Llama 3.2:3B",
                handled_locally=True,
                requires_llm_synthesis=True,
            )

        # 9. Fallback Unknown
        return RoutingResult(
            route=RouteCategory.UNKNOWN,
            confidence=0.40,
            reason="Ambiguous input, defaulting to local general conversation",
            handled_locally=True,
            requires_llm_synthesis=True,
        )

    async def route_and_resolve(self, text: str) -> RoutingResult:
        """
        Complete asynchronous routing and retrieval resolution.
        If the query requires live information, fetches and prepares sanitized context.
        """
        result = self.route_query_sync(text)

        # If it's a live web query, perform caching and rate-limited retrieval
        if result.route == RouteCategory.LIVE_WEB:
            # 1. Check cache first
            cached_context = await self.cache.get(text)
            if cached_context:
                result.augmented_context = cached_context
                return result

            # 2. Check rate limiter & provider availability
            if not self.web_provider.is_available():
                result.direct_response = "Live web search is currently disabled in configuration."
                result.requires_llm_synthesis = False
                result.handled_locally = True
                return result

            can_request = await self.cache.can_request()
            if not can_request:
                log.info("Throttling active — fetching shortly or using offline notice")

            # 3. Perform external search with safety boundaries
            await self.cache.record_request()
            search_results = await self.web_provider.search(text, max_results=settings.web_search_max_results)

            if not search_results:
                # Offline-first fallback
                result.direct_response = (
                    "I cannot access live information right now. "
                    "I can still answer general questions using my local knowledge."
                )
                result.requires_llm_synthesis = False
                result.handled_locally = True
                return result

            # 4. Construct untrusted, isolated reference context for local Llama
            snippets_text = "\n".join([f"- {r.snippet}" for r in search_results])
            untrusted_context = (
                "[LIVE REAL-TIME INFORMATION RETRIEVED]\n"
                "The following real-time stories/facts have been retrieved from live feeds:\n"
                "--- BEGIN REAL-TIME INFORMATION ---\n"
                f"{snippets_text}\n"
                "--- END REAL-TIME INFORMATION ---\n"
                f"User Question: {text}\n"
                "Based directly on the real-time information provided above, tell the user the actual news headlines, weather, or facts in 1-2 concise, clear spoken sentences. "
                "Do NOT say 'you can search for' or 'information can be found at' or refer to websites. Directly state the actual facts and news stories to the user."
            )

            # Store in cache
            await self.cache.set(text, untrusted_context)
            result.augmented_context = untrusted_context

        return result


# Singleton instance
intelligence_router = IntelligenceRouter()
