"""
CYNEXIS — Warm latency benchmark.
Request 1: cold-start (loads model into RAM, keep_alive=-1 keeps it there).
Request 2: warm (real production TTFT with model already in memory).
Request 3: warm (confirm consistency).
"""
import sys, asyncio, httpx, time
sys.path.insert(0, 'D:/Cynexis')

BASE = 'http://localhost:8000'
PROMPTS = [
    ("What is CYNEXIS?",              "warm-up / cold start"),
    ("What can you do?",              "WARM run 1"),
    ("Explain robotics in one sentence.", "WARM run 2"),
]

async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=180) as c:
        print("=" * 60)
        print("  CYNEXIS warm latency test (keep_alive=-1 applied)")
        print("=" * 60)
        for i, (prompt, label) in enumerate(PROMPTS):
            print(f"\n[{label}]  \"{prompt}\"")
            t0 = time.monotonic()
            r = await c.post('/api/conversation/text', json={
                'text': prompt,
                'voice': 'am_michael',
                'play_local': True,
            })
            wall = round(time.monotonic() - t0, 3)
            d = r.json()
            lat = d.get('latencies', {})
            print(f"  Response:    {str(d.get('response',''))[:80]}")
            print(f"  TTS:         {d.get('tts_provider')}")
            print(f"  Intent:      {lat.get('intent_s')}s")
            print(f"  LLM+action:  {lat.get('llm_or_action_s')}s")
            print(f"  TTS synth:   {lat.get('tts_s')}s")
            print(f"  Total:       {lat.get('total_s')}s")
            print(f"  Wall clock:  {wall}s")
            if d.get('error'):
                print(f"  ERROR:       {d['error']}")

if __name__ == "__main__":
    asyncio.run(run())
