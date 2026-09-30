"""Cascading Infrastructure Failure Engine: Models multi-system compound breakdowns
across Climate, Power, Water, Cooling, Exposure, Healthcare, and Emergency Response.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.digital_twin import CascadeGraphDB
from ..utils.time import utcnow
from .schemas import (
    CascadeEdge,
    CascadeNode,
    CascadeSimulationRequest,
    CascadeSimulationResponse,
    RelationshipStatus,
)


class ResilienceCascadeEngine:
    """Simulates multi-sector cascade vulnerability networks during compound heat events."""

    @classmethod
    def simulate_cascade(
        cls, db: Session, req: CascadeSimulationRequest
    ) -> CascadeSimulationResponse:
        """Propagates heat stress through infrastructure nodes to calculate cascade vulnerability."""
        graph_id = f"casc_{uuid.uuid4().hex[:8]}"

        # Base climate forcing
        heat_forcing = 0.85  # Severe heatwave baseline
        
        # Grid state calculation
        base_grid_stress = 0.40
        grid_contingency_adder = 0.35 if req.power_grid_contingency else 0.0
        grid_heat_adder = heat_forcing * 0.30
        power_stress = min(1.0, base_grid_stress + grid_contingency_adder + grid_heat_adder)
        power_capacity_pct = max(0.0, (1.0 - power_stress) * 100.0)

        # Cooling system state
        cooling_loss_from_grid = power_stress * 0.50
        cooling_loss_forced = (req.cooling_failure_rate_pct / 100.0) * 0.40
        cooling_failure_prob = min(1.0, cooling_loss_from_grid + cooling_loss_forced + 0.10)
        cooling_capacity_pct = max(0.0, (1.0 - cooling_failure_prob) * 100.0)

        # Water infrastructure state
        water_base_stress = 0.30
        water_strain_adder = 0.35 if req.water_system_strain else 0.0
        water_heat_adder = heat_forcing * 0.25
        water_stress = min(1.0, water_base_stress + water_strain_adder + water_heat_adder)
        water_capacity_pct = max(0.0, (1.0 - water_stress) * 100.0)

        # Population thermal exposure spike
        exposure_stress = min(1.0, heat_forcing * 0.50 + cooling_failure_prob * 0.35 + water_stress * 0.15)
        exposure_capacity_pct = max(0.0, (1.0 - exposure_stress) * 100.0)

        # Healthcare system surge
        healthcare_stress = min(1.0, exposure_stress * 0.70 + (1.0 - power_capacity_pct / 100.0) * 0.20)
        healthcare_surge_mult = round(1.0 + healthcare_stress * 2.2, 2)
        hospital_capacity_pct = max(5.0, 100.0 - (healthcare_surge_mult - 1.0) * 40.0)

        # Overall compound stress index
        compound_stress = round(
            (power_stress * 0.25 + cooling_failure_prob * 0.25 + water_stress * 0.20 + healthcare_stress * 0.30),
            3,
        )

        # Construct Nodes
        nodes = [
            CascadeNode(
                id="node_climate",
                name="Extreme Heatwave Forcing",
                layer="CLIMATE",
                status="CRITICAL" if heat_forcing > 0.7 else "STRESSED",
                stress_index=round(heat_forcing, 2),
                capacity_remaining_pct=round((1.0 - heat_forcing) * 100.0, 1),
                metadata={"forcing_metric": "Heat Index > 48C"},
            ),
            CascadeNode(
                id="node_power",
                name="Urban Electricity Distribution & Substation Grid",
                layer="INFRASTRUCTURE",
                status="FAILED" if power_capacity_pct < 20.0 else ("CRITICAL" if power_capacity_pct < 45.0 else "STRESSED"),
                stress_index=round(power_stress, 2),
                capacity_remaining_pct=round(power_capacity_pct, 1),
                metadata={"contingency_active": req.power_grid_contingency},
            ),
            CascadeNode(
                id="node_cooling",
                name="Cooling Shelters & Commercial HVAC Networks",
                layer="INFRASTRUCTURE",
                status="FAILED" if cooling_capacity_pct < 20.0 else ("CRITICAL" if cooling_capacity_pct < 50.0 else "STRESSED"),
                stress_index=round(cooling_failure_prob, 2),
                capacity_remaining_pct=round(cooling_capacity_pct, 1),
                metadata={"failure_probability": round(cooling_failure_prob, 2)},
            ),
            CascadeNode(
                id="node_water",
                name="Municipal Water Supply & Pressure Network",
                layer="INFRASTRUCTURE",
                status="CRITICAL" if water_capacity_pct < 40.0 else "STRESSED",
                stress_index=round(water_stress, 2),
                capacity_remaining_pct=round(water_capacity_pct, 1),
                metadata={"system_strain": req.water_system_strain},
            ),
            CascadeNode(
                id="node_exposure",
                name="Vulnerable Population Thermal Burden",
                layer="SOCIAL",
                status="CRITICAL" if exposure_stress > 0.7 else "STRESSED",
                stress_index=round(exposure_stress, 2),
                capacity_remaining_pct=round(exposure_capacity_pct, 1),
                metadata={"vulnerable_exposure_level": "EXTREME"},
            ),
            CascadeNode(
                id="node_healthcare",
                name="Emergency Hospital & EMS Capacity",
                layer="HEALTH",
                status="CRITICAL" if hospital_capacity_pct < 35.0 else "STRESSED",
                stress_index=round(healthcare_stress, 2),
                capacity_remaining_pct=round(hospital_capacity_pct, 1),
                metadata={"surge_multiplier": healthcare_surge_mult},
            ),
        ]

        # Construct Edges
        edges = [
            CascadeEdge(
                source="node_climate",
                target="node_power",
                relationship_type="STRAINS",
                coupling_strength=0.85,
                relationship_status=RelationshipStatus.MODEL_BASED,
                description="High ambient temperature increases air-conditioning load and decreases transformer efficiency.",
            ),
            CascadeEdge(
                source="node_power",
                target="node_cooling",
                relationship_type="FAILS",
                coupling_strength=0.92,
                relationship_status=RelationshipStatus.MODEL_BASED,
                description="Power substation overload causes brownouts and cooling center HVAC outages.",
            ),
            CascadeEdge(
                source="node_climate",
                target="node_water",
                relationship_type="STRAINS",
                coupling_strength=0.75,
                relationship_status=RelationshipStatus.MODEL_BASED,
                description="Elevated evaporation and peak drinking demand deplete municipal buffer tanks.",
            ),
            CascadeEdge(
                source="node_cooling",
                target="node_exposure",
                relationship_type="OVERLOADS",
                coupling_strength=0.88,
                relationship_status=RelationshipStatus.MODEL_BASED,
                description="Loss of passive and active cooling exposes indoor occupants to dangerous core body temperatures.",
            ),
            CascadeEdge(
                source="node_water",
                target="node_exposure",
                relationship_type="STRAINS",
                coupling_strength=0.70,
                relationship_status=RelationshipStatus.MODEL_BASED,
                description="Lack of accessible hydration accelerates physiological heat exhaustion.",
            ),
            CascadeEdge(
                source="node_exposure",
                target="node_healthcare",
                relationship_type="OVERLOADS",
                coupling_strength=0.94,
                relationship_status=RelationshipStatus.MODEL_BASED,
                description="Heat exhaustion progresses to heat stroke, causing ambulance and ICU surges.",
            ),
        ]

        critical_path = ["node_climate", "node_power", "node_cooling", "node_exposure", "node_healthcare"]

        # Persist in DB
        db_record = CascadeGraphDB(
            graph_id=graph_id,
            scenario_id=req.scenario_id,
            location_id=req.location_id,
            compound_stress_index=compound_stress,
            power_stress_level=round(power_stress, 2),
            water_deficit_level=round(water_stress, 2),
            cooling_failure_probability=round(cooling_failure_prob, 2),
            healthcare_surge_multiplier=healthcare_surge_mult,
            nodes=[n.model_dump() for n in nodes],
            edges=[e.model_dump() for e in edges],
            relationship_status=RelationshipStatus.MODEL_BASED.value,
            simulated_at=utcnow(),
        )
        db.add(db_record)
        db.commit()

        return CascadeSimulationResponse(
            graph_id=graph_id,
            scenario_id=req.scenario_id,
            location_id=req.location_id,
            compound_stress_index=compound_stress,
            power_stress_level=round(power_stress, 2),
            water_deficit_level=round(water_stress, 2),
            cooling_failure_probability=round(cooling_failure_prob, 2),
            healthcare_surge_multiplier=healthcare_surge_mult,
            nodes=nodes,
            edges=edges,
            relationship_status=RelationshipStatus.MODEL_BASED.value,
            critical_failure_path=critical_path,
            simulated_at=utcnow(),
        )
