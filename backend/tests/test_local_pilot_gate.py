import pytest
from fastapi import HTTPException, Request
from starlette.applications import Starlette

from app.config import settings


@pytest.mark.parametrize("environment,enabled,bind,client,forwarded,allowed", [
    ("test", True, "127.0.0.1", "127.0.0.1", False, True),
    ("local", True, "127.0.0.1", "127.0.0.1", False, True),
    ("development", True, "127.0.0.1", "127.0.0.1", False, True),
    ("production", True, "127.0.0.1", "127.0.0.1", False, False),
    ("test", False, "127.0.0.1", "127.0.0.1", False, False),
    ("test", True, "0.0.0.0", "127.0.0.1", False, False),
    ("test", True, "127.0.0.1", "192.0.2.2", False, False),
    ("test", True, "127.0.0.1", "127.0.0.1", True, False),
])
def test_gate_checks_real_listener_and_request(
    monkeypatch, environment, enabled, bind, client, forwarded, allowed,
):
    from app.local_pilot import PilotListener, require_local_pilot
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "local_pilot_enabled", enabled)
    application = Starlette()
    with PilotListener() as listener:
        listener.bind((bind, 0))
        listener.listen()
        application.state.local_pilot_listener = listener
        port = listener.getsockname()[1]
        request = Request({
            "type": "http", "app": application,
            "server": ("127.0.0.1", port), "client": (client, 23456),
            "headers": [(b"x-forwarded-for", b"127.0.0.1")] if forwarded else [],
        })
        if allowed:
            require_local_pilot(request)
        else:
            with pytest.raises(HTTPException) as error:
                require_local_pilot(request)
            assert error.value.status_code == 404


def test_gate_rejects_missing_closed_or_mismatched_listener(monkeypatch):
    from app.local_pilot import PilotListener, require_local_pilot
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "local_pilot_enabled", True)
    application = Starlette()
    request = Request({"type": "http", "app": application,
                       "server": ("127.0.0.1", 1), "client": ("127.0.0.1", 2), "headers": []})
    with pytest.raises(HTTPException):
        require_local_pilot(request)
    with PilotListener() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        application.state.local_pilot_listener = listener
        with pytest.raises(HTTPException):
            require_local_pilot(request)
    with pytest.raises(HTTPException):
        require_local_pilot(request)


@pytest.mark.parametrize("bind,expected", [("127.0.0.1", 200), ("0.0.0.0", 404)])
def test_real_http_boundary_uses_listening_bind_not_accepted_connection(monkeypatch, bind, expected):
    import threading
    import time
    import httpx
    import uvicorn
    from app.local_pilot import PilotListener
    from app.main import app

    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "local_pilot_enabled", True)
    with PilotListener() as listener:
        listener.bind((bind, 0))
        listener.listen()
        app.state.local_pilot_listener = listener
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, proxy_headers=False, lifespan="off", log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 3
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            with httpx.Client(base_url=address, timeout=2) as client:
                assert client.get("/api/health").status_code == 200
                assert client.get("/api/practice/availability").status_code == expected
                assert client.get("/api/practice/availability", headers={"Forwarded": "for=127.0.0.1"}).status_code == 404
                assert client.get("/api/practice/availability", headers={"Origin": "https://example.invalid"}).status_code == 404
                monkeypatch.setattr(settings, "local_pilot_enabled", False)
                assert client.get("/api/practice/availability").status_code == 404
                assert client.get("/api/health").status_code == 200
                monkeypatch.setattr(settings, "local_pilot_enabled", True)
                monkeypatch.setattr(settings, "environment", "production")
                assert client.get("/api/practice/availability").status_code == 404
        finally:
            server.should_exit = True
            thread.join(timeout=4)
            del app.state.local_pilot_listener
            assert not thread.is_alive()
