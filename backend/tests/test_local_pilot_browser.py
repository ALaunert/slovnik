"""Opt-in real-browser integration on disposable file SQLite and real loopback servers."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import UserProfile
from app.services.reviewed_pilot_publication_service import ContentPublicationService
from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def await_http(url, process):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("Integration server exited before readiness")
        try:
            with urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.05)
    raise AssertionError("Integration server readiness timed out")


@pytest.mark.skipif(os.getenv("SLOVNIK_RUN_BROWSER_INTEGRATION") != "1", reason="Opt-in real browser integration")
def test_real_local_written_browser_flow(tmp_path):
    from datetime import datetime, timezone
    node = os.getenv("SLOVNIK_NODE_BINARY") or shutil.which("node")
    assert node, "Provide SLOVNIK_NODE_BINARY or put Node on PATH"
    root = Path(__file__).resolve().parents[2]
    database_url = f"sqlite+pysqlite:///{tmp_path / 'browser-pilot.sqlite'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(UserProfile(user_id="browser-pilot-test"))
        session.commit()
        ContentPublicationService(session).publish(
            load_reviewed_pilot_bundle(root / "content/curricula/a1-pilot/publication-v1.json"),
            published_at=datetime.now(timezone.utc),
        )
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    environment = {**os.environ, "ENVIRONMENT": "test", "DATABASE_URL": database_url,
                   "EDITOR_PASSWORD": "test-editor-password", "LOCAL_PILOT_ENABLED": "true",
                   "LANGUAGE_ASSISTANT_SHADOW_ENABLED": "false", "OPENAI_API_KEY": "",
                   "CORS_ORIGINS": json.dumps([ui_url]), "VITE_API_BASE_URL": api_url,
                   "PILOT_API_URL": api_url, "PILOT_FRONTEND_URL": ui_url}
    processes = []
    try:
        with (tmp_path / "servers.log").open("w+") as log:
            processes.append(subprocess.Popen([sys.executable, "-m", "app.local_pilot", "--port", str(api_port)],
                                               cwd=root / "backend", env=environment, stdout=log, stderr=log))
            await_http(f"{api_url}/api/practice/availability", processes[-1])
            processes.append(subprocess.Popen([node, "node_modules/vite/bin/vite.js", "--host", "127.0.0.1",
                                                "--port", str(ui_port), "--strictPort"],
                                               cwd=root / "frontend", env=environment, stdout=log, stderr=log))
            await_http(ui_url, processes[-1])
            result = subprocess.run([node, "tests/integration/local-written-flow.mjs"], cwd=root / "frontend",
                                    env=environment, capture_output=True, text=True, timeout=45)
            assert result.returncode == 0, result.stdout + result.stderr
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        engine.dispose()
