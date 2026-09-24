import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SNIPBOX_DB_PATH", str(tmp_path / "test.db"))
    for name in [m for m in sys.modules if m.startswith("app")]:
        del sys.modules[name]
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["snippets"] == 0


def test_create_then_read_snippet(client):
    created = client.post("/snippets", json={"content": "print(1)", "language": "python"})
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "untitled"
    assert len(body["id"]) == 8

    fetched = client.get(f"/snippets/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_list_and_delete(client):
    ids = [
        client.post("/snippets", json={"content": f"snippet {i}"}).json()["id"]
        for i in range(3)
    ]
    listed = client.get("/snippets", params={"limit": 2})
    assert listed.status_code == 200
    assert listed.json()["total"] == 3
    assert len(listed.json()["items"]) == 2

    assert client.delete(f"/snippets/{ids[0]}").status_code == 204
    assert client.delete(f"/snippets/{ids[0]}").status_code == 404
    assert client.get(f"/snippets/{ids[0]}").status_code == 404


def test_empty_content_is_rejected(client):
    assert client.post("/snippets", json={"content": ""}).status_code == 422


def test_data_survives_a_restart(tmp_path, monkeypatch):
    """The same database file, reopened, still has the snippet."""
    monkeypatch.setenv("SNIPBOX_DB_PATH", str(tmp_path / "persist.db"))

    def fresh_app():
        for name in [m for m in sys.modules if m.startswith("app")]:
            del sys.modules[name]
        from app.main import app

        return app

    with TestClient(fresh_app()) as first:
        snippet_id = first.post("/snippets", json={"content": "keep me"}).json()["id"]

    with TestClient(fresh_app()) as second:
        assert second.get(f"/snippets/{snippet_id}").json()["content"] == "keep me"
