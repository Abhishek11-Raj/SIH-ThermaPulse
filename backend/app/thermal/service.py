"""Thermal Stress Calculation Service — STEP 3.

Main orchestration service that combines all thermal indices,
nighttime analysis, exposure memory, persistence, and classification
into a unified thermal stress result.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from ..core.enums import QualityFlag
from ..models.thermal import (
    ThermalStressResult as ThermalStressResultModel,
    ThermalDailySummary as ThermalDailySummaryModel,
    NighttimeHeatMetric as NighttimeHeatMetricModel,
    ExposureMemoryState as ExposureMemoryStateModel,
    ThermalCalculationRun as ThermalCalculationRunModel,
)
from ..schemas.weather import WeatherObservation
from ..schemas.forecast import WeatherForecast
from ..schemas.air_quality import AirQualityObservation
from ..utils.time import utcnow
from .schemas import (
    ThermalStressResult,
    ThermalInput,
    ThermalCalculationConfig,
    ThermalIndices,
    NighttimeMetrics,
    ExposureMetrics,
    ThermalClassification,
    ThermalQualityUncertainty,
    ThermalProvenance,
    ThermalDailySummary,
    NighttimeHeatMetric,
    ExposureMemoryState,
    ThermalCalculationRun,
)
from .heat_index import calculate_heat_index_from_input, HeatIndexResult
from .wet_bulb import calculate_wet_bulb_from_input, WetBulbResult
from .wbgt import calculate_wbgt_from_input, WBGTResult
from .utci import calculate_utci_from_input, UTCIResult
from .mrt import calculate_mrt, MRTResult
from .nighttime import (
    analyze_nighttime_heat,
    build_baseline_from_history,
    NighttimeResult,
)
from .exposure_memory import (
    run_exposure_memory_step,
    calculate_cumulative_exposure,
    ExposureMemoryResult,
)
from .persistence import calculate_persistence_metrics, PersistenceResult
from .classification import (
    classify_combined,
    get_classification_explanation,
    ClassificationThresholds,
)
from .uncertainty import assess_thermal_input_quality, ThermalQualityUncertainty


class ThermalCalculationService:
    """Main service for thermal stress calculations."""

    def __init__(self, db: Session, config: Optional[ThermalCalculationConfig] = None):
        self.db = db
        self.config = config or ThermalCalculationConfig()

    def _to_thermal_input(
        self,
        obs: Union[WeatherObservation, WeatherForecast, AirQualityObservation],
        source_type: str,
    ) -> Tuple[ThermalInput, Dict[str, QualityFlag]]:
        """Convert canonical observation/forecast to ThermalInput."""
        input_data = ThermalInput(
            air_temperature_c=obs.temperature,
            relative_humidity=obs.relative_humidity,
            wind_speed_ms=obs.wind_speed,
            wind_direction_deg=getattr(obs, 'wind_direction', None),
            pressure_hpa=obs.pressure,
            solar_radiation_wm2=obs.solar_radiation,
            cloud_cover_pct=obs.cloud_cover,
        )

        # Extract quality info
        quality_map = {}
        if hasattr(obs, 'quality_assessment') and obs.quality_assessment:
            for var in obs.quality_assessment.missing_variables or []:
                if var is not None:
                    quality_map[var] = QualityFlag.MISSING
            for issue in obs.quality_assessment.issues or []:
                if issue.variable and issue.variable not in quality_map:
                    quality_map[issue.variable] = QualityFlag.SUSPECT

        return input_data, quality_map

    def _get_baseline_temperatures(
        self,
        location_id: str,
        timestamp: datetime,
        days: int = 30
    ) -> List[float]:
        """Get historical baseline nighttime temperatures for a location."""
        # Query historical thermal daily summaries
        from ..models.thermal import ThermalDailySummary as DailyModel

        start_date = timestamp - timedelta(days=days)
        summaries = self.db.query(DailyModel).filter(
            DailyModel.location_id == location_id,
            DailyModel.date >= start_date,
            DailyModel.date < timestamp,
            DailyModel.nighttime_mean_temperature_c.isnot(None),
        ).all()

        return [s.nighttime_mean_temperature_c for s in summaries if s.nighttime_mean_temperature_c is not None]

    def _get_previous_exposure_memory(
        self,
        location_id: str,
        timestamp: datetime
    ) -> Optional[float]:
        """Get the most recent exposure memory state for a location."""
        from ..models.thermal import ExposureMemoryState as MemoryModel

        state = self.db.query(MemoryModel).filter(
            MemoryModel.location_id == location_id,
            MemoryModel.timestamp < timestamp,
        ).order_by(MemoryModel.timestamp.desc()).first()

        return state.exposure_memory if state else None

    def _get_daily_history(
        self,
        location_id: str,
        timestamp: datetime,
        days: int = 7
    ) -> Tuple[List[float], List[Optional[float]], List[datetime]]:
        """Get recent daily temperature and heat index history."""
        from ..models.thermal import ThermalDailySummary as DailyModel

        start_date = timestamp - timedelta(days=days)
        summaries = self.db.query(DailyModel).filter(
            DailyModel.location_id == location_id,
            DailyModel.date >= start_date,
            DailyModel.date <= timestamp,
        ).order_by(DailyModel.date).all()

        temps = []
        his = []
        dates = []

        for s in summaries:
            dates.append(s.date)
            temps.append(s.max_temperature_c)
            his.append(s.max_heat_index_c)

        return temps, his, dates

    def calculate_single(
        self,
        obs: Union[WeatherObservation, WeatherForecast, AirQualityObservation],
        source_type: str,
        location_id: str,
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> ThermalStressResult:
        """
        Calculate thermal stress for a single observation/forecast.

        Args:
            obs: Canonical weather observation or forecast
            source_type: "OBSERVATION", "FORECAST", or "ESTIMATED"
            location_id: Location identifier
            latitude: Latitude
            longitude: Longitude

        Returns:
            ThermalStressResult with all computed metrics
        """
        calculation_id = f"therm_{uuid4().hex[:12]}"
        timestamp = obs.observed_at if hasattr(obs, 'observed_at') else obs.valid_from

        # Convert to thermal input
        thermal_input, quality_map = self._to_thermal_input(obs, source_type)

        # --- 1. Calculate thermal indices ---

        # Heat Index
        hi_result: HeatIndexResult = calculate_heat_index_from_input(
            thermal_input, quality_map.get("air_temperature_c")
        )

        # Wet-bulb
        wb_result: WetBulbResult = calculate_wet_bulb_from_input(
            thermal_input, quality_map.get("air_temperature_c"),
            method=self.config.wet_bulb_method
        )

        # MRT
        mrt_result: MRTResult = calculate_mrt(
            thermal_input,
            method=self.config.mrt_method,
        )

        # WBGT
        wbgt_result: WBGTResult = calculate_wbgt_from_input(
            thermal_input, wb_result,
            indoor=self.config.wbgt_indoor,
            wbgt_method=self.config.wbgt_method,
        )

        # UTCI
        utci_result: UTCIResult = calculate_utci_from_input(
            thermal_input, mrt_result, quality_map.get("air_temperature_c")
        )

        # Assemble indices
        indices = ThermalIndices(
            heat_index_c=hi_result.heat_index_c,
            heat_index_f=hi_result.heat_index_f,
            wet_bulb_c=wb_result.wet_bulb_c,
            wbgt_c=wbgt_result.wbgt_c,
            wbgt_indoor_c=wbgt_result.wbgt_indoor_c,
            utci_c=utci_result.utci_c,
            mrt_c=mrt_result.mrt_c,
            heat_index_method=hi_result.method,
            wet_bulb_method=wb_result.method,
            wbgt_method=wbgt_result.method,
            wbgt_estimated_components=wbgt_result.estimated_components,
            utci_method=utci_result.method,
            mrt_method=mrt_result.method,
        )

        # --- 2. Nighttime analysis ---
        # Build hourly temperature series for nighttime analysis
        # For single observation, we need historical context
        # This is simplified - in practice would use recent hourly data
        nighttime_result = None
        nighttime_quality = quality_map.get("air_temperature_c", QualityFlag.VALID)

        if source_type == "OBSERVATION":
            # Try to get recent hourly data for nighttime analysis
            # For now, create a simplified result
            pass

        # --- 3. Exposure memory ---
        previous_memory = self._get_previous_exposure_memory(location_id, timestamp)

        # Build nighttime result for exposure memory (simplified)
        nighttime_for_memory = None

        memory_result: ExposureMemoryResult = run_exposure_memory_step(
            indices, nighttime_for_memory, previous_memory,
            config={
                "memory_decay_factor": self.config.memory_decay_factor,
                "stress_weights": self.config.stress_weights if hasattr(self.config, 'stress_weights') else None,
            },
            quality=quality_map.get("air_temperature_c"),
        )

        # --- 4. Cumulative exposure ---
        daily_temps, daily_his, daily_dates = self._get_daily_history(location_id, timestamp)
        cumulative = calculate_cumulative_exposure(daily_temps, windows_hours=self.config.exposure_windows_hours)

        # --- 5. Persistence ---
        baseline_temps = self._get_baseline_temperatures(location_id, timestamp)
        if baseline_temps:
            baseline_90 = sorted(baseline_temps)[int(len(baseline_temps) * 0.9)]
            baseline_975 = sorted(baseline_temps)[int(len(baseline_temps) * 0.975)]
        else:
            baseline_90 = 35.0
            baseline_975 = 40.0

        persistence = calculate_persistence_metrics(
            daily_temps, daily_his, daily_dates, baseline_90, baseline_975
        )

        # --- 6. Classification ---
        classification = classify_combined(indices, None)

        # --- 7. Quality & Uncertainty ---
        quality = assess_thermal_input_quality(thermal_input, {
            "air_temperature_c": quality_map.get("air_temperature_c") or QualityFlag.VALID,
            "relative_humidity": quality_map.get("relative_humidity") or QualityFlag.VALID,
            "wind_speed_ms": quality_map.get("wind_speed_ms") or QualityFlag.VALID,
            "solar_radiation_wm2": quality_map.get("solar_radiation_wm2") or QualityFlag.VALID,
        })

        # --- 8. Provenance ---
        provenance = ThermalProvenance(
            method_versions={
                "heat_index": hi_result.method,
                "wet_bulb": wb_result.method,
                "wbgt": wbgt_result.method,
                "utci": utci_result.method,
                "mrt": mrt_result.method,
                "nighttime": "nighttime_analysis_v1",
                "exposure_memory": "exposure_memory_v1",
                "persistence": "persistence_v1",
                "classification": "classification_v1",
            },
            configuration=self.config.model_dump(),
            source_observation_ids=[obs.observation_id] if hasattr(obs, 'observation_id') else [],
            source_forecast_ids=[obs.forecast_id] if hasattr(obs, 'forecast_id') else [],
        )

        # --- 9. Explanation ---
        explanation = get_classification_explanation(classification, indices, None)

        # --- 10. Assemble result ---
        result = ThermalStressResult(
            calculation_id=calculation_id,
            location_id=location_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp,
            source_type=source_type,
            inputs=thermal_input,
            indices=indices,
            nighttime=None,  # Would need hourly data
            exposure=ExposureMetrics(
                daily_stress=memory_result.current_stress_contribution,
                cumulative_exposure_24h=cumulative.get("cumulative_exposure_24h"),
                cumulative_exposure_72h=cumulative.get("cumulative_exposure_72h"),
                cumulative_exposure_7d=cumulative.get("cumulative_exposure_7d"),
                exposure_memory=memory_result.exposure_memory,
                memory_decay_factor=memory_result.decay_factor,
                memory_window_hours=memory_result.window_hours,
            ),
            classification=classification,
            quality=quality,
            provenance=provenance,
            explanation=explanation,
        )

        return result

    def calculate_batch(
        self,
        observations: List[Union[WeatherObservation, WeatherForecast, AirQualityObservation]],
        source_type: str,
        location_id: str,
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> List[ThermalStressResult]:
        """Calculate thermal stress for a batch of observations."""
        results = []
        for obs in observations:
            try:
                result = self.calculate_single(obs, source_type, location_id, latitude, longitude)
                results.append(result)
            except Exception as e:
                # Log error but continue
                import logging
                logging.getLogger("keshav.thermal").error(
                    f"Thermal calculation failed for {obs}: {e}"
                )
        return results

    def persist_results(
        self,
        results: List[ThermalStressResult],
        run_id: str,
    ) -> None:
        """Persist thermal stress results to database."""
        from ..models.thermal import ThermalStressResult as ResultModel

        for result in results:
            model = ResultModel(
                calculation_id=result.calculation_id,
                location_id=result.location_id,
                latitude=result.latitude,
                longitude=result.longitude,
                timestamp=result.timestamp,
                source_type=result.source_type,
                air_temperature_c=result.inputs.air_temperature_c,
                relative_humidity=result.inputs.relative_humidity,
                wind_speed_ms=result.inputs.wind_speed_ms,
                wind_direction_deg=result.inputs.wind_direction_deg,
                pressure_hpa=result.inputs.pressure_hpa,
                solar_radiation_wm2=result.inputs.solar_radiation_wm2,
                cloud_cover_pct=result.inputs.cloud_cover_pct,
                heat_index_c=result.indices.heat_index_c,
                heat_index_f=result.indices.heat_index_f,
                wet_bulb_c=result.indices.wet_bulb_c,
                wbgt_c=result.indices.wbgt_c,
                wbgt_indoor_c=result.indices.wbgt_indoor_c,
                utci_c=result.indices.utci_c,
                mrt_c=result.indices.mrt_c,
                thermal_stress_category=result.classification.thermal_stress_category,
                occupational_heat_category=result.classification.occupational_heat_category,
                nighttime_recovery_category=result.classification.nighttime_recovery_category,
                quality_summary=result.quality.quality_summary,
                uncertainty_summary=result.quality.uncertainty_summary,
                method_versions=result.provenance.method_versions,
                configuration=result.provenance.configuration,
                provenance=result.provenance.provenance.model_dump(mode="json") if result.provenance.provenance else None,
            )
            self.db.add(model)

        self.db.commit()