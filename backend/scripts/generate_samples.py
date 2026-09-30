"""Generate deterministic demo sample files into data/samples.

Run from backend/:  python scripts/generate_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import init_db  # noqa: E402
from app.services.bootstrap import generate_demo_samples  # noqa: E402

if __name__ == "__main__":
    init_db()
    generate_demo_samples(days=int(sys.argv[1]) if len(sys.argv) > 1 else 2)
    print("Sample files written under data/samples/")