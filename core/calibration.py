"""
CYNEXIS — Hand Sensor Calibration & Normalization Engine
==========================================================
Provides data models, low-latency filtering, and bidirectional normalization
for flex sensor ADC telemetry.

Supports:
- Direction-agnostic calibration (handles both ADC increasing or decreasing with bend)
- Low-latency 3-sample median + Exponential Moving Average (EMA) filtering
- Safe clamping to 0.0% – 100.0%
- JSON persistence (Config/calibration_hand.json)
- Zero-actuator safety: Pure mathematical normalization, no motor or servo commands
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import statistics

# Default calibration file path
DEFAULT_CALIBRATION_PATH = Path(__file__).resolve().parent.parent / "Config" / "calibration_hand.json"


class CalibrationStats(BaseModel):
    """Statistical summary of calibration sampling."""
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    samples: int = 0


class FingerCalibration(BaseModel):
    """Calibration profile for an individual finger."""
    finger: str  # "thumb" | "index" | etc.
    straight_raw: float  # Raw ADC value when finger is straight (0% bend)
    bent_raw: float      # Raw ADC value when finger is fully bent (100% bend)
    direction: str = "INCREASING"  # "INCREASING" (bent > straight) or "DECREASING" (bent < straight)
    min_delta: float = 20.0  # Minimum raw difference required for valid calibration
    straight_stats: Optional[CalibrationStats] = None
    bent_stats: Optional[CalibrationStats] = None
    calibrated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_valid(self) -> bool:
        """Check if calibration range has sufficient separation."""
        return abs(self.bent_raw - self.straight_raw) >= self.min_delta

    def normalize(self, raw_value: float) -> float:
        """
        Normalize raw ADC reading to 0.0% - 100.0% bend percentage.
        Clamped safely between 0.0 and 100.0.
        """
        if not self.is_valid():
            return 0.0

        if self.direction.upper() == "INCREASING":
            # Higher raw ADC = more bending
            pct = ((raw_value - self.straight_raw) / (self.bent_raw - self.straight_raw)) * 100.0
        else:
            # Lower raw ADC = more bending
            pct = ((self.straight_raw - raw_value) / (self.straight_raw - self.bent_raw)) * 100.0

        return max(0.0, min(100.0, round(pct, 1)))


class HandCalibrationProfile(BaseModel):
    """Complete hand calibration profile containing all finger models."""
    version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    thumb: Optional[FingerCalibration] = None
    index: Optional[FingerCalibration] = None


class FlexSensorFilter:
    """
    Low-latency filter combining 3-sample median filtering with an
    Exponential Moving Average (alpha = 0.35) for smooth, bounce-free readings.
    """

    def __init__(self, alpha: float = 0.35, window_size: int = 3):
        self.alpha = alpha
        self.window_size = window_size
        self._history: list[float] = []
        self._ema_value: Optional[float] = None

    def update(self, sample: float) -> float:
        """Push a new sample and return the filtered value."""
        self._history.append(sample)
        if len(self._history) > self.window_size:
            self._history.pop(0)

        # 1. Median filter over recent window (eliminates single-sample spikes)
        median_val = statistics.median(self._history)

        # 2. Exponential moving average (smooths sensor noise)
        if self._ema_value is None:
            self._ema_value = median_val
        else:
            self._ema_value = (self.alpha * median_val) + ((1.0 - self.alpha) * self._ema_value)

        return self._ema_value

    def reset(self) -> None:
        """Reset filter history."""
        self._history.clear()
        self._ema_value = None


def compute_calibration_stats(samples: list[float]) -> CalibrationStats:
    """Compute statistical distribution over collected samples."""
    if not samples:
        return CalibrationStats()

    n = len(samples)
    min_v = float(min(samples))
    max_v = float(max(samples))
    mean_v = float(statistics.mean(samples))
    med_v = float(statistics.median(samples))
    std_v = float(statistics.stdev(samples)) if n > 1 else 0.0

    return CalibrationStats(
        min=round(min_v, 1),
        max=round(max_v, 1),
        mean=round(mean_v, 1),
        median=round(med_v, 1),
        std_dev=round(std_v, 2),
        samples=n,
    )


def create_finger_calibration(
    finger: str,
    straight_samples: list[float],
    bent_samples: list[float],
) -> FingerCalibration:
    """
    Analyze collected samples to automatically determine direction,
    median operating points, and statistical quality.
    """
    straight_stats = compute_calibration_stats(straight_samples)
    bent_stats = compute_calibration_stats(bent_samples)

    # Use median for robustness against sensor noise
    straight_raw = straight_stats.median
    bent_raw = bent_stats.median

    # Determine direction automatically
    direction = "INCREASING" if bent_raw >= straight_raw else "DECREASING"

    return FingerCalibration(
        finger=finger,
        straight_raw=straight_raw,
        bent_raw=bent_raw,
        direction=direction,
        straight_stats=straight_stats,
        bent_stats=bent_stats,
        calibrated_at=datetime.now(timezone.utc).isoformat(),
    )


def save_calibration(profile: HandCalibrationProfile, path: Optional[Path] = None) -> bool:
    """Save hand calibration profile to JSON file."""
    target_path = path or DEFAULT_CALIBRATION_PATH
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2)
        return True
    except Exception:
        return False


def load_calibration(path: Optional[Path] = None) -> HandCalibrationProfile:
    """
    Load hand calibration profile from JSON file.
    Returns empty profile if file is missing or corrupted.
    """
    target_path = path or DEFAULT_CALIBRATION_PATH
    if not target_path.exists():
        return HandCalibrationProfile()

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return HandCalibrationProfile.model_validate(data)
    except Exception:
        return HandCalibrationProfile()
