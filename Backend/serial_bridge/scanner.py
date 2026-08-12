"""
CYNEXIS — Serial Port Scanner & ESP32 Auto-Discovery
Scans system COM ports and identifies connected ESP32 microcontrollers.
"""

from typing import Optional
from dataclasses import dataclass
from core.logger import get_logger

log = get_logger("scanner")

# Known USB-to-UART bridge VIDs / PIDs and driver descriptions
KNOWN_ESP32_IDENTIFIERS = [
    # Silicon Labs CP210x
    {"vid": 0x10C4, "pid": 0xEA60, "name": "Silicon Labs CP210x"},
    # WCH CH340 / CH341
    {"vid": 0x1A86, "pid": 0x7523, "name": "WCH CH340 USB-Serial"},
    {"vid": 0x1A86, "pid": 0x55D4, "name": "WCH CH343 USB-Serial"},
    # FTDI FT232R / FT231X
    {"vid": 0x0403, "pid": 0x6001, "name": "FTDI FT232R USB-Serial"},
    {"vid": 0x0403, "pid": 0x6015, "name": "FTDI FT231X USB-Serial"},
    # Espressif Native USB-JTAG/Serial (ESP32-S3, ESP32-C3, etc.)
    {"vid": 0x303A, "pid": 0x1001, "name": "Espressif USB JTAG/serial debug unit"},
    {"vid": 0x303A, "pid": 0x0002, "name": "Espressif ESP32-S2 USB CDC"},
    {"vid": 0x303A, "pid": 0x1002, "name": "Espressif ESP32-S3 USB CDC"},
]

@dataclass
class DiscoveredPort:
    device: str
    description: str
    hwid: str
    vid: Optional[int] = None
    pid: Optional[int] = None
    is_esp32_candidate: bool = False
    matched_chip: Optional[str] = None


def scan_com_ports() -> list[DiscoveredPort]:
    """Scan all system serial ports and identify likely ESP32 devices."""
    discovered = []
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
    except ImportError:
        log.error("pyserial is required for COM port scanning. (pip install pyserial)")
        return []

    for p in ports:
        is_candidate = False
        matched_chip = None

        # Check VID/PID
        for ident in KNOWN_ESP32_IDENTIFIERS:
            if p.vid == ident["vid"] and (ident.get("pid") is None or p.pid == ident["pid"]):
                is_candidate = True
                matched_chip = ident["name"]
                break

        # Check description text if VID/PID not populated
        if not is_candidate and p.description:
            desc_lower = p.description.lower()
            if any(k in desc_lower for k in ["cp210", "ch340", "ch341", "ftdi", "esp32", "usb serial", "uart"]):
                is_candidate = True
                matched_chip = "Generic USB-to-UART Bridge"

        discovered.append(
            DiscoveredPort(
                device=p.device,
                description=p.description or "Unknown",
                hwid=p.hwid or "",
                vid=p.vid,
                pid=p.pid,
                is_esp32_candidate=is_candidate,
                matched_chip=matched_chip,
            )
        )

    return discovered


def auto_detect_esp32_port() -> Optional[str]:
    """Return the device path of the most likely ESP32 port, or None if not found."""
    ports = scan_com_ports()
    candidates = [p for p in ports if p.is_esp32_candidate]
    if candidates:
        log.info(f"Auto-detected ESP32 candidate: {candidates[0].device} ({candidates[0].matched_chip})")
        return candidates[0].device
    return None
