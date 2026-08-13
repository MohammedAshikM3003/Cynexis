"""
CYNEXIS — FastAPI Server
Main application with CORS, lifespan, and all routers mounted.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.constants import CYNEXIS_VERSION, ConnectionState, SystemMode
from core.logger import setup_logging, get_logger
from core.state import robot_state

from Database.database import db
from AI.Actions.actions import register_all_actions, inject_controllers

from .routes_health import router as health_router
from .routes_robot import router as robot_router
from .routes_camera import router as camera_router
from .routes_command import router as command_router
from .routes_voice import router as voice_router
from .routes_conversation import router as conversation_router, llm_router
from .ws_telemetry import router as ws_router
from .ws_voice import router as ws_voice_router

log = get_logger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # STARTUP
    setup_logging()
    log.info(f"CYNEXIS v{CYNEXIS_VERSION} starting...")
    log.info(f"Mock mode: {settings.mock_mode}")

    # Initialize database
    await db.initialize()
    await db.log_event("SYSTEM", "server", "CYNEXIS started")

    # Register all predefined actions
    register_all_actions()

    # Store references on app state for route access
    app.state.db = db

    if settings.mock_mode:
        from Backend.Robot.rover import MockRoverController
        from Backend.Robot.arm import MockArmController
        from Backend.Robot.gripper import MockGripperController
        from Backend.Vision.camera import MockCamera
        from AI.LLM.provider import MockLLMProvider
        from AI.STT.microphone import MockMicrophone
        from AI.TTS.provider import MockTTSProvider
        from AI.TTS.kokoro import KokoroTTSProvider
        from AI.Intent.engine import intent_engine

        from AI.Memory.provider import MockMemoryProvider
        from AI.Actions.registry import registry
        from Backend.Robot.Safety.safety import safety
        from AI.pipeline import VoicePipeline

        app.state.rover = MockRoverController()
        app.state.arm = MockArmController()
        app.state.gripper = MockGripperController()
        app.state.camera = MockCamera()
        await app.state.camera.start()

        if getattr(settings, "vision_provider", "mock").lower() == "local_vlm":
            from AI.Vision.vlm import LocalVLMProvider
            vision = LocalVLMProvider()
        else:
            from AI.Vision.provider import MockVisionProvider
            vision = MockVisionProvider()
        await vision.load()
        app.state.vision = vision

        # Inject controllers into action layer (ARCHITECTURE RULE #1)
        inject_controllers(
            rover=app.state.rover,
            arm=app.state.arm,
            gripper=app.state.gripper,
            camera=app.state.camera,
            vision=app.state.vision,
        )

        if getattr(settings, "llm_provider", "mock").lower() == "ollama":
            from AI.LLM.ollama_provider import OllamaLLMProvider
            llm = OllamaLLMProvider()
        else:
            llm = MockLLMProvider()
        await llm.load()
        app.state.llm = llm

        if getattr(settings, "stt_provider", "mock").lower() == "whisper":
            from AI.STT.whisper import WhisperSTTProvider
            stt = WhisperSTTProvider()
        else:
            from AI.STT.provider import MockSTTProvider
            stt = MockSTTProvider()
        await stt.load()
        mic = MockMicrophone()

        if getattr(settings, "tts_provider", "kokoro").lower() == "kokoro":
            tts = KokoroTTSProvider()
            await tts.load()  # Pre-warm: load Kokoro model NOW, not on first request
        else:
            tts = MockTTSProvider()
            await tts.load()
        app.state.tts = tts

        memory = MockMemoryProvider(max_conversation=getattr(settings, "ollama_context_window", 8) * 2)

        app.state.pipeline = VoicePipeline(
            stt=stt, tts=tts, llm=llm,
            intent=intent_engine, memory=memory,
            actions=registry, safety=safety,
            microphone=mic,
        )

        # Pre-warm Ollama synchronously — server is not ready until model is in RAM.
        # A 12 s safety timeout prevents a broken Ollama from hanging startup forever.
        if hasattr(llm, '_model') and llm.is_loaded():
            log.info("Pre-warming Ollama model into RAM (blocking — server ready after)...")
            try:
                await asyncio.wait_for(llm.generate("hi"), timeout=12.0)
                log.info("Ollama model pre-warmed successfully")
            except asyncio.TimeoutError:
                log.warning("Ollama pre-warm timed out after 12 s — server starting anyway")
            except Exception as e:
                log.warning(f"Ollama pre-warm failed (non-fatal): {e}")

        robot_state.ai.llm_loaded = True
        robot_state.ai.stt_loaded = True
        robot_state.ai.tts_loaded = tts.is_loaded()
        robot_state.ai.intent_ready = True
        robot_state.connection = ConnectionState.CONNECTED
        robot_state.mode = SystemMode.NORMAL

    else:
        # ---- HARDWARE / LIVE MODE ----
        from Backend.serial_bridge.transport import SerialTransport, MockTransport
        from Backend.serial_bridge.bridge import SerialBridge
        from Backend.Robot.rover import ESP32RoverController
        from Backend.Robot.esp32_arm import ESP32ArmController
        from Backend.Robot.esp32_gripper import ESP32GripperController
        from Backend.Vision.camera import MockCamera  # Camera still mock until HW ready
        from AI.LLM.provider import MockLLMProvider
        from AI.STT.microphone import LocalMicrophone
        from AI.TTS.kokoro import KokoroTTSProvider
        from AI.TTS.provider import MockTTSProvider
        from AI.Intent.engine import intent_engine
        from AI.Memory.provider import MockMemoryProvider
        from AI.Actions.registry import registry
        from Backend.Robot.Safety.safety import safety
        from AI.pipeline import VoicePipeline

        # Create transport (serial if port configured, else mock)
        if settings.esp32_serial_port:
            transport = SerialTransport(
                port=settings.esp32_serial_port,
                baud_rate=settings.esp32_baud_rate,
            )
            log.info(f"Using SerialTransport on {settings.esp32_serial_port}")
        else:
            transport = MockTransport(auto_respond=True)
            log.warning("No ESP32_SERIAL_PORT configured — using MockTransport")

        # Create bridge
        bridge = SerialBridge(
            transport=transport,
            command_timeout=settings.command_timeout_s,
            max_retries=settings.max_retries,
            heartbeat_interval=settings.heartbeat_interval_s,
            heartbeat_timeout=settings.heartbeat_timeout_s,
            motors_enabled=settings.hardware_motors_enabled,
        )
        app.state.bridge = bridge

        # Start bridge (connect + background tasks)
        bridge_ok = await bridge.start()
        if bridge_ok:
            log.info("SerialBridge started")
        else:
            log.warning("SerialBridge failed to connect — running in degraded mode")

        # Create controllers using bridge
        app.state.rover = ESP32RoverController(bridge)
        app.state.arm = ESP32ArmController(bridge)
        app.state.gripper = ESP32GripperController(bridge)
        from Backend.Vision.camera import OpenCVCamera
        cam = OpenCVCamera(settings.camera_device_index)
        await cam.start()
        if not cam.status().get("active"):
            log.warning("Physical camera device not active, falling back to MockCamera")
            cam = MockCamera()
            await cam.start()
        app.state.camera = cam

        if getattr(settings, "vision_provider", "mock").lower() == "local_vlm":
            from AI.Vision.vlm import LocalVLMProvider
            vision = LocalVLMProvider()
        else:
            from AI.Vision.provider import MockVisionProvider
            vision = MockVisionProvider()
        await vision.load()
        app.state.vision = vision

        inject_controllers(
            rover=app.state.rover,
            arm=app.state.arm,
            gripper=app.state.gripper,
            camera=app.state.camera,
            vision=app.state.vision,
        )

        if getattr(settings, "llm_provider", "mock").lower() == "ollama":
            from AI.LLM.ollama_provider import OllamaLLMProvider
            llm = OllamaLLMProvider()
        else:
            llm = MockLLMProvider()
        await llm.load()
        app.state.llm = llm

        if getattr(settings, "stt_provider", "mock").lower() == "whisper":
            from AI.STT.whisper import WhisperSTTProvider
            stt = WhisperSTTProvider()
        else:
            from AI.STT.provider import MockSTTProvider
            stt = MockSTTProvider()
        await stt.load()
        mic = LocalMicrophone()

        if getattr(settings, "tts_provider", "kokoro").lower() == "kokoro":
            tts = KokoroTTSProvider()
        else:
            tts = MockTTSProvider()
        await tts.load()
        app.state.tts = tts

        memory = MockMemoryProvider(max_conversation=getattr(settings, "ollama_context_window", 8) * 2)

        app.state.pipeline = VoicePipeline(
            stt=stt, tts=tts, llm=llm,
            intent=intent_engine, memory=memory,
            actions=registry, safety=safety,
            microphone=mic,
        )

        # Pre-warm Ollama synchronously — same as mock mode.
        if hasattr(llm, '_model') and llm.is_loaded():
            log.info("Pre-warming Ollama model into RAM (blocking — server ready after)...")
            try:
                await asyncio.wait_for(llm.generate("hi"), timeout=12.0)
                log.info("Ollama model pre-warmed successfully")
            except asyncio.TimeoutError:
                log.warning("Ollama pre-warm timed out after 12 s — server starting anyway")
            except Exception as e:
                log.warning(f"Ollama pre-warm failed (non-fatal): {e}")

        robot_state.ai.llm_loaded = True
        robot_state.ai.stt_loaded = True
        robot_state.ai.tts_loaded = tts.is_loaded()
        robot_state.ai.intent_ready = True
        robot_state.connection = ConnectionState.CONNECTED
        robot_state.mode = SystemMode.NORMAL

    # Start Glove Receiver Bridge (Read-Only Telemetry)
    if settings.glove_receiver_enabled and settings.glove_receiver_port:
        from Backend.serial_bridge.glove_receiver import GloveReceiverBridge
        glove_bridge = GloveReceiverBridge(
            port=settings.glove_receiver_port,
            baud_rate=settings.glove_receiver_baud,
            reconnect_interval=settings.glove_receiver_reconnect_interval_s,
            enabled=settings.glove_receiver_enabled,
        )
        app.state.glove_bridge = glove_bridge
        await glove_bridge.start()

    log.info(f"CYNEXIS v{CYNEXIS_VERSION} ready on {settings.api_host}:{settings.api_port}")

    yield

    # SHUTDOWN
    log.info("CYNEXIS shutting down...")
    if hasattr(app.state, "glove_bridge"):
        await app.state.glove_bridge.stop()
    if hasattr(app.state, "bridge"):
        await app.state.bridge.stop()
    if hasattr(app.state, "camera"):
        await app.state.camera.stop()
    if hasattr(app.state, "tts"):
        await app.state.tts.unload()
    await db.log_event("SYSTEM", "server", "CYNEXIS stopped")
    await db.close()


# Create FastAPI app
app = FastAPI(
    title="CYNEXIS API",
    description="AI-Powered Gesture-Controlled Robotic Platform",
    version=CYNEXIS_VERSION,
    lifespan=lifespan,
)

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health_router)
app.include_router(robot_router, prefix="/api")
app.include_router(camera_router, prefix="/api")
app.include_router(command_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(conversation_router, prefix="/api")
app.include_router(llm_router, prefix="/api")
app.include_router(ws_router)
app.include_router(ws_voice_router)



@app.get("/voice", include_in_schema=False)
@app.get("/lab", include_in_schema=False)
async def serve_voice_lab():
    """Serve the CYNEXIS Voice Pipeline Laboratory interface."""
    from fastapi.responses import HTMLResponse
    lab_file = settings.resolve_path("./Frontend/public/voice_lab.html")
    if lab_file.exists():
        with open(lab_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Voice Laboratory interface not found</h2>", status_code=404)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon placeholder to prevent browser console 404."""
    from fastapi.responses import Response
    return Response(status_code=204)

