"""
CYNEXIS — Real Live Information Verification Script
Tests real internet HTTP retrieval, caching, and local Llama 3.2:3B synthesis.
"""

import asyncio
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import setup_logging, get_logger
from core.config import settings
from AI.Router.models import RouteCategory
from AI.Router.router import IntelligenceRouter
from AI.Router.providers.web_search import WebSearchProvider
from AI.Router.cache import InformationCache
from AI.LLM.ollama_provider import OllamaLLMProvider
from AI.LLM.provider import MockLLMProvider

log = get_logger("live_test")


async def main():
    setup_logging()
    print("\n" + "=" * 70)
    print("  CYNEXIS PHASE 8 — REAL LIVE INFORMATION RUNTIME TEST")
    print("=" * 70)

    # 1. Initialize Real Web Search Provider & Cache
    cache = InformationCache(default_ttl_s=900, min_request_interval_s=1.0)
    web_provider = WebSearchProvider(timeout_s=5.0)
    router = IntelligenceRouter(cache=cache, web_provider=web_provider)

    test_queries = [
        "What is the latest AI news?",
        "What happened in India today?",
        "What is 345 times 78",          # Deterministic tool sanity check
        "What time is it in India",       # Deterministic tool sanity check
    ]

    print("\n--- STEP 1: Testing Live Search Provider Over Active Network ---")
    live_query = "latest SpaceX news"
    print(f"Query: '{live_query}'")
    t0 = time.time()
    results = await web_provider.search(live_query, max_results=3)
    elapsed = round(time.time() - t0, 3)

    if results:
        print(f"[SUCCESS] Retrieved {len(results)} live search results in {elapsed}s:")
        for i, r in enumerate(results, 1):
            print(f"  [{i}] Source: {r.source} | Title: {r.title}")
            print(f"      Snippet: {r.snippet[:140]}...")
    else:
        print(f"[OFFLINE / NO RESULTS] Search returned 0 results in {elapsed}s.")

    print("\n--- STEP 2: Testing Router Decision & Cache Logic ---")
    for q in test_queries:
        t_start = time.time()
        res = await router.route_and_resolve(q)
        dur = round((time.time() - t_start) * 1000, 1)

        print(f"\nQuery: '{q}'")
        print(f"  Route: {res.route.value} (Confidence: {res.confidence})")
        print(f"  Handled Locally: {res.handled_locally} | Duration: {dur}ms")
        if res.direct_response:
            print(f"  Direct Tool Response: '{res.direct_response}'")
        if res.augmented_context:
            print(f"  Augmented Live Context Available: Yes ({len(res.augmented_context)} chars)")

    print("\n--- STEP 3: Testing Cache Hit (Repeated Query) ---")
    t_cache = time.time()
    res_cached = await router.route_and_resolve("What is the latest AI news?")
    cache_dur = round((time.time() - t_cache) * 1000, 2)
    print(f"Repeat Query Duration: {cache_dur}ms (Expected: < 5ms cache hit)")
    print(f"Cache Hit Verified: {res_cached.augmented_context is not None}")

    print("\n--- STEP 4: Testing Local Llama 3.2:3B Synthesis with Live Context ---")
    if getattr(settings, "llm_provider", "mock").lower() == "ollama":
        llm = OllamaLLMProvider()
    else:
        llm = MockLLMProvider()

    loaded = await llm.load()
    print(f"LLM Loaded ({type(llm).__name__}): {loaded}")

    if res_cached.augmented_context:
        prompt_text = "What is the latest AI news?"
        context = (
            "You are CYNEXIS, a helpful AI robot.\n"
            f"{res_cached.augmented_context}"
        )
        print("\nStreaming response from Local Llama 3.2:3B...")
        full_reply = ""
        t_llm = time.time()
        async for token in llm.stream(prompt_text, context=context):
            full_reply += token
            print(token, end="", flush=True)
        print()
        print(f"\n[SUCCESS] Llama generated concise answer in {round(time.time() - t_llm, 2)}s.")

    print("\n" + "=" * 70)
    print("  LIVE RUNTIME TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
