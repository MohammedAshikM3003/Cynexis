"""
CYNEXIS — Web Search & Live News Provider
Async, rate-limit aware live web and news provider using httpx and RSS feeds.
Requires zero paid API keys and implements prompt injection sanitization, live news extraction, and multi-source fallback.
"""

import re
import html
import unicodedata
import xml.etree.ElementTree as ET
import httpx
from typing import Optional
from core.logger import get_logger
from core.config import settings
from AI.Router.providers.base import LiveInformationProvider, SearchResult

log = get_logger("web_search")


class WebSearchProvider(LiveInformationProvider):
    """
    Retrieves current public information from web search and live news feeds.
    Free, rate-limited, and sandboxed with prompt-injection filtering.
    Implements multi-source fallback (Live News Feeds -> DuckDuckGo HTML -> DuckDuckGo Lite -> Wikipedia API).
    """

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    WIKI_USER_AGENT = "CynexisVoicePlatform/1.0 (admin@cynexis.local)"

    def __init__(self, timeout_s: Optional[float] = None):
        self.timeout_s = timeout_s or getattr(settings, "web_search_timeout_s", 6.0)
        self.enabled = getattr(settings, "web_search_enabled", True)
        log.info(f"WebSearchProvider initialized (timeout={self.timeout_s}s, enabled={self.enabled})")

    def is_available(self) -> bool:
        return self.enabled

    @staticmethod
    def is_news_query(text: str) -> bool:
        """Check if query is asking for current news, headlines, or today's events."""
        t = text.lower()
        news_keywords = [
            "news", "headline", "headlines", "happened today", "happening today",
            "happened in", "current affairs", "breaking news", "updates today",
            "top stories", "world events", "latest updates", "what happened"
        ]
        return any(kw in t for kw in news_keywords)

    @staticmethod
    def sanitize_snippet(text: str) -> str:
        """
        Sanitize untrusted text from the web:
        1. Decode HTML entities.
        2. Strip HTML/XML tags.
        3. Neutralize dangerous prompt injection keywords & delimiters.
        4. Normalize unicode characters for safe TTS and console encoding.
        5. Normalize whitespace and bound length.
        """
        if not text:
            return ""

        # Decode HTML entities
        cleaned = html.unescape(text)

        # Remove HTML tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)

        # Normalize unicode to avoid Windows console / TTS encoding crashes
        cleaned = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")

        # Strip dangerous prompt-injection tokens and delimiters
        injection_patterns = [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"disregard\s+(all\s+)?prior\s+instructions",
            r"system\s*:",
            r"assistant\s*:",
            r"user\s*:",
            r"<\/?s>",
            r"\[INST\]",
            r"\[\/INST\]",
            r"```",
        ]
        for pattern in injection_patterns:
            cleaned = re.sub(pattern, "[filtered]", cleaned, flags=re.IGNORECASE)

        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Bound length
        return cleaned[:350]

    @staticmethod
    def optimize_search_query(query: str) -> str:
        """Reformulate conversational queries into high-yield search keywords."""
        q = query.lower().strip()
        # Remove conversational filler prefixes
        q = re.sub(r"^(what is the|what is|what are|tell me about|tell me the|tell me|can you tell me|what happened in|what happened|who is the|who is|who won)\s+", "", q)
        q = q.rstrip("?").strip()
        return q

    async def _fetch_live_news(self, query: str, client: httpx.AsyncClient, max_results: int = 3) -> list[SearchResult]:
        """Fetch actual real-time news headlines via live news feeds."""
        try:
            q_clean = query.lower().strip()
            # Remove filler words to get core topic
            q_clean = re.sub(r"^(what is the|what is|tell me the|tell me|latest|today'?s|recent|news about|news in|news on|breaking news|top stories)\s+", "", q_clean)
            q_clean = re.sub(r"\b(news|today|happened|world|now|please|in the world)\b", "", q_clean).strip()

            if q_clean and len(q_clean) >= 2:
                url = f"https://news.google.com/rss/search?q={q_clean}&hl=en-US&gl=US&ceid=US:en"
            else:
                url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            }
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                items = root.findall(".//item")
                results = []
                for item in items[:max_results]:
                    title = item.findtext("title", "")
                    cleaned_title = self.sanitize_snippet(title)
                    if cleaned_title:
                        results.append(SearchResult(title="Live Headline", snippet=cleaned_title, source="live_news"))
                if results:
                    log.info(f"Live news feed returned {len(results)} fresh headlines for '{query}'")
                    return results
        except Exception as e:
            log.debug(f"Live news feed fetch error: {e}")
        return []

    async def _search_duckduckgo(self, search_query: str, client: httpx.AsyncClient, max_results: int) -> list[SearchResult]:
        """Search DuckDuckGo HTML and Lite endpoints."""
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        url = "https://html.duckduckgo.com/html/"
        try:
            response = await client.get(url, params={"q": search_query}, headers=headers)
            if response.status_code != 200:
                response = await client.post(url, data={"q": search_query}, headers=headers)

            if response.status_code != 200:
                lite_url = "https://lite.duckduckgo.com/lite/"
                response = await client.get(lite_url, params={"q": search_query}, headers=headers)

            if response.status_code in (200, 202):
                html_content = response.text
                snippet_matches = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html_content, re.DOTALL | re.IGNORECASE)
                if not snippet_matches:
                    snippet_matches = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', html_content, re.DOTALL | re.IGNORECASE)

                title_matches = re.findall(r'<a[^>]*class="result__url"[^>]*>(.*?)</a>', html_content, re.DOTALL | re.IGNORECASE)

                results = []
                for i, raw_snippet in enumerate(snippet_matches[:max_results]):
                    cleaned_snippet = self.sanitize_snippet(raw_snippet)
                    if not cleaned_snippet:
                        continue
                    title = f"Web Result {i+1}"
                    if i < len(title_matches):
                        title = self.sanitize_snippet(title_matches[i])
                    results.append(SearchResult(title=title, snippet=cleaned_snippet, source="duckduckgo"))
                return results
        except Exception as e:
            log.debug(f"DuckDuckGo search attempt failed: {e}")
        return []

    async def _search_wikipedia(self, search_query: str, client: httpx.AsyncClient, max_results: int) -> list[SearchResult]:
        """Fallback to Wikipedia Knowledge search."""
        headers = {"User-Agent": self.WIKI_USER_AGENT}
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": search_query,
                "utf8": 1,
                "format": "json",
                "srlimit": max_results,
            }
            resp = await client.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get("query", {}).get("search", [])
                results = []
                for item in items:
                    title = self.sanitize_snippet(item.get("title", ""))
                    snippet = self.sanitize_snippet(item.get("snippet", ""))
                    if snippet:
                        results.append(SearchResult(title=title, snippet=snippet, source="wikipedia"))
                return results
        except Exception as e:
            log.debug(f"Wikipedia search attempt failed: {e}")
        return []

    async def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        """
        Execute an async search for current information or live news.
        """
        if not self.is_available():
            log.info("Web search is disabled in settings.")
            return []

        clean_query = query.strip()
        if not clean_query:
            return []

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
                # 1. If it's a news query, fetch fresh live news headlines first
                if self.is_news_query(clean_query):
                    news_results = await self._fetch_live_news(clean_query, client, max_results)
                    if news_results:
                        return news_results

                search_query = self.optimize_search_query(clean_query)
                log.info(f"Optimized search query: '{clean_query}' -> '{search_query}'")

                # 2. Primary Web: DuckDuckGo search
                results = await self._search_duckduckgo(search_query, client, max_results)
                if results:
                    log.info(f"Web search via DuckDuckGo returned {len(results)} sanitized results")
                    return results

                # 3. Fallback: Wikipedia Knowledge Search
                results = await self._search_wikipedia(search_query, client, max_results)
                if results:
                    log.info(f"Web search fallback via Wikipedia returned {len(results)} sanitized results")
                    return results

        except httpx.TimeoutException:
            log.warning(f"Web search timed out after {self.timeout_s}s for query: '{clean_query}'")
        except Exception as e:
            log.warning(f"Web search encountered error: {e}")

        return []


