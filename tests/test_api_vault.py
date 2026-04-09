"""Integration tests for vault API endpoints.

Requires:
  - Backend running at http://localhost:8000
  - Database seeded via 'tennetctl setup --env dev --mode a --yes'

Run with:
  pytest tests/test_api_vault.py -v -m integration
"""

import pytest
import httpx


BASE = "http://localhost:58000"


@pytest.mark.integration
def test_healthz():
    res = httpx.get(f"{BASE}/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "ok"


@pytest.mark.integration
def test_readyz():
    res = httpx.get(f"{BASE}/readyz")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "ready"


@pytest.mark.integration
def test_vault_status():
    res = httpx.get(f"{BASE}/v1/vault/status")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["initialized"] is True
    assert data["status"] == "unsealed"
    assert data["unseal_mode"] == "manual"
    assert data["initialized_at"] is not None
