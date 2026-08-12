"""
CYNEXIS — Live Information Provider Base
Abstract interface and data models for pluggable external live-information retrieval.
"""

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Normalized search result snippet from a live information provider."""
    title: str = Field(default="", description="Headline or title of the retrieved item")
    snippet: str = Field(..., description="Clean textual excerpt or summary")
    url: Optional[str] = Field(default=None, description="Source URL if available")
    source: str = Field(default="web", description="Provider identifier (e.g. web, rss, api)")


class LiveInformationProvider(ABC):
    """Abstract interface for live external information providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        """
        Asynchronously search for live information given a query.

        Args:
            query: Cleaned user search query
            max_results: Maximum number of snippets to return

        Returns:
            List of SearchResult objects (empty list if no results or offline)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is operational and enabled."""
        pass
