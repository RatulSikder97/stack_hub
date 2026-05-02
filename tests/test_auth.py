"""Auth + admin route tests against the FastAPI app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pipeline.web import create_app


@pytest.fixture
def auth_client(tmp_project, monkeypatch):  # noqa: ANN001
    """Build a client with auth enabled. Default credentials: admin/admin, user/user."""
    monkeypatch.setenv("AUTH_DISABLED", "false")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-admin-pw")
    monkeypatch.setenv("USER_USERNAME", "user")
    monkeypatch.setenv("USER_PASSWORD", "secret-user-pw")
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    return TestClient(create_app())


def test_unauthenticated_pipeline_endpoint_returns_401(auth_client) -> None:  # noqa: ANN001
    res = auth_client.get("/api/status")
    assert res.status_code == 401


def test_login_with_bad_credentials_returns_401(auth_client) -> None:  # noqa: ANN001
    res = auth_client.post(
        "/api/auth/login", json={"username": "admin", "password": "nope"}
    )
    assert res.status_code == 401


def test_login_with_admin_credentials_sets_cookie(auth_client) -> None:  # noqa: ANN001
    res = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body == {"username": "admin", "role": "admin"}
    assert "stack_hub_session" in res.cookies


def test_session_cookie_grants_access_to_protected_endpoints(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_user_role_cannot_access_admin_endpoints(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "user", "password": "secret-user-pw"},
    )
    res = auth_client.get("/api/admin/files")
    assert res.status_code == 403


def test_admin_role_can_access_admin_endpoints(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.get("/api/admin/files")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    paths = {item["path"] for item in items}
    assert "voice/voice_map.md" in paths
    assert "data/config.json" in paths


def test_logout_clears_session(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    auth_client.post("/api/auth/logout")
    auth_client.cookies.clear()
    res = auth_client.get("/api/auth/me")
    assert res.status_code == 401


def test_admin_can_read_and_write_a_whitelisted_file(auth_client, tmp_project) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.get("/api/admin/files/voice/brand_promise.md")
    assert res.status_code == 200
    body = res.json()
    assert "Sample promise" in body["content"]

    new_content = "# Brand Promise\n\nUpdated promise.\n"
    res = auth_client.put(
        "/api/admin/files/voice/brand_promise.md",
        json={"path": "voice/brand_promise.md", "content": new_content},
    )
    assert res.status_code == 200
    assert (tmp_project / "voice" / "brand_promise.md").read_text() == new_content


def test_resolve_editable_path_rejects_traversal(tmp_project) -> None:  # noqa: ANN001
    """Unit-test the resolver directly — httpx normalizes URL paths so an HTTP
    test of `..` would never reach our handler."""
    from fastapi import HTTPException

    from pipeline.web.api import _resolve_editable_path

    with pytest.raises(HTTPException):
        _resolve_editable_path("../../etc/passwd")
    with pytest.raises(HTTPException):
        _resolve_editable_path("voice/../data/posts.json")


def test_admin_rejects_non_whitelisted_file(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.get("/api/admin/files/data/posts.json")
    assert res.status_code == 403


def test_admin_can_delete_corpus_file(auth_client, tmp_project) -> None:  # noqa: ANN001
    writer = tmp_project / "corpus" / "test_writer"
    writer.mkdir(parents=True, exist_ok=True)
    target = writer / "post_1.md"
    target.write_text("hello", encoding="utf-8")

    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.delete("/api/admin/files/corpus/test_writer/post_1.md")
    assert res.status_code == 200
    assert not target.exists()


def test_admin_cannot_delete_whitelisted_file(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.delete("/api/admin/files/voice/brand_promise.md")
    assert res.status_code == 400


def test_invalid_json_in_config_is_rejected(auth_client) -> None:  # noqa: ANN001
    auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-admin-pw"},
    )
    res = auth_client.put(
        "/api/admin/files/data/config.json",
        json={"path": "data/config.json", "content": "{ not valid json"},
    )
    assert res.status_code == 400
