"""Verified loopback listener for the opt-in, supervised written pilot."""

import argparse
import errno
from ipaddress import ip_address
import socket

from fastapi import HTTPException, Request

from app.config import settings


class PilotListener(socket.socket):
    """Register listen() on the actual socket handed to the ASGI server."""

    listening = False

    def listen(self, backlog: int = 128) -> None:
        super().listen(backlog)
        self.listening = True

    def is_listening(self) -> bool:
        if self.fileno() < 0 or not self.listening:
            return False
        try:
            return bool(self.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN))
        except OSError as error:
            # Some macOS/Python combinations expose SO_ACCEPTCONN but reject
            # getsockopt for it. The successful listen() registration survives.
            if error.errno == errno.ENOPROTOOPT:
                return self.listening
            raise


def _loopback(host: str) -> bool:
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def require_local_pilot(request: Request) -> None:
    allowed = settings.local_pilot_enabled and settings.environment.strip().casefold() in {
        "local", "development", "test",
    }
    listener = getattr(request.app.state, "local_pilot_listener", None)
    try:
        if not isinstance(listener, PilotListener) or not listener.is_listening():
            allowed = False
        else:
            endpoint = listener.getsockname()
            server = request.scope.get("server")
            client = request.scope.get("client")
            allowed = bool(
                allowed
                and _loopback(endpoint[0]) and server and client
                and _loopback(server[0]) and _loopback(client[0])
                and server[1] == endpoint[1]
                and ip_address(server[0]) == ip_address(endpoint[0])
            )
    except (OSError, ValueError, TypeError):
        allowed = False
    if any(name == "forwarded" or name.startswith("x-forwarded-") for name in request.headers):
        allowed = False
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        allowed = False
    if not allowed:
        raise HTTPException(status_code=404, detail="Local practice unavailable")


def main() -> None:
    """Supply the same listening socket to Uvicorn and the request guard."""
    import uvicorn
    from app.main import app

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not settings.local_pilot_enabled or settings.environment.strip().casefold() not in {
        "local", "development", "test",
    }:
        parser.error("explicit local environment and LOCAL_PILOT_ENABLED=true required")
    with PilotListener(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
        app.state.local_pilot_listener = listener
        try:
            uvicorn.Server(uvicorn.Config(app, proxy_headers=False)).run(sockets=[listener])
        finally:
            del app.state.local_pilot_listener


if __name__ == "__main__":
    # The router imports app.local_pilot. Use that same module's listener class;
    # a __main__.PilotListener fails its isinstance guard under python -m.
    from app.local_pilot import main as canonical_main
    canonical_main()
