"""KESHAV STEP 6: What-If Intervention and Counterfactual Simulation Engine.

Provides a complete counterfactual simulation layer for health risk predictions.

Key scientific principles:
- Never make unsupported causal claims
- Always distinguish observed vs simulated vs model-predicted
- Use qualified language (simulated, modeled, counterfactual) not absolute (guaranteed, prevented, caused)
- Feature recomputation, not direct probability manipulation
- Uncertainty and OOD propagation from Step 5
- Equity and data-coverage auditing from Step 5
- Reproducible and provenance-tracked

All outputs must clearly identify as model-based counterfactual simulations.
"""

__version__ = "6.0.0"