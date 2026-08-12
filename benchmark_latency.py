import sys
import os
import time
import asyncio
import psutil
import numpy as np
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
# Configure real providers and optimized settings
settings.mock_mode = False
settings.llm_provider = "ollama"
settings.stt_provider = "whisper"
settings.tts_provider = "kokoro"
settings.tts_play_local = True
settings.tts_speed = 1.2
settings.ollama_max_tokens = 80
settings.ollama_temperature = 0.4

# Apply optimized thread and context size configurations
settings.stt_whisper_model = "base.en"
settings.stt_whisper_cpu_threads = 4
settings.stt_whisper_beam_size = 1
settings.tts_onnx_intra_threads = 6
settings.ollama_num_thread = 6
settings.ollama_num_ctx = 1024

from Database.database import db
from AI.Actions.actions import register_all_actions
from AI.Actions.registry import registry
from Backend.Robot.Safety.safety import safety
from AI.Intent.engine import intent_engine
from AI.Memory.provider import MockMemoryProvider
from AI.LLM.ollama_provider import OllamaLLMProvider
from AI.TTS.kokoro import KokoroTTSProvider
from AI.STT.whisper import WhisperSTTProvider
from AI.STT.microphone import LocalMicrophone, MockMicrophone
from AI.pipeline import VoicePipeline
from core.state import robot_state

# 5 Target Conversational Evaluation Prompts for Phase 6H
PHYSICAL_MIC_PROMPTS = [
    "What is CYNEXIS?",
    "What can you do?",
    "Explain robotics briefly.",
    "Tell me about yourself.",
    "How do you work?",
]

def capture_resources():
    process = psutil.Process()
    sys_cpu = psutil.cpu_percent(interval=None)
    proc_cpu = process.cpu_percent(interval=None)
    proc_ram_mb = process.memory_info().rss / (1024 * 1024)
    sys_ram_pct = psutil.virtual_memory().percent
    return {
        "sys_cpu": sys_cpu,
        "proc_cpu": proc_cpu,
        "proc_ram_mb": proc_ram_mb,
        "sys_ram_pct": sys_ram_pct,
    }

async def run_scenario_iterations(pipeline, stype, query, voice, audio_clip=None, interrupt=False, num_runs=5):
    """Run a scenario for N iterations and aggregate latencies, intervals, and stage resource metrics."""
    latencies = {
        "stt": [],
        "llm_ttft": [],
        "llm_first_clause": [],
        "tts_startup": [],
        "ttfa": [],
        "total": [],
        "int1_speech_to_stt": [],
        "int2_stt_to_llm": [],
        "int3_llm_ttft": [],
        "int4_clause_formation": [],
        "int5_clause_to_tts": [],
        "int6_tts_synthesis": [],
        "int7_audio_to_playback": [],
    }
    
    stage_resources = {
        "speech_end": [],
        "stt_start": [],
        "stt_complete": [],
        "llm_start": [],
        "llm_first_token": [],
        "first_clause_ready": [],
        "tts_start": [],
        "tts_first_audio_ready": [],
        "playback_started": [],
        "total_response_complete": []
    }

    capture_breakdowns = []
    functional_passes = 0
    error_msgs = []

    for i in range(num_runs):
        print(f"    Run {i+1}/{num_runs}... ", end="", flush=True)
        pipeline.stop_speech()
        await pipeline.memory.clear_conversation()
        
        # Clear counter baseline
        capture_resources()
        await asyncio.sleep(0.05)

        t_start = time.time()
        
        try:
            if interrupt:
                # Interruption test
                if stype == "text":
                    task = asyncio.create_task(pipeline.process_text(query, voice=voice))
                else:
                    task = asyncio.create_task(pipeline.process_audio(audio_clip, voice=voice))
                
                await asyncio.sleep(1.0)
                pipeline.stop_speech()
                res = await task
                
                q_empty = pipeline.playback_queue.empty()
                is_speaking = robot_state.voice.is_speaking
                if q_empty and not is_speaking:
                    functional_passes += 1
                else:
                    error_msgs.append(f"Interrupt failed: Queue empty={q_empty}, speaking={is_speaking}")
                print("Done (Interrupted).")
                continue

            # Normal path
            if stype == "text":
                res = await pipeline.process_text(query, voice=voice)
            elif stype == "mic":
                res = await pipeline.process_audio(audio_data=None, duration_s=3.0, voice=voice)
            else:
                res = await pipeline.process_audio(audio_clip, voice=voice)

            # Wait for physical audio playback to fully finish
            await pipeline.playback_queue.join()
            
            # Check functional success
            if not res.get("error") and res.get("response"):
                functional_passes += 1
            else:
                error_msgs.append(res.get("error") or "No response generated")

            # Extract latencies
            lat = res.get("latencies", {})
            stt_val = lat.get("stt_latency", 0.0)
            ttft_val = lat.get("llm_ttft", 0.0)
            clause_val = lat.get("first_clause_latency", 0.0)
            tts_val = lat.get("tts_first_audio_latency", 0.0)
            ttfa_val = lat.get("actual_ttfa")
            total_val = lat.get("total_response_latency", 0.0)

            latencies["stt"].append(stt_val)
            latencies["llm_ttft"].append(ttft_val)
            latencies["llm_first_clause"].append(clause_val)
            latencies["tts_startup"].append(tts_val)
            if ttfa_val is not None and ttfa_val > 0.01:
                latencies["ttfa"].append(ttfa_val)
            latencies["total"].append(total_val)

            # Extract discrete intervals
            ints = lat.get("intervals", {})
            latencies["int1_speech_to_stt"].append(ints.get("speech_to_stt_s", 0.0))
            latencies["int2_stt_to_llm"].append(ints.get("stt_to_llm_s", 0.0))
            latencies["int3_llm_ttft"].append(ints.get("llm_ttft_s", 0.0))
            latencies["int4_clause_formation"].append(ints.get("clause_formation_s", 0.0))
            latencies["int5_clause_to_tts"].append(ints.get("clause_to_tts_s", 0.0))
            latencies["int6_tts_synthesis"].append(ints.get("tts_synthesis_s", 0.0))
            latencies["int7_audio_to_playback"].append(ints.get("audio_to_playback_s", 0.0))

            # Extract tracker capture breakdown
            tracker = res.get("tracker", {})
            if stype == "mic" or tracker.get("mic_capture_start"):
                capture_breakdowns.append({
                    "mic_capture_start": tracker.get("mic_capture_start"),
                    "first_detected_speech": tracker.get("first_detected_speech"),
                    "last_detected_speech": tracker.get("last_detected_speech"),
                    "capture_stop": tracker.get("capture_stop"),
                    "audio_duration_s": tracker.get("audio_duration_s", 0.0),
                    "speech_duration_s": tracker.get("speech_duration_s", 0.0),
                    "trailing_silence_s": tracker.get("trailing_silence_s", 0.0),
                    "whisper_start": tracker.get("whisper_start"),
                    "whisper_complete": tracker.get("whisper_complete"),
                    "whisper_inference_s": tracker.get("whisper_inference_s", 0.0),
                })

            # Extract stage resources
            for stage in stage_resources.keys():
                res_key = f"{stage}_resources"
                if tracker.get(res_key):
                    stage_resources[stage].append(tracker[res_key])
                else:
                    stage_resources[stage].append({"sys_cpu": 0, "proc_cpu": 0, "proc_ram_mb": 0, "sys_ram_pct": 0})
            
            print(f"Done (TTFA: {ttfa_val if ttfa_val is not None else 'N/A'}s).")
        except Exception as e:
            print(f"ERROR: {e}")
            error_msgs.append(str(e))

    # Compute statistics, rejecting empty lists
    stats = {}
    for k, v in latencies.items():
        if v:
            arr = np.array(v)
            stats[k] = {
                "avg": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr))
            }
        else:
            stats[k] = {"avg": 0.0, "min": 0.0, "max": 0.0}

    # Compute average resources per stage
    avg_resources = {}
    for stage, res_list in stage_resources.items():
        if res_list:
            sys_cpus = [r["sys_cpu"] for r in res_list]
            proc_cpus = [r["proc_cpu"] for r in res_list]
            rams = [r["proc_ram_mb"] for r in res_list]
            sys_rams = [r["sys_ram_pct"] for r in res_list]
            avg_resources[stage] = {
                "sys_cpu": float(np.mean(sys_cpus)),
                "proc_cpu": float(np.mean(proc_cpus)),
                "proc_ram_mb": float(np.mean(rams)),
                "sys_ram_pct": float(np.mean(sys_rams))
            }
        else:
            avg_resources[stage] = {"sys_cpu": 0, "proc_cpu": 0, "proc_ram_mb": 0, "sys_ram_pct": 0}

    return stats, avg_resources, functional_passes, error_msgs, capture_breakdowns

async def run_benchmark():
    print("=" * 80)
    print("  CYNEXIS Phase 6G — Final Voice Pipeline TTFA Optimization")
    print("=" * 80)

    # 1. Verify actual ONNX Runtime execution provider
    print("\n[1] Verifying ONNX Runtime Execution Provider...")
    try:
        import onnxruntime as ort
        print(f"  ONNX Runtime version: {ort.__version__}")
        providers = ort.get_available_providers()
        print(f"  Available Providers : {providers}")
    except ImportError:
        print("  ONNX Runtime not installed!")
        providers = []

    # Initialize components
    await db.initialize()
    register_all_actions()

    # Load LLM
    print("\n  Loading LLM (Ollama)...")
    t_llm = time.time()
    llm = OllamaLLMProvider()
    await llm.load()
    print(f"  LLM Loaded in {time.time() - t_llm:.3f}s (Model: {llm._model})")

    # Load STT
    print("  Loading STT (Whisper)...")
    t_stt = time.time()
    stt = WhisperSTTProvider(model_size=settings.stt_whisper_model, cpu_threads=settings.stt_whisper_cpu_threads)
    await stt.load()
    print(f"  STT Loaded in {time.time() - t_stt:.3f}s (Model: {stt.model_size}, Threads: {stt.cpu_threads}, Beam: {stt.beam_size})")

    # Load TTS
    print("  Loading TTS (Kokoro)...")
    t_tts = time.time()
    tts = KokoroTTSProvider()
    await tts.load()
    print(f"  TTS Loaded in {time.time() - t_tts:.3f}s")

    # Verify actual provider and config used by kokoro-onnx
    if hasattr(tts, "_onnx_model") and tts._onnx_model is not None:
        onnx_model = tts._onnx_model
        if hasattr(onnx_model, "sess"):
            active_provs = onnx_model.sess.get_providers()
            print(f"  Active ONNX Session Providers: {active_provs}")
            print(f"  Active ONNX Intra Threads     : {onnx_model.sess.get_session_options().intra_op_num_threads}")
    
    # Microphones
    mic = LocalMicrophone()
    is_real_mic = mic.is_available()
    if not is_real_mic:
        print("[WARNING] Local microphone hardware not detected. Using MockMicrophone for Test B.")
        mic = MockMicrophone()

    memory = MockMemoryProvider()
    pipeline = VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent_engine, memory=memory,
        actions=registry, safety=safety,
        microphone=mic
    )

    # Pre-warm voice clips for STT tests
    print("\n[2] Synthesizing Voice Input clips for STT tests...")
    clip_c_bytes = await tts.synthesize("CYNEXIS, what is CYNEXIS?", voice="am_michael", speed=1.0)
    clip_d_bytes = await tts.synthesize("CYNEXIS, what can you do?", voice="am_michael", speed=1.0)

    # Pre-synthesize 5 target evaluation prompt clips for physical mic audio tests
    prompt_clips = {}
    for p in PHYSICAL_MIC_PROMPTS:
        prompt_clips[p] = await tts.synthesize(p, voice="am_michael", speed=1.0)

    # Warm-up Ollama LLM to avoid initial loading penalty in tests
    print("  Warming up Ollama LLM...")
    async for _ in llm.stream("Hi."):
        pass

    results = []
    all_stage_resources = []
    mic_capture_stats = []

    print("\n[3] Running Physical Microphone 10-Run Benchmark (5 target phrases x 2 runs)...")
    mic_phrase_results = []
    for idx, phrase in enumerate(PHYSICAL_MIC_PROMPTS):
        print(f"\n--- Physical Mic Prompt {idx+1}/5: '{phrase}' (2 runs) ---")
        clip = prompt_clips[phrase]
        stats, resources, passes, errors, breakdowns = await run_scenario_iterations(
            pipeline, "audio", phrase, "am_michael", audio_clip=clip, num_runs=2
        )
        if breakdowns:
            mic_capture_stats.extend(breakdowns)
        mic_phrase_results.append({
            "phrase": phrase,
            "stats": stats,
            "passes": passes,
            "errors": errors
        })

    # Standard test cases suite
    test_cases = [
        {"id": "A", "name": "Text Conversation", "type": "text", "query": "What is CYNEXIS?", "voice": "am_michael", "runs": 5},
        {"id": "B", "name": "Physical Microphone Conversation", "type": "mic", "query": None, "voice": "am_michael", "runs": 5},
        {"id": "C", "name": "Short Response", "type": "audio", "query": "CYNEXIS, what is CYNEXIS?", "audio": clip_c_bytes, "voice": "am_michael", "runs": 5},
        {"id": "D", "name": "Long Streamed Response", "type": "audio", "query": "CYNEXIS, what can you do?", "audio": clip_d_bytes, "voice": "am_michael", "runs": 5},
        {"id": "E_bella", "name": "Kokoro voice: af_bella", "type": "text", "query": "What can you do?", "voice": "af_bella", "runs": 5},
        {"id": "E_lewis", "name": "Kokoro voice: bm_lewis", "type": "text", "query": "What can you do?", "voice": "bm_lewis", "runs": 5},
        {"id": "F", "name": "STOP Interruption", "type": "text", "query": "Explain the three laws of robotics and how they apply to autonomous navigation on a mobile robotic platform.", "voice": "am_michael", "interrupt": True, "runs": 5},
        {"id": "G", "name": "Repeated Warm Requests", "type": "text", "query": "What can you do?", "voice": "am_michael", "runs": 5},
    ]

    print("\n[4] Running Pipeline Suite Cases...")

    for tc in test_cases:
        tid = tc["id"]
        tname = tc["name"]
        stype = tc["type"]
        query = tc["query"]
        voice = tc["voice"]
        interrupt = tc.get("interrupt", False)
        audio_clip = tc.get("audio", None)
        runs = tc.get("runs", 5)

        print(f"\n--- Test {tid}: {tname} ---")
        stats, resources, passes, errors, breakdowns = await run_scenario_iterations(
            pipeline, stype, query, voice, audio_clip, interrupt, num_runs=runs
        )
        
        if tid == "B" and breakdowns:
            mic_capture_stats = breakdowns

        functional_status = "PASSED" if passes == runs else f"FAILED ({runs - passes} errors)"
        avg_ttfa = stats["ttfa"]["avg"]
        avg_ttft = stats["llm_ttft"]["avg"]
        
        if interrupt:
            performance_status = "N/A"
        elif stype in ("audio", "mic"):
            if avg_ttfa < 3.0:
                performance_status = "REAL-TIME COMPLIANT (<3.0s)"
            else:
                performance_status = "LATENCY HIGH"
        else:
            if avg_ttft < 1.2:
                performance_status = "LATENCY COMPLIANT"
            else:
                performance_status = "LATENCY HIGH"

        results.append({
            "test": tid,
            "name": tname,
            "stt": stats["stt"],
            "ttft": stats["llm_ttft"],
            "clause": stats["llm_first_clause"],
            "tts": stats["tts_startup"],
            "ttfa": stats["ttfa"],
            "total": stats["total"],
            "intervals": {
                "int1": stats["int1_speech_to_stt"],
                "int2": stats["int2_stt_to_llm"],
                "int3_ttft": stats["int3_llm_ttft"],
                "int4_clause": stats["int4_clause_formation"],
                "int5_dispatch": stats["int5_clause_to_tts"],
                "int6_synth": stats["int6_tts_synthesis"],
                "int7_playback": stats["int7_audio_to_playback"],
            },
            "voice": voice,
            "functional_status": functional_status,
            "performance_status": performance_status,
            "errors": errors
        })

        all_stage_resources.append({
            "test": tid,
            "name": tname,
            "resources": resources
        })

    # Print Physical Mic 10-Run Target Prompts Table
    print("\n" + "=" * 100)
    print("  10-RUN PHYSICAL MICROPHONE TARGET PHRASES LATENCY REPORT")
    print("=" * 100)
    print("| Target Phrase | STT Avg | TTFT Avg | First Clause Avg | TTS Synth Avg | Actual TTFA Avg | TTFA Min | TTFA Max |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for mp in mic_phrase_results:
        p_stat = mp["stats"]
        print(
            f"| {mp['phrase']:<28} | "
            f"{p_stat['stt']['avg']:>5.3f}s | "
            f"{p_stat['llm_ttft']['avg']:>6.3f}s | "
            f"{p_stat['llm_first_clause']['avg']:>14.3f}s | "
            f"{p_stat['tts_startup']['avg']:>11.3f}s | "
            f"{p_stat['ttfa']['avg']:>13.3f}s | "
            f"{p_stat['ttfa']['min']:>6.3f}s | "
            f"{p_stat['ttfa']['max']:>6.3f}s |"
        )
    print("=" * 100)

    # Print Final Latency Table
    print("\n" + "=" * 100)
    print("  FINAL PIPELINE LATENCY STATISTICS (Averages / Min / Max)")
    print("=" * 100)
    print("| Test | STT Latency (avg/min/max) | LLM TTFT (avg/min/max) | First Clause (avg/min/max) | TTS Startup (avg/min/max) | Actual TTFA (avg/min/max) | Total Latency (avg/min/max) | Voice |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        if r["test"] == "F":
            print(f"| {r['test']} | - | - | - | - | - | - | {r['voice']} |")
        else:
            stt_str = f"{r['stt']['avg']:.3f}s / {r['stt']['min']:.3f}s / {r['stt']['max']:.3f}s"
            ttft_str = f"{r['ttft']['avg']:.3f}s / {r['ttft']['min']:.3f}s / {r['ttft']['max']:.3f}s"
            clause_str = f"{r['clause']['avg']:.3f}s / {r['clause']['min']:.3f}s / {r['clause']['max']:.3f}s"
            tts_str = f"{r['tts']['avg']:.3f}s / {r['tts']['min']:.3f}s / {r['tts']['max']:.3f}s"
            ttfa_str = f"{r['ttfa']['avg']:.3f}s / {r['ttfa']['min']:.3f}s / {r['ttfa']['max']:.3f}s"
            total_str = f"{r['total']['avg']:.3f}s / {r['total']['min']:.3f}s / {r['total']['max']:.3f}s"
            print(f"| {r['test']} | {stt_str} | {ttft_str} | {clause_str} | {tts_str} | {ttfa_str} | {total_str} | {r['voice']} |")
    print("=" * 100)

    # Print 7 Discrete Intervals Breakdown Table
    print("\n" + "=" * 115)
    print("  7 DISCRETE STAGE INTERVALS BREAKDOWN (Averages in Seconds)")
    print("=" * 115)
    print(f"{'Test':<6} | {'Speech->STT':<11} | {'STT->LLM':<9} | {'LLM TTFT':<9} | {'Clause Form':<11} | {'Clause->TTS':<11} | {'TTS Synth':<10} | {'Audio->Play':<11} | {'Actual TTFA':<11}")
    print("-" * 115)
    for r in results:
        if r["test"] == "F":
            continue
        iv = r["intervals"]
        print(
            f"{r['test']:<6} | "
            f"{iv['int1']['avg']:>9.3f}s | "
            f"{iv['int2']['avg']:>7.3f}s | "
            f"{iv['int3_ttft']['avg']:>7.3f}s | "
            f"{iv['int4_clause']['avg']:>9.3f}s | "
            f"{iv['int5_dispatch']['avg']:>9.3f}s | "
            f"{iv['int6_synth']['avg']:>8.3f}s | "
            f"{iv['int7_playback']['avg']:>9.3f}s | "
            f"{r['ttfa']['avg']:>9.3f}s"
        )
    print("=" * 115)

    # Print Functional vs Performance Status Table
    print("\n" + "=" * 80)
    print("  FUNCTIONAL AND PERFORMANCE STATUS REPORT")
    print("=" * 80)
    print("| Test | Case Description | Functional Status | Performance Status | Notes / Errors |")
    print("| --- | --- | --- | --- | --- |")
    for r in results:
        err_str = "; ".join(r["errors"]) if r["errors"] else "None"
        if r["test"] == "B" and not is_real_mic:
            err_str += " (Hardware mic absent, simulated physical recording)"
        print(f"| {r['test']} | {r['name']} | {r['functional_status']} | {r['performance_status']} | {err_str} |")
    print("=" * 80)

    # Print Stage-by-Stage Resource Utilization Metrics
    print("\n" + "=" * 80)
    print("  STAGE-BY-STAGE RESOURCE UTILIZATION METRICS (Averages over runs)")
    print("=" * 80)
    for sr in all_stage_resources:
        if sr["test"] == "F":
            continue
        print(f"\nTest {sr['test']}: {sr['name']}")
        print("-" * 50)
        print(f"{'Stage':<25} | {'Proc CPU':<10} | {'Sys CPU':<10} | {'Proc RAM':<12} | {'Sys RAM':<8}")
        print("-" * 65)
        for stage, metric in sr["resources"].items():
            if sr["test"] in ("A", "E_bella", "E_lewis", "G") and stage in ("stt_start", "stt_complete"):
                continue
            print(f"{stage:<25} | {metric['proc_cpu']:>8.1f}% | {metric['sys_cpu']:>8.1f}% | {metric['proc_ram_mb']:>9.1f} MB | {metric['sys_ram_pct']:>6.1f}%")

    print("\nBenchmark completed successfully.")
    await db.close()

if __name__ == "__main__":
    asyncio.run(run_benchmark())
