"""Every route the console asks for must exist on the API.

The console builds its URLs as BASE + path, where BASE is already "/api". A path
written with the prefix included asked for /api/api/demo/reset, and the static
file mount answered 405 rather than 404 — so the console reported a method
problem for a route that was simply not there.

Reading the paths out of api.js and checking them against the app's own route
table catches that without a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from muster.api.app import create_app

API_JS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api.js"

#: request('/world') and request(`/schedule/${...}`), with the method if given.
CALL = re.compile(
    r"request\(\s*[`'\"](?P<path>/[^`'\"]*)[`'\"]"
    r"(?:\s*,\s*\{[^}]*method:\s*'(?P<method>[A-Z]+)')?",
)


def _console_calls() -> list[tuple[str, str]]:
    source = API_JS.read_text()
    return [(m.group("method") or "GET", m.group("path")) for m in CALL.finditer(source)]


def test_the_console_asks_for_paths_that_exist():
    calls = _console_calls()
    assert calls, "no request() calls found — the regex has drifted from api.js"

    app = create_app()
    routes = {(method, route.path) for route in app.routes
              for method in getattr(route, "methods", set())}

    # The console's paths are relative to BASE, and its template literals leave
    # ${...} where the API declares {param}.
    declared = {(m, p.removeprefix("/api")) for m, p in routes}
    declared = {(m, re.sub(r"\{[^}]+\}", "*", p)) for m, p in declared}

    missing = []
    for method, path in calls:
        normalised = re.sub(r"\$\{[^}]+\}", "*", path)
        if (method, normalised) not in declared:
            missing.append(f"{method} {path}")
    assert not missing, f"the console asks for routes the API does not serve: {missing}"


def test_no_path_in_the_client_repeats_the_base_prefix():
    doubled = [p for _, p in _console_calls() if p.startswith("/api")]
    assert not doubled, (
        f"BASE is already '/api'; these would resolve to /api/api/...: {doubled}"
    )


@pytest.mark.parametrize("path", ["/api/demo/reset"])
def test_the_reset_route_is_a_post(path):
    client = TestClient(create_app())
    assert client.post(path).status_code == 200
    assert client.get(path).status_code == 405
