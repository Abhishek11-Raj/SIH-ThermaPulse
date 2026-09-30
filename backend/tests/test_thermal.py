"""Tests for STEP 3: Thermal Stress and Exposure Memory Engine."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.core.enums import QualityFlag
from app.thermal.heat_index import calculate_heat_index, calculate_heat_index_from_input
from app.thermal.wet_bulb import calculate_wet_bulb, calculate_wet_bulb_from_input
from app.thermal.wbgt import calculate_wbgt_from_input, estimate_globe_temperature
from app.thermal.utci import calculate_utci_from_input, categorize_utci
from app.thermal.mrt import calculate_mrt, estimate_mrt_from_solar
from app.thermal.nighttime import (
    analyze_nighttime_heat,
    build_baseline_from_history,
    calculate_nighttime_temperatures,
    calculate_nighttime_stats,
)
from app.thermal.exposure_memory import (
    calculate_exposure_memory,
    calculate_daily_stress,
    run_exposure_memory_step,
)
from app.thermal.classification import (
    classify_combined,
    ClassificationThresholds,
    classify_heat_index,
    classify_wbgt,
    classify_utci,
    classify_occupational_heat,
)
from app.thermal.schemas import ThermalInput, ThermalIndices


class TestHeatIndex:
    """Tests for Heat Index calculation."""

    def test_heat_index_valid_range(self):
        """Test HI in valid range (>= 27°C, >= 40% RH)."""
        result = calculate_heat_index(35.0, 60.0)
        assert result.heat_index_c is not None
        assert result.heat_index_c > 35.0  # HI should be higher than temp
        assert result.method == "rothfusz"
        assert not result.extrapolated

    def test_heat_index_extrapolated_low_temp(self):
        """Test HI with temperature below validity threshold."""
        result = calculate_heat_index(20.0, 60.0)
        assert result.extrapolated
        assert result.validity_note is not None

    def test_heat_index_extrapolated_low_rh(self):
        """Test HI with RH below validity threshold."""
        result = calculate_heat_index(35.0, 30.0)
        assert result.extrapolated
        assert result.validity_note is not None

    def test_heat_index_missing_inputs(self):
        """Test HI with missing inputs."""
        result = calculate_heat_index_from_input(ThermalInput())
        assert result.heat_index_c is None
        assert result.quality == QualityFlag.MISSING

    def test_heat_index_high_humidity_adjustment(self):
        """Test HI with high humidity adjustment (RH > 85%, 80-87°F)."""
        # 85°F = 29.4°C, RH=90%
        result = calculate_heat_index(29.4, 90.0)
        assert result.heat_index_c is not None


class TestWetBulb:
    """Tests for Wet-Bulb Temperature calculation."""

    def test_wet_bulb_stull(self):
        """Test Stull method."""
        result = calculate_wet_bulb(30.0, 60.0, method="stull")
        assert result.wet_bulb_c is not None
        assert result.wet_bulb_c <= 30.0  # WB cannot exceed dry bulb
        assert result.method == "stull"

    def test_wet_bulb_davies_jones(self):
        """Test Davies-Jones method."""
        result = calculate_wet_bulb(30.0, 60.0, method="davies_jones")
        assert result.wet_bulb_c is not None
        assert result.wet_bulb_c <= 30.0

    def test_wet_bulb_iterative(self):
        """Test iterative method."""
        result = calculate_wet_bulb(30.0, 60.0, method="iterative")
        assert result.wet_bulb_c is not None
        assert result.wet_bulb_c <= 30.0

    def test_wet_bulb_missing_inputs(self):
        """Test with missing inputs."""
        result = calculate_wet_bulb_from_input(ThermalInput())
        assert result.wet_bulb_c is None
        assert result.quality == QualityFlag.MISSING

    def test_wet_bulb_clamped(self):
        """Test WB is clamped to dry bulb temp."""
        result = calculate_wet_bulb(40.0, 100.0)
        assert result.wet_bulb_c <= 40.0


class TestWBGT:
    """Tests for Wet Bulb Globe Temperature."""

    def test_wbgt_outdoor(self):
        """Test outdoor WBGT calculation."""
        wb_result = type('obj', (object,), {'wet_bulb_c': 25.0})()
        result = calculate_wbgt_from_input(
            ThermalInput(
                air_temperature_c=35.0,
                relative_humidity=60.0,
                wind_speed_ms=3.0,
                solar_radiation_wm2=800.0,
            ),
            wb_result,
            indoor=False,
        )
        assert result.wbgt_c is not None
        assert result.wbgt_c > 0

    def test_wbgt_indoor(self):
        """Test indoor WBGT calculation."""
        wb_result = type('obj', (object,), {'wet_bulb_c': 25.0})()
        result = calculate_wbgt_from_input(
            ThermalInput(
                air_temperature_c=35.0,
                relative_humidity=60.0,
            ),
            wb_result,
            indoor=True,
        )
        assert result.wbgt_indoor_c is not None

    def test_wbgt_missing_wet_bulb(self):
        """Test WBGT with missing wet-bulb."""
        wb_result = type('obj', (object,), {'wet_bulb_c': None})()
        result = calculate_wbgt_from_input(ThermalInput(air_temperature_c=35.0), wb_result)
        assert result.wbgt_c is None
        assert result.quality == QualityFlag.MISSING


class TestUTCI:
    """Tests for Universal Thermal Climate Index."""

    def test_utci_categorization(self):
        """Test UTCI category classification."""
        assert categorize_utci(50.0) == "extreme_heat_stress"
        assert categorize_utci(40.0) == "very_strong_heat_stress"
        assert categorize_utci(35.0) == "strong_heat_stress"
        assert categorize_utci(30.0) == "moderate_heat_stress"
        assert categorize_utci(20.0) == "no_thermal_stress"
        assert categorize_utci(5.0) == "slight_cold_stress"
        assert categorize_utci(-10.0) == "moderate_cold_stress"

    def test_utci_approximation(self):
        """Test UTCI approximation calculation."""
        mrt_result = type('obj', (object,), {'mrt_c': 40.0})()
        result = calculate_utci_from_input(
            ThermalInput(
                air_temperature_c=35.0,
                relative_humidity=60.0,
                wind_speed_ms=3.0,
                solar_radiation_wm2=800.0,
            ),
            mrt_result,
        )
        assert result.utci_c is not None
        assert result.thermal_stress_category is not None


class TestMRT:
    """Tests for Mean Radiant Temperature."""

    def test_mrt_solar_estimation(self):
        """Test MRT estimation from solar radiation."""
        result = calculate_mrt(
            ThermalInput(
                air_temperature_c=30.0,
                solar_radiation_wm2=800.0,
            ),
            method="solar_only",
        )
        assert result.mrt_c is not None
        assert result.mrt_c >= 30.0  # MRT should be >= air temp in sun

    def test_mrt_no_solar(self):
        """Test MRT with no solar radiation."""
        result = calculate_mrt(
            ThermalInput(
                air_temperature_c=30.0,
                solar_radiation_wm2=0.0,
            ),
            method="solar_only",
        )
        assert result.mrt_c is None or result.mrt_c == 30.0

    def test_mrt_missing_temp(self):
        """Test MRT with missing air temperature."""
        result = calculate_mrt(
            ThermalInput(solar_radiation_wm2=800.0),
            method="solar_only",
        )
        assert result.mrt_c is None
        assert result.quality == QualityFlag.MISSING


class TestNighttimeHeat:
    """Tests for Nighttime Heat Analysis."""

    def test_calculate_nighttime_temperatures(self):
        """Test extraction of nighttime temperatures."""
        hourly_temps = [30.0] * 24
        hourly_times = [datetime(2026, 9, 28, h, tzinfo=timezone.utc) for h in range(24)]

        night_temps, night_times = calculate_nighttime_temperatures(hourly_temps, hourly_times)

        # Should get 12 hours: 20-23 and 0-7
        assert len(night_temps) == 12

    def test_calculate_nighttime_stats(self):
        """Test nighttime statistics calculation."""
        night_temps = [28.0, 27.5, 27.0, 26.5, 26.0, 25.5, 25.0, 24.5, 24.0, 24.0, 24.0, 24.0]
        baseline = [24.0] * 30  # Baseline nights at 24°C

        stats = calculate_nighttime_stats(night_temps, baseline, percentile=90.0)

        assert stats["min_temp_c"] == 24.0
        assert stats["max_temp_c"] == 28.0
        assert stats["anomaly_c"] is not None
        assert stats["threshold_c"] is not None

    def test_analyze_nighttime_heat(self):
        """Test complete nighttime analysis."""
        hourly_temps = [30.0] * 12 + [25.0] * 12  # Day: 30, Night: 25
        hourly_times = [datetime(2026, 9, 28, h, tzinfo=timezone.utc) for h in range(24)]
        baseline = [24.0] * 30

        result = analyze_nighttime_heat(
            hourly_temps, hourly_times,
            baseline_night_temps=baseline,
            config={"nighttime_percentile": 90.0, "recovery_threshold_c": 25.0},
        )

        assert result.mean_temperature_c is not None
        assert result.hot_night in (True, False)
        assert result.recovery_status in (
            "full_recovery", "partial_recovery", "impaired_recovery", "minimal_recovery", "no_data"
        )

    def test_build_baseline_from_history(self):
        """Test building baseline from historical data."""
        # 5 days of historical data
        historical_temps = [
            [24.0] * 12 + [30.0] * 12,  # Night 24°C
            [25.0] * 12 + [31.0] * 12,
            [23.0] * 12 + [29.0] * 12,
            [24.0] * 12 + [30.0] * 12,
            [26.0] * 12 + [32.0] * 12,
        ]
        historical_times = [
            [datetime(2026, 9, d, h, tzinfo=timezone.utc) for h in range(24)]
            for d in range(23, 28)
        ]

        baseline = build_baseline_from_history(historical_temps, historical_times)
        assert len(baseline) == 5
        assert all(isinstance(t, float) for t in baseline)


class TestExposureMemory:
    """Tests for Heat Exposure Memory."""

    def test_calculate_daily_stress(self):
        """Test daily stress calculation from indices."""
        indices = ThermalIndices(
            heat_index_c=38.0,
            wbgt_c=30.0,
            utci_c=35.0,
            wet_bulb_c=28.0,
        )
        stress = calculate_daily_stress(indices)
        assert 0.0 <= stress <= 1.0

    def test_calculate_daily_stress_nighttime(self):
        """Test daily stress with nighttime amplification."""
        indices = ThermalIndices(
            heat_index_c=38.0,
            wbgt_c=30.0,
            utci_c=35.0,
            wet_bulb_c=28.0,
        )
        stress_normal = calculate_daily_stress(indices)
        stress_hot_night = calculate_daily_stress(indices, nighttime_hot=True)
        stress_consecutive = calculate_daily_stress(indices, consecutive_hot_nights=3)

        assert stress_hot_night >= stress_normal
        assert stress_consecutive >= stress_hot_night

    def test_calculate_exposure_memory(self):
        """Test exposure memory state equation."""
        result = calculate_exposure_memory(
            previous_memory=2.0,
            current_stress=0.8,
            recovery=0.5,
            decay_factor=0.95,
        )
        # E_t = 0.95 * 2.0 + 0.8 - 0.5 = 1.9 + 0.3 = 2.2
        expected = 0.95 * 2.0 + 0.8 - 0.5
        assert abs(result.exposure_memory - expected) < 0.001
        assert result.decay_factor == 0.95

    def test_exposure_memory_no_previous(self):
        """Test exposure memory with no previous state."""
        result = calculate_exposure_memory(
            previous_memory=None,
            current_stress=0.5,
            recovery=0.3,
        )
        # Should initialize to 0 and compute: 0 + 0.5 - 0.3 = 0.2
        assert result.exposure_memory == 0.2
        assert result.extrapolated

    def test_exposure_memory_capped(self):
        """Test exposure memory is capped at maximum."""
        result = calculate_exposure_memory(
            previous_memory=10.0,
            current_stress=1.0,
            recovery=0.0,
            decay_factor=1.0,
        )
        # Should cap at 10.0
        assert result.exposure_memory <= 10.0

    def test_run_exposure_memory_step(self):
        """Test one step of exposure memory model."""
        indices = ThermalIndices(
            heat_index_c=38.0,
            wbgt_c=30.0,
            utci_c=35.0,
            wet_bulb_c=28.0,
        )
        nighttime_result = type('obj', (object,), {
            'recovery_status': 'full_recovery',
            'consecutive_hot_nights': 0,
            'recovery_deficit': 0.0,
        })()

        result = run_exposure_memory_step(
            indices, nighttime_result, previous_memory=1.0,
            config={"memory_decay_factor": 0.95},
        )

        assert result.exposure_memory is not None
        assert result.current_stress_contribution > 0
        assert result.recovery_contribution > 0


class TestClassification:
    """Tests for Thermal Stress Classification."""

    def test_classify_heat_index(self):
        """Test HI classification."""
        thresholds = ClassificationThresholds()
        assert classify_heat_index(20.0, thresholds) == "NORMAL"
        assert classify_heat_index(30.0, thresholds) == "CAUTION"
        assert classify_heat_index(35.0, thresholds) == "HIGH"
        assert classify_heat_index(45.0, thresholds) == "VERY_HIGH"
        assert classify_heat_index(55.0, thresholds) == "EXTREME"

    def test_classify_wbgt(self):
        """Test WBGT classification."""
        thresholds = ClassificationThresholds()
        assert classify_wbgt(20.0, thresholds) == "NORMAL"
        assert classify_wbgt(26.0, thresholds) == "CAUTION"
        assert classify_wbgt(29.0, thresholds) == "HIGH"
        assert classify_wbgt(31.0, thresholds) == "VERY_HIGH"
        assert classify_wbgt(33.0, thresholds) == "EXTREME"

    def test_classify_utci(self):
        """Test UTCI classification."""
        thresholds = ClassificationThresholds()
        assert classify_utci(20.0, thresholds) == "NORMAL"
        assert classify_utci(30.0, thresholds) == "CAUTION"
        assert classify_utci(35.0, thresholds) == "HIGH"
        assert classify_utci(40.0, thresholds) == "VERY_HIGH"
        assert classify_utci(50.0, thresholds) == "EXTREME"

    def test_classify_combined(self):
        """Test multi-index classification."""
        indices = ThermalIndices(
            heat_index_c=38.0,
            wbgt_c=30.0,
            utci_c=35.0,
            wet_bulb_c=28.0,
        )
        classification = classify_combined(indices, None)

        # Should pick the most severe
        assert classification.thermal_stress_category in ("HIGH", "VERY_HIGH", "EXTREME")

    def test_classify_occupational_heat(self):
        """Test occupational heat classification."""
        thresholds = ClassificationThresholds()
        occ = classify_occupational_heat(28.0, 32.0, thresholds)
        assert occ in ("CAUTION", "HIGH", "VERY_HIGH", "EXTREME")


class TestThermalInputValidation:
    """Tests for thermal input validation."""

    def test_thermal_input_valid(self):
        """Test valid thermal input."""
        inp = ThermalInput(
            air_temperature_c=35.0,
            relative_humidity=60.0,
            wind_speed_ms=3.0,
            solar_radiation_wm2=800.0,
        )
        assert inp.air_temperature_c == 35.0

    def test_thermal_input_invalid_humidity(self):
        """Test invalid humidity."""
        with pytest.raises(ValueError):
            ThermalInput(relative_humidity=150.0)

    def test_thermal_input_invalid_wind_direction(self):
        """Test invalid wind direction."""
        with pytest.raises(ValueError):
            ThermalInput(wind_direction_deg=400.0)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_extreme_temperature(self):
        """Test with extreme temperature (50°C)."""
        result = calculate_heat_index(50.0, 20.0)
        assert result.heat_index_c is not None

    def test_very_high_humidity(self):
        """Test with very high humidity (95%)."""
        result = calculate_heat_index(35.0, 95.0)
        assert result.heat_index_c is not None

    def test_zero_wind(self):
        """Test with zero wind speed."""
        result = calculate_wet_bulb(30.0, 60.0, pressure_hpa=1013.25)
        assert result.wet_bulb_c is not None

    def test_missing_radiation_wbgt(self):
        """Test WBGT with missing radiation."""
        wb_result = type('obj', (object,), {'wet_bulb_c': 25.0})()
        result = calculate_wbgt_from_input(
            ThermalInput(air_temperature_c=35.0, relative_humidity=60.0),
            wb_result,
        )
        # Should estimate globe = air temp
        assert result.wbgt_c is not None

    def test_missing_humidity(self):
        """Test with missing humidity."""
        inp = ThermalInput(air_temperature_c=35.0, wind_speed_ms=3.0)
        result = calculate_heat_index_from_input(inp)
        assert result.heat_index_c is None
        assert result.quality == QualityFlag.MISSING

    def test_forecast_vs_observation_distinction(self):
        """Test that forecast and observation are distinguishable."""
        # This is tested by the source_type field in the schema
        from app.thermal.schemas import ThermalStressResult
        result_obs = ThermalStressResult(
            calculation_id="test",
            location_id="TEST",
            timestamp=datetime.now(timezone.utc),
            source_type="OBSERVATION",
            inputs=ThermalInput(),
            indices=ThermalIndices(),
        )
        result_fc = ThermalStressResult(
            calculation_id="test",
            location_id="TEST",
            timestamp=datetime.now(timezone.utc),
            source_type="FORECAST",
            inputs=ThermalInput(),
            indices=ThermalIndices(),
        )
        assert result_obs.source_type == "OBSERVATION"
        assert result_fc.source_type == "FORECAST"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])