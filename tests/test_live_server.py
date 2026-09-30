"""Optional live-server integration test.

Starts the real backend with uvicorn, waits for it to come up, then verifies a
handful of endpoints over real HTTP. Skipped automatically when the stack's
deps (uvicorn/httpx) are unavailable.

Run from repo root:  python -m pytest tests/test_live_server.py -v
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

try:
    import httpx  # noqa: F401
    import uvicorn  # noqa: F401
    HAS_STACK = True
except Exception:  # pragma: no cover
    HAS_STACK = False


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_healthy(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


@pytest.mark.skipif(not HAS_STACK, reason="uvicorn/httpx not installed in this interpreter")
def test_live_server_health_and_endpoints():
    os.environ["MOCK_MODE"] = "true"
    os.environ["MOCK_SEED"] = "2026"
    os.environ.setdefault("DATABASE_URL", "sqlite:///./keshav_live_test.db")
    port = _free_port()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(BACKEND),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_healthy(port), "server did not become healthy"
        base = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=base, timeout=10) as c:
            assert c.get("/api/v1/system/info").status_code == 200
            loc = c.get("/api/v1/locations")
            assert loc.status_code == 200 and loc.json()["count"] == 10
            w = c.get("/api/v1/weather?location_id=DEMO-WARD-01")
            assert w.status_code == 200 and w.json()["count"] > 0
            f = c.get("/api/v1/forecast?location_id=DEMO-WARD-01&horizon_hours=24")
            assert f.status_code == 200 and f.json()["count"] == 24
            assert c.get("/api/v1/air-quality?location_id=DEMO-WARD-01").status_code == 200
            prov = c.get("/api/v1/provider-status").json()
            assert len(prov) == 6
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()