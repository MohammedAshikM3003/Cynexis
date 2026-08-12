"""Integration tests for the FastAPI backend."""

import sys
import os
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import pytest
from httpx import AsyncClient, ASGITransport

from Backend.api.server import app


@pytest.fixture
def transport():
    """ASGI transport with lifespan support."""
    return ASGITransport(app=app, raise_app_exceptions=False)


# ============================================================
# TESTS THAT WORK WITHOUT LIFESPAN (no DB needed)
# ============================================================

@pytest.mark.asyncio
async def test_health(transport):
    """GET /health returns ok."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["name"] == "CYNEXIS"


@pytest.mark.asyncio
async def test_status(transport):
    """GET /api/status returns full state."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "rover" in data
    assert "arm" in data
    assert "battery_pct" in data


@pytest.mark.asyncio
async def test_diagnostics(transport):
    """GET /api/diagnostics returns subsystem info."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/diagnostics")
    assert resp.status_code == 200
    data = resp.json()
    assert "subsystems" in data
    assert "features" in data


# ============================================================
# TESTS THAT NEED LIFESPAN (DB + controllers)
# These use the full app lifecycle via httpx lifespan support.
# ============================================================

@pytest.mark.asyncio
async def test_command_hello_with_lifespan():
    """POST /api/command with HELLO succeeds (full lifespan)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as client:
        # Manually trigger lifespan
        async with app.router.lifespan_context(app):
            resp = await client.post("/api/command", json={"action": "HELLO"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["action"] == "HELLO"


@pytest.mark.asyncio
async def test_command_stop_with_lifespan():
    """POST /api/command with STOP succeeds (full lifespan)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as client:
        async with app.router.lifespan_context(app):
            resp = await client.post("/api/command", json={"action": "STOP"})
            assert resp.status_code == 200
            assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_command_rejected_with_lifespan():
    """POST /api/command with invalid action is rejected (403)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as client:
        async with app.router.lifespan_context(app):
            resp = await client.post("/api/command", json={"action": "HACK_MOTORS"})
            assert resp.status_code == 403


@pytest.mark.asyncio
async def test_capture_with_lifespan():
    """POST /api/capture takes a photo (full lifespan)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as client:
        async with app.router.lifespan_context(app):
            resp = await client.post("/api/capture")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
