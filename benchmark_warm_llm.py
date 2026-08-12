import sys
import time
import asyncio
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
settings.mock_mode = False
settings.llm_provider = "ollama"
settings.ollama_max_tokens = 80
settings.ollama_temperature = 0.4
# We will verify settings.ollama_model is llama3.2:3b when running, but for the script we just use whatever is configured

from AI.LLM.ollama_provider import OllamaLLMProvider

async def main():
    print("=" * 70)
    print(f"  CYNEXIS LLM Latency Benchmark: {settings.ollama_model}")
    print("=" * 70)

    llm = OllamaLLMProvider()
    print("Connecting to Ollama server and loading model...")
    loaded = await llm.load()
    if not loaded:
        print("ERROR: Failed to connect to Ollama server or find model.")
        return

    # Warm-up run
    print("\nRunning warm-up inference...")
    warmup_prompt = "Explain robotics in one sentence."
    response = ""
    async for token in llm.stream(warmup_prompt):
        response += token
    print(f"Warm-up complete. Response: \"{response.strip()}\"")
    print(f"Warm-up stats: TTFT={llm.llm_telemetry['ttft_s']}s | Gen={llm.llm_telemetry['generation_s']}s | tokens/sec={llm.llm_telemetry['tokens_per_sec']}")

    # 10 Benchmark Runs
    print("\nRunning 10 benchmark runs...")
    prompt = "Explain the three laws of robotics in a concise paragraph."
    
    ttfts = []
    tokens_per_secs = []
    gen_times = []
    token_counts = []

    for i in range(1, 11):
        print(f"  Run {i:02d}... ", end="", flush=True)
        t_start = time.time()
        
        resp = ""
        async for token in llm.stream(prompt):
            resp += token
            
        dt = time.time() - t_start
        telemetry = llm.llm_telemetry
        
        ttft = telemetry.get("ttft_s")
        tps = telemetry.get("tokens_per_sec")
        gen_time = telemetry.get("generation_s")
        toks = telemetry.get("tokens_generated")
        
        if ttft is not None:
            ttfts.append(ttft)
        if tps is not None:
            tokens_per_secs.append(tps)
        if gen_time is not None:
            gen_times.append(gen_time)
        if toks is not None:
            token_counts.append(toks)
            
        print(f"TTFT={ttft:.3f}s | Gen={gen_time:.2f}s | {tps} tok/sec | {toks} tokens")

    # Calculate statistics
    avg_ttft = sum(ttfts) / len(ttfts) if ttfts else 0
    min_ttft = min(ttfts) if ttfts else 0
    max_ttft = max(ttfts) if ttfts else 0

    avg_tps = sum(tokens_per_secs) / len(tokens_per_secs) if tokens_per_secs else 0
    min_tps = min(tokens_per_secs) if tokens_per_secs else 0
    max_tps = max(tokens_per_secs) if tokens_per_secs else 0

    avg_gen = sum(gen_times) / len(gen_times) if gen_times else 0
    min_gen = min(gen_times) if gen_times else 0
    max_gen = max(gen_times) if gen_times else 0

    avg_tok = sum(token_counts) / len(token_counts) if token_counts else 0

    print("\n" + "=" * 70)
    print("  BENCHMARK SUMMARY STATISTICS")
    print("=" * 70)
    print(f"Model            : {settings.ollama_model}")
    print(f"Average Warm TTFT: {avg_ttft:.3f}s (Min: {min_ttft:.3f}s, Max: {max_ttft:.3f}s)")
    print(f"Average Speed    : {avg_tps:.1f} tokens/sec (Min: {min_tps:.1f}, Max: {max_tps:.1f})")
    print(f"Average Gen Time : {avg_gen:.2f}s (Min: {min_gen:.2f}s, Max: {max_gen:.2f}s)")
    print(f"Average Tokens   : {avg_tok:.1f}")
    print("=" * 70)

    await llm.unload()

if __name__ == "__main__":
    asyncio.run(main())
