"""KESHAV STEP 5: Explanation, Uncertainty, and Equity Engine.

Provides prediction explainability, uncertainty estimation, and fairness auditing
for health risk predictions. All components are designed to integrate with the
existing Step 4 risk prediction pipeline.

Key principles:
- Explanations describe model behavior, not causal effects
- Data quality ≠ safety (data-poor areas must not become low risk)
- Uncertainty metrics are separate from risk probability
- All explanations are provenance-tracked and auditable
"""

__version__ = "5.0.0"