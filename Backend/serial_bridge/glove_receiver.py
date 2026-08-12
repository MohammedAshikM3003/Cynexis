"""
CYNEXIS — Glove Telemetry Receiver
====================================
Dedicated, read-only serial telemetry bridge for the Control Glove receiver.

Key Guarantees:
- Read-only: Never writes or transmits commands to the receiver COM port.
- Non-blocking: Runs in a dedicated background worker thread to prevent event-loop blocking.
- Dual-mode parser: Handles both structured JSON HAND_DATA packets and legacy plaintext.
- Resilient: Auto-reconnects on disconnection and never raises exceptions that crash CYNEXIS.
- Isolated: Decoupled from the main ESP32 Gateway SerialBridge and robot motor control.
"""

import asyncio
import threading
import json
import re
import time
from typing import Optional, Callable, Awaitable
from datetime import datetime, timezone

from core.logger import get_logger
from core.state import robot_state
from core.config import settings
from core.calibration import (
    load_calibration,
    HandCalibrationProfile,
    FlexSensorFilter,
)
from core.gestures import HandGestureRecognizer, GestureThresholds

log = get_logger("glove_receiver")

# Regex pattern for plaintext fallback: "Thumb: 123   Index: 456"
PLAINTEXT_PATTERN = re.compile(
    r"Thumb:\s*(-?\d+)\s+Index:\s*(-?\d+)",
    re.IGNORECASE
)

# Valid sensor value bounds (12-bit ADC range)
MIN_ADC_VAL = 0
MAX_ADC_VAL = 4095


class GloveReceiverBridge:
    """
    Threaded, read-only receiver for hand/glove telemetry data.
    Runs a worker thread reading standard pyserial without blocking asyncio loops.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: Optional[int] = None,
        reconnect_interval: Optional[float] = None,
        enabled: Optional[bool] = None,
    ):
        self._port = port if port is not None else settings.glove_receiver_port
        self._baud_rate = baud_rate if baud_rate is not None else settings.glove_receiver_baud
        self._reconnect_interval = (
            reconnect_interval if reconnect_interval is not None
            else settings.glove_receiver_reconnect_interval_s
        )
        self._enabled = enabled if enabled is not None else settings.glove_receiver_enabled

        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._serial_obj = None
        self._last_packet_time: Optional[datetime] = None
        self._packets_received: int = 0
        self._callback: Optional[Callable[[int, int], Awaitable[None]]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Calibration, filtering and gesture recognition
        self._calibration_profile: HandCalibrationProfile = load_calibration()
        self._thumb_filter = FlexSensorFilter(alpha=0.35, window_size=3)
        self._index_filter = FlexSensorFilter(alpha=0.35, window_size=3)
        self._gesture_recognizer = HandGestureRecognizer()

        log.info(
            f"GloveReceiverBridge initialized (port='{self._port}', "
            f"baud={self._baud_rate}, enabled={self._enabled})"
        )

    def reload_calibration(self) -> None:
        """Reload calibration profile from disk."""
        self._calibration_profile = load_calibration()
        self._thumb_filter.reset()
        self._index_filter.reset()
        self._gesture_recognizer.reset()
        log.info("Hand calibration profile reloaded.")

    # ============================================================
    # LIFECYCLE
    # ============================================================

    async def start(self) -> bool:
        """Start the background receiver thread."""
        if not self._enabled:
            log.info("GloveReceiverBridge is disabled by configuration")
            return False

        if self._running:
            log.warning("GloveReceiverBridge already running")
            return True

        if not self._port:
            log.warning("No glove receiver port configured — receiver idle")
            return False

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="GloveReceiverThread",
            daemon=True
        )
        self._thread.start()
        log.info(f"GloveReceiverBridge started background worker on {self._port}")
        return True

    async def stop(self) -> None:
        """Stop background receiver and cleanly close connection."""
        self._running = False
        self._close_serial()

        if self._thread and self._thread.is_alive():
            # Wait for thread exit in non-blocking manner
            await asyncio.to_thread(self._thread.join, timeout=1.5)

        self._thread = None
        log.info("GloveReceiverBridge stopped")

    # ============================================================
    # PARSING LOGIC (PURE & DETERMINISTIC)
    # ============================================================

    @staticmethod
    def parse_line(line: str) -> Optional[tuple[int, int]]:
        """
        Safely parse incoming serial line into (thumb, index) integers.
        Supports both JSON and plaintext formats.
        Returns None if malformed or invalid.
        """
        if not line or not isinstance(line, str):
            return None

        line_str = line.strip()
        if not line_str:
            return None

        # 1. Attempt JSON parsing
        if line_str.startswith("{") and line_str.endswith("}"):
            try:
                payload = json.loads(line_str)
                if isinstance(payload, dict):
                    msg_type = payload.get("type")
                    if msg_type in ("HAND_DATA", None):  # Accept type='HAND_DATA' or direct key dicts
                        thumb_raw = payload.get("thumb", payload.get("flex_thumb"))
                        index_raw = payload.get("index", payload.get("flex_index"))

                        if thumb_raw is not None and index_raw is not None:
                            thumb_val = int(thumb_raw)
                            index_val = int(index_raw)
                            if MIN_ADC_VAL <= thumb_val <= MAX_ADC_VAL and MIN_ADC_VAL <= index_val <= MAX_ADC_VAL:
                                return thumb_val, index_val
            except (json.JSONDecodeError, ValueError, TypeError):
                pass  # Fall through to plaintext check

        # 2. Attempt Plaintext Regex parsing: "Thumb: 123   Index: 456"
        match = PLAINTEXT_PATTERN.search(line_str)
        if match:
            try:
                thumb_val = int(match.group(1))
                index_val = int(match.group(2))
                if MIN_ADC_VAL <= thumb_val <= MAX_ADC_VAL and MIN_ADC_VAL <= index_val <= MAX_ADC_VAL:
                    return thumb_val, index_val
            except (ValueError, IndexError):
                pass

        return None

    # ============================================================
    # STATE APPLICATION
    # ============================================================

    def _apply_telemetry(self, thumb: int, index: int) -> None:
        """Apply verified sensor values directly to robot_state."""
        # 1. Update raw ADC values
        robot_state.sensors.flex_thumb = thumb
        robot_state.sensors.flex_index = index

        # 2. Filter and calculate normalized bend percentages if calibrated
        filtered_thumb = self._thumb_filter.update(float(thumb))
        filtered_index = self._index_filter.update(float(index))

        if self._calibration_profile.thumb and self._calibration_profile.thumb.is_valid():
            robot_state.sensors.flex_thumb_bend_pct = self._calibration_profile.thumb.normalize(filtered_thumb)
        else:
            robot_state.sensors.flex_thumb_bend_pct = 0.0

        if self._calibration_profile.index and self._calibration_profile.index.is_valid():
            robot_state.sensors.flex_index_bend_pct = self._calibration_profile.index.normalize(filtered_index)
        else:
            robot_state.sensors.flex_index_bend_pct = 0.0

        # 3. Classify gesture and update robot_state.hand telemetry
        gesture_res = self._gesture_recognizer.process(
            robot_state.sensors.flex_thumb_bend_pct,
            robot_state.sensors.flex_index_bend_pct
        )
        robot_state.hand.gesture = gesture_res.gesture
        robot_state.hand.confidence = gesture_res.confidence
        robot_state.hand.thumb_bend_pct = gesture_res.thumb_bend_pct
        robot_state.hand.index_bend_pct = gesture_res.index_bend_pct
        robot_state.hand.is_stable = gesture_res.is_stable
        robot_state.hand.stable_count = gesture_res.stable_count
        robot_state.hand.last_updated = gesture_res.timestamp

        self._last_packet_time = datetime.now(timezone.utc)
        self._packets_received += 1

        if self._callback:
            loop = self._loop
            if loop is None or loop.is_closed():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

            if loop and not loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(
                        self._callback(thumb, index),
                        loop
                    )
                except Exception as e:
                    log.debug(f"Telemetry callback dispatch error: {e}")

    # ============================================================
    # WORKER THREAD & AUTO-RECONNECT
    # ============================================================

    def _worker_loop(self) -> None:
        """Background thread loop for serial reading and auto-reconnect."""
        import serial

        while self._running:
            try:
                log.info(f"Opening serial port {self._port} @ {self._baud_rate}...")
                self._serial_obj = serial.Serial(
                    port=self._port,
                    baudrate=self._baud_rate,
                    timeout=0.5,
                    rtscts=False,
                    dsrdtr=False,
                )
                self._connected = True
                log.info(f"Glove receiver connected on {self._port}")

                while self._running and self._connected:
                    try:
                        if not self._serial_obj or not self._serial_obj.is_open:
                            break

                        line_bytes = self._serial_obj.readline()
                        if not line_bytes:
                            continue

                        line = line_bytes.decode("utf-8", errors="ignore")
                        parsed = self.parse_line(line)
                        if parsed:
                            thumb, index = parsed
                            self._apply_telemetry(thumb, index)

                    except (serial.SerialException, OSError) as e:
                        log.warning(f"Glove receiver read error on {self._port}: {e}")
                        break
                    except Exception as e:
                        log.debug(f"Line processing error: {e}")

            except (serial.SerialException, OSError, Exception) as e:
                log.debug(f"Unable to open glove receiver on {self._port}: {e}")

            self._close_serial()

            if self._running:
                # Sleep before retrying
                time.sleep(self._reconnect_interval)

    def _close_serial(self) -> None:
        """Safely close pyserial port instance."""
        self._connected = False
        if self._serial_obj:
            try:
                if self._serial_obj.is_open:
                    self._serial_obj.close()
            except Exception:
                pass
            self._serial_obj = None

    # ============================================================
    # PUBLIC PROPERTIES & ACCESSORS
    # ============================================================

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def packets_received(self) -> int:
        return self._packets_received

    @property
    def last_packet_time(self) -> Optional[datetime]:
        return self._last_packet_time

    @property
    def port(self) -> str:
        return self._port

    def set_callback(self, callback: Callable[[int, int], Awaitable[None]]) -> None:
        """Register an optional async callback for each valid packet."""
        self._callback = callback
