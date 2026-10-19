"""
Integration tests for Health and OpenAPI endpoints
"""
import pytest
import httpx


@pytest.mark.asyncio
async def test_health_check_endpoint(client: httpx.AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert data["storage_ready"] is True
    assert data["version"] == "1.0.0"
    assert "salary_finder" in data["models"]
    assert "decision_engine" in data["models"]


@pytest.mark.asyncio
async def test_openapi_json(client: httpx.AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "SalaryLens AI by CodeSec"
    assert "/api/v1/health" in spec["paths"]
