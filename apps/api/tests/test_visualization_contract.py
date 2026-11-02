from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import visualizations
from app.auth import get_current_user
from app.db import get_connection
from app.main import app


def test_browser_can_read_retry_after_and_send_idempotency_key(monkeypatch):
    def limited(*args, **kwargs):
        raise HTTPException(429, "Visualization limit exceeded", headers={"Retry-After": "120"})

    monkeypatch.setattr(visualizations, "enqueue", limited)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: object())
    monkeypatch.setitem(app.dependency_overrides, get_connection, lambda: object())
    client = TestClient(app)
    preflight = client.options(
        "/visualizations",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Idempotency-Key",
        },
    )
    assert preflight.status_code == 200
    response = client.post(
        "/visualizations",
        headers={"Origin": "http://localhost:5173", "Idempotency-Key": "test"},
        data={"description": "A playground"},
        files={"photos": ("site.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 429 and response.headers["Retry-After"] == "120"
    assert "Retry-After" in response.headers["Access-Control-Expose-Headers"]
