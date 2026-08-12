"""
CYNEXIS — Unit Tests for Hand Calibration & Normalization Engine
=================================================================
Tests for:
- Increasing direction normalization (bent > straight)
- Decreasing direction normalization (bent < straight)
- Normalization clamping (0% - 100%)
- Invalid/insufficient calibration ranges
- Missing calibration file handling
- FlexSensorFilter median spike suppression & EMA smoothing
- Statistical analysis computation
- JSON file persistence and recovery
- Independent thumb and index profiles
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import tempfile
from core.calibration import (
    FingerCalibration,
    HandCalibrationProfile,
    CalibrationStats,
    FlexSensorFilter,
    compute_calibration_stats,
    create_finger_calibration,
    save_calibration,
    load_calibration,
)


# ============================================================
# 1. NORMALIZATION & DIRECTION TESTS
# ============================================================

class TestNormalization:
    """Tests normalization calculations across both directions and boundaries."""

    def test_increasing_direction(self):
        # Straight = 100, Bent = 700 (Increasing)
        cal = FingerCalibration(
            finger="index",
            straight_raw=100.0,
            bent_raw=700.0,
            direction="INCREASING"
        )
        assert cal.is_valid()
        assert cal.normalize(100.0) == 0.0     # Straight -> 0%
        assert cal.normalize(400.0) == 50.0    # Halfway -> 50%
        assert cal.normalize(700.0) == 100.0   # Fully bent -> 100%

    def test_decreasing_direction(self):
        # Straight = 700, Bent = 100 (Decreasing)
        cal = FingerCalibration(
            finger="thumb",
            straight_raw=700.0,
            bent_raw=100.0,
            direction="DECREASING"
        )
        assert cal.is_valid()
        assert cal.normalize(700.0) == 0.0     # Straight -> 0%
        assert cal.normalize(400.0) == 50.0    # Halfway -> 50%
        assert cal.normalize(100.0) == 100.0   # Fully bent -> 100%

    def test_clamping_bounds(self):
        cal_inc = FingerCalibration(
            finger="index",
            straight_raw=200.0,
            bent_raw=600.0,
            direction="INCREASING"
        )
        # Below straight
        assert cal_inc.normalize(50.0) == 0.0
        # Above bent
        assert cal_inc.normalize(900.0) == 100.0

        cal_dec = FingerCalibration(
            finger="thumb",
            straight_raw=600.0,
            bent_raw=200.0,
            direction="DECREASING"
        )
        # Higher than straight
        assert cal_dec.normalize(800.0) == 0.0
        # Lower than bent
        assert cal_dec.normalize(50.0) == 100.0

    def test_invalid_calibration_range(self):
        # Zero delta
        cal_zero = FingerCalibration(
            finger="thumb",
            straight_raw=300.0,
            bent_raw=300.0,
            direction="INCREASING"
        )
        assert not cal_zero.is_valid()
        assert cal_zero.normalize(300.0) == 0.0

        # Delta below min_delta threshold (e.g. 5 units)
        cal_narrow = FingerCalibration(
            finger="thumb",
            straight_raw=300.0,
            bent_raw=305.0,
            min_delta=20.0
        )
        assert not cal_narrow.is_valid()
        assert cal_narrow.normalize(302.0) == 0.0


# ============================================================
# 2. STATISTICAL ANALYSIS & FACTORY TESTS
# ============================================================

class TestCalibrationStats:
    """Tests sample statistics calculation and direction discovery."""

    def test_compute_stats(self):
        samples = [100.0, 105.0, 95.0, 100.0, 100.0]
        stats = compute_calibration_stats(samples)
        assert stats.min == 95.0
        assert stats.max == 105.0
        assert stats.mean == 100.0
        assert stats.median == 100.0
        assert stats.samples == 5
        assert stats.std_dev > 0.0

    def test_create_finger_calibration_increasing(self):
        straight = [115.0, 120.0, 125.0] * 10  # Median 120
        bent = [435.0, 440.0, 445.0] * 10      # Median 440

        cal = create_finger_calibration("thumb", straight, bent)
        assert cal.finger == "thumb"
        assert cal.straight_raw == 120.0
        assert cal.bent_raw == 440.0
        assert cal.direction == "INCREASING"
        assert cal.is_valid()

    def test_create_finger_calibration_decreasing(self):
        straight = [600.0, 610.0, 590.0] * 10  # Median 600
        bent = [190.0, 200.0, 210.0] * 10      # Median 200

        cal = create_finger_calibration("index", straight, bent)
        assert cal.finger == "index"
        assert cal.straight_raw == 600.0
        assert cal.bent_raw == 200.0
        assert cal.direction == "DECREASING"
        assert cal.is_valid()


# ============================================================
# 3. FILTERING TESTS
# ============================================================

class TestFlexSensorFilter:
    """Tests noise filtering and spike rejection."""

    def test_filter_rejects_single_sample_spike(self):
        filt = FlexSensorFilter(alpha=0.5, window_size=3)
        # Feed steady 200
        filt.update(200.0)
        filt.update(200.0)
        v = filt.update(200.0)
        assert v == 200.0

        # Inject single spike: 900
        # Window is [200, 200, 900] -> median is 200!
        v_spiked = filt.update(900.0)
        assert v_spiked == 200.0

    def test_filter_smooth_transition(self):
        filt = FlexSensorFilter(alpha=0.3, window_size=3)
        v1 = filt.update(100.0)
        filt.update(100.0)
        filt.update(100.0)

        # Step jump to 200
        filt.update(200.0)
        filt.update(200.0)
        v_after = filt.update(200.0)
        # EMA smoothed step
        assert 100.0 < v_after <= 200.0


# ============================================================
# 4. PERSISTENCE & INDEPENDENCE TESTS
# ============================================================

class TestPersistence:
    """Tests saving and loading calibration JSON profiles."""

    def test_save_and_load_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_cal.json"

            thumb_cal = FingerCalibration(
                finger="thumb",
                straight_raw=120.0,
                bent_raw=440.0,
                direction="INCREASING"
            )
            index_cal = FingerCalibration(
                finger="index",
                straight_raw=600.0,
                bent_raw=150.0,
                direction="DECREASING"
            )

            profile = HandCalibrationProfile(
                thumb=thumb_cal,
                index=index_cal
            )

            assert save_calibration(profile, file_path)
            assert file_path.exists()

            loaded = load_calibration(file_path)
            assert loaded.thumb is not None
            assert loaded.thumb.straight_raw == 120.0
            assert loaded.thumb.direction == "INCREASING"

            assert loaded.index is not None
            assert loaded.index.bent_raw == 150.0
            assert loaded.index.direction == "DECREASING"

    def test_load_non_existent_file_returns_empty_profile(self):
        missing_path = Path("non_existent_calibration_file_xyz.json")
        loaded = load_calibration(missing_path)
        assert loaded.thumb is None
        assert loaded.index is None
