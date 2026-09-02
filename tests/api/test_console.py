"""The console mount, and the order it must be registered in.

`create_app` mounts `StaticFiles` at `/` only when `MUSTER_CONSOLE_DIR` is set
and points at a real directory - and only *after* every `/api` route is
registered. A mount at `/` registered first would swallow every API route
underneath it; that is exactly what `test_the_api_still_answers_once_the_console_is_mounted`
below catches.
"""

from fastapi.testclient import TestClient

from muster.api.app import create_app
from muster.loops.hold.runner import HoldRunResult


def _client():
    async def noop_hold(state, disruption):
        return HoldRunResult(False, None, None, None, "covered")

    async def noop_resume(state, pending):
        return HoldRunResult(False, None, None, None, "resumed")

    async def noop_draft(state, site_id):
        return HoldRunResult(False, None, None, None, "drafted")

    app = create_app(hold_runner=noop_hold, draft_runner=noop_draft, decision_resumer=noop_resume)
    return TestClient(app)


def test_no_console_mounted_when_env_var_is_unset(monkeypatch):
    monkeypatch.delenv("MUSTER_CONSOLE_DIR", raising=False)
    client = _client()
    assert client.get("/").status_code == 404
    assert client.get("/health").json() == {"status": "ok"}


def test_console_is_served_and_the_api_still_answers(tmp_path, monkeypatch):
    index = tmp_path / "index.html"
    index.write_text("<html><body>muster console</body></html>")
    monkeypatch.setenv("MUSTER_CONSOLE_DIR", str(tmp_path))

    client = _client()

    response = client.get("/")
    assert response.status_code == 200
    assert "muster console" in response.text

    world = client.get("/api/world")
    assert world.status_code == 200
    assert "sites" in world.json()
