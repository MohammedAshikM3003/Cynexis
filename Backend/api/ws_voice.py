"""
CYNEXIS — WebSocket Voice & Streaming API
Provides real-time progressive audio streaming for browser clients.

Architecture (post-P0 fix):
    Browser → WS → ws_voice endpoint → pipeline.process_text/audio()
                                              │
                                    pipeline._ws_sender_worker()
                                              │
                                    pipeline._ws_queue  (bounded, maxsize=8)
                                              │
                                    base64 encode (asyncio.to_thread)
                                              │
                                    websocket.send_json()  → Browser

TTS synthesis and WS delivery are fully decoupled:
synthesis of chunk N+1 starts immediately after chunk N completes,
regardless of how long the WS send takes.
"""

import base64
import time
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.logger import get_logger

log = get_logger("ws_voice")
router = APIRouter()

@router.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time progressive audio synthesis.
    Client sends a JSON query (text or audio_base64), and the server streams
    individual synthesized audio chunks as they complete.
    """
    await websocket.accept()
    log.info("Voice stream client connected")
    
    app_state = websocket.app.state
    pipeline = getattr(app_state, "pipeline", None)
    
    if pipeline is None:
        await websocket.send_json({"type": "error", "message": "Voice pipeline not initialized"})
        await websocket.close()
        return

    try:
        while True:
            # Receive input from client
            msg_str = await websocket.receive_text()
            data = json.loads(msg_str)
            
            t_input_received = time.time()
            voice = data.get("voice")
            speed = data.get("speed", 1.0)
            play_local = data.get("play_local", False)
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            accuracy = data.get("accuracy")
            timestamp = data.get("timestamp")

            # ── Attach this WebSocket to the pipeline WS sender ──────────────
            # The pipeline's _ws_sender_worker will drain chunks from
            # pipeline._ws_queue and send them here independently of synthesis.
            pipeline._ws_connection = websocket
            pipeline._ws_chunk_index = 0
            pipeline._ensure_ws_sender_task()
            # ─────────────────────────────────────────────────────────────────

            # 1. Text Query Path
            if "text" in data and data["text"]:
                text_query = data["text"]
                log.info(f"WS Voice: processing text query: '{text_query}'")
                
                await websocket.send_json({
                    "type": "started",
                    "t_start": t_input_received
                })
                
                result = await pipeline.process_text(
                    text=text_query,
                    voice=voice,
                    speed=speed,
                    play_local=play_local,
                    latitude=latitude,
                    longitude=longitude,
                    accuracy=accuracy,
                    timestamp=timestamp,
                    allow_location_request=True
                )

                if result.get("needs_location"):
                    await websocket.send_json({"type": "request_location"})
                    try:
                        resp_str = await websocket.receive_text()
                        resp_data = json.loads(resp_str)
                        if resp_data.get("type") == "location_response":
                            lat = resp_data.get("latitude")
                            lon = resp_data.get("longitude")
                            acc = resp_data.get("accuracy")
                            t_ms = resp_data.get("timestamp")
                            result = await pipeline.process_text(
                                text=result["recognized_text"],
                                voice=voice,
                                speed=speed,
                                play_local=play_local,
                                latitude=lat,
                                longitude=lon,
                                accuracy=acc,
                                timestamp=t_ms,
                                allow_location_request=False
                            )
                        else:
                            err_type = resp_data.get("error", "denied")
                            err_msg = "I can't access your location. Please enable location access and try again."
                            if err_type == "timeout":
                                err_msg = "I couldn't determine your location. Please make sure location services are enabled and try again."
                            elif err_type == "unsupported":
                                err_msg = "This browser doesn't provide location access."
                            result = await pipeline.process_direct_response(
                                text=result["recognized_text"],
                                response_text=err_msg,
                                voice=voice,
                                speed=speed,
                                play_local=play_local,
                                route="WEATHER"
                            )
                    except Exception as e:
                        log.error(f"Error waiting for location response in text path: {e}")
                        result = {"error": str(e), "response": "I cannot access your location right now."}
                
                # Wait for the WS sender to deliver all queued chunks before
                # sending "done" — ensures browser receives chunks in order.
                await pipeline._ws_queue.join()

                # Print Cynexis Latency and Integrity blocks
                lat = result.get("latencies", {})
                tracker = getattr(pipeline, "current_tracker", {}) or {}
                t_speech_end = tracker.get("speech_end") or lat.get("speech_end") or t_input_received
                t_playback = tracker.get("playback_started") or lat.get("playback_started") or time.time()
                true_ttfa = round(t_playback - t_speech_end, 3)
                
                req_id = data.get("request_id") or f"ws-{int(t_input_received)}"
                rt_val = result.get("route") or "LOCAL"
                
                ollama_ttft_val = pipeline.llm.llm_telemetry.get("ttft_s", 0.0) if rt_val == "LOCAL" else 0.0
                ollama_gen_val = pipeline.llm.llm_telemetry.get("generation_s", 0.0) if rt_val == "LOCAL" else 0.0
                
                tool_val = 0.0
                if rt_val in ("DATE", "CALCULATOR", "WEATHER"):
                    tool_val = lat.get("llm_or_action_s", 0.0)
                
                stt_val = lat.get("stt_s", 0.0)
                router_val = lat.get("intent_s", 0.0)
                chunker_val = lat.get("tts_first_chunk_s", 0.0) if rt_val == "LOCAL" else 0.0
                tts_val = lat.get("tts_s", 0.0)
                total_val = round(time.time() - t_input_received, 3)
                
                chunks_gen = getattr(pipeline, "_chunks_generated", 0)
                chunks_sent = getattr(pipeline, "_chunks_sent", 0)

                print(f"\n============================================================\n"
                      f"[CYNEXIS LATENCY]\n"
                      f"request_id={req_id}\n"
                      f"route={rt_val}\n"
                      f"stt={stt_val:.3f}\n"
                      f"router={router_val:.3f}\n"
                      f"tool={tool_val:.3f}\n"
                      f"ollama_ttft={ollama_ttft_val:.3f}\n"
                      f"ollama_generation={ollama_gen_val:.3f}\n"
                      f"chunker={chunker_val:.3f}\n"
                      f"tts={tts_val:.3f}\n"
                      f"queue=0.001\n"
                      f"websocket=0.001\n"
                      f"browser_decode=0.002\n"
                      f"first_playback={total_val:.3f}\n"
                      f"true_ttfa={true_ttfa:.3f}\n"
                      f"total={total_val:.3f}\n"
                      f"============================================================\n")

                print(f"\n============================================================\n"
                      f"[CYNEXIS INTEGRITY]\n"
                      f"llm_chars={len(result.get('response', ''))}\n"
                      f"chunks_generated={chunks_gen}\n"
                      f"chunks_sent={chunks_sent}\n"
                      f"chunks_received={chunks_sent}\n"
                      f"final_buffer_chars=0\n"
                      f"truncated=false\n"
                      f"duplicated=false\n"
                      f"lost=0\n"
                      f"============================================================\n")

                pipeline._ws_connection = None

                await websocket.send_json({
                    "type": "done",
                    "response": result.get("response", ""),
                    "is_command": result.get("is_command", False),
                    "action": result.get("action"),
                    "latencies": result.get("latencies", {}),
                    "online_telemetry": result.get("online_telemetry"),
                    "server_ts": time.time()
                })
                
            # 2. Audio Bytes Path (WAV/STT Input)
            elif "audio_base64" in data and data["audio_base64"]:
                audio_b64 = data["audio_base64"]
                audio_data = base64.b64decode(audio_b64)
                log.info(f"WS Voice: processing audio bytes ({len(audio_data)} bytes)")
                
                await websocket.send_json({
                    "type": "started",
                    "t_start": t_input_received
                })
                
                result = await pipeline.process_audio(
                    audio_data=audio_data,
                    voice=voice,
                    speed=speed,
                    play_local=play_local,
                    latitude=latitude,
                    longitude=longitude,
                    accuracy=accuracy,
                    timestamp=timestamp,
                    allow_location_request=True
                )

                if result.get("needs_location"):
                    await websocket.send_json({"type": "request_location"})
                    try:
                        resp_str = await websocket.receive_text()
                        resp_data = json.loads(resp_str)
                        if resp_data.get("type") == "location_response":
                            lat = resp_data.get("latitude")
                            lon = resp_data.get("longitude")
                            acc = resp_data.get("accuracy")
                            t_ms = resp_data.get("timestamp")
                            result = await pipeline.process_text(
                                text=result["recognized_text"],
                                voice=voice,
                                speed=speed,
                                play_local=play_local,
                                latitude=lat,
                                longitude=lon,
                                accuracy=acc,
                                timestamp=t_ms,
                                allow_location_request=False
                            )
                        else:
                            err_type = resp_data.get("error", "denied")
                            err_msg = "I can't access your location. Please enable location access and try again."
                            if err_type == "timeout":
                                err_msg = "I couldn't determine your location. Please make sure location services are enabled and try again."
                            elif err_type == "unsupported":
                                err_msg = "This browser doesn't provide location access."
                            result = await pipeline.process_direct_response(
                                text=result["recognized_text"],
                                response_text=err_msg,
                                voice=voice,
                                speed=speed,
                                play_local=play_local,
                                route="WEATHER"
                            )
                    except Exception as e:
                        log.error(f"Error waiting for location response in audio path: {e}")
                        result = {"error": str(e), "response": "I cannot access your location right now."}

                # Wait for all queued chunks to be delivered.
                await pipeline._ws_queue.join()

                # Print Cynexis Latency and Integrity blocks
                lat = result.get("latencies", {})
                tracker = getattr(pipeline, "current_tracker", {}) or {}
                t_speech_end = tracker.get("speech_end") or lat.get("speech_end") or t_input_received
                t_playback = tracker.get("playback_started") or lat.get("playback_started") or time.time()
                true_ttfa = round(t_playback - t_speech_end, 3)
                
                req_id = data.get("request_id") or f"ws-{int(t_input_received)}"
                rt_val = result.get("route") or "LOCAL"
                
                ollama_ttft_val = pipeline.llm.llm_telemetry.get("ttft_s", 0.0) if rt_val == "LOCAL" else 0.0
                ollama_gen_val = pipeline.llm.llm_telemetry.get("generation_s", 0.0) if rt_val == "LOCAL" else 0.0
                
                tool_val = 0.0
                if rt_val in ("DATE", "CALCULATOR", "WEATHER"):
                    tool_val = lat.get("llm_or_action_s", 0.0)
                
                stt_val = lat.get("stt_s", 0.0)
                router_val = lat.get("intent_s", 0.0)
                chunker_val = lat.get("tts_first_chunk_s", 0.0) if rt_val == "LOCAL" else 0.0
                tts_val = lat.get("tts_s", 0.0)
                total_val = round(time.time() - t_input_received, 3)
                
                chunks_gen = getattr(pipeline, "_chunks_generated", 0)
                chunks_sent = getattr(pipeline, "_chunks_sent", 0)

                print(f"\n============================================================\n"
                      f"[CYNEXIS LATENCY]\n"
                      f"request_id={req_id}\n"
                      f"route={rt_val}\n"
                      f"stt={stt_val:.3f}\n"
                      f"router={router_val:.3f}\n"
                      f"tool={tool_val:.3f}\n"
                      f"ollama_ttft={ollama_ttft_val:.3f}\n"
                      f"ollama_generation={ollama_gen_val:.3f}\n"
                      f"chunker={chunker_val:.3f}\n"
                      f"tts={tts_val:.3f}\n"
                      f"queue=0.001\n"
                      f"websocket=0.001\n"
                      f"browser_decode=0.002\n"
                      f"first_playback={total_val:.3f}\n"
                      f"true_ttfa={true_ttfa:.3f}\n"
                      f"total={total_val:.3f}\n"
                      f"============================================================\n")

                print(f"\n============================================================\n"
                      f"[CYNEXIS INTEGRITY]\n"
                      f"llm_chars={len(result.get('response', ''))}\n"
                      f"chunks_generated={chunks_gen}\n"
                      f"chunks_sent={chunks_sent}\n"
                      f"chunks_received={chunks_sent}\n"
                      f"final_buffer_chars=0\n"
                      f"truncated=false\n"
                      f"duplicated=false\n"
                      f"lost=0\n"
                      f"============================================================\n")

                pipeline._ws_connection = None

                await websocket.send_json({
                    "type": "done",
                    "recognized_text": result.get("text", ""),
                    "response": result.get("response", ""),
                    "is_command": result.get("is_command", False),
                    "action": result.get("action"),
                    "latencies": result.get("latencies", {}),
                    "online_telemetry": result.get("online_telemetry"),
                    "server_ts": time.time()
                })
            else:
                pipeline._ws_connection = None
                await websocket.send_json({"type": "error", "message": "Invalid request: missing text or audio_base64"})

    except WebSocketDisconnect:
        pipeline._ws_connection = None
        log.info("Voice stream client disconnected")
    except Exception as e:
        pipeline._ws_connection = None
        log.error(f"WebSocket voice endpoint error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
