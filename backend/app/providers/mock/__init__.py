"""Deterministic mock data generators for weather, forecast, air quality,
locations, vulnerability and aggregated health outcomes.

All generators are seeded and reproducible: the same ``(seed, scenario,
location, window)`` always yields the same series — required for reliable tests,
demos and future scenario-based evaluations.
"""