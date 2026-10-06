"""Shared helpers for the Sahayta simulation package.

- Repository path constants.
- Minimal stdlib HTTP client (urllib) speaking the frozen API contracts.
- ``BackendBoot``: context manager that fresh-seeds the backend DB and boots
  uvicorn on localhost, then tears it down. Used by the load simulator and
  the demo director so both are one-click and deterministic.

No third-party dependencies.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
DATA_DIR = REPO_ROOT / "data"
VENV_PY = BACKEND_DIR / ".venv" / "bin" / "python"
SIM_DIR = Path(__file__).resolve().parent

ADMIN_KEY = os.environ.get("SAHAYTA_ADMIN_KEY", "demo-admin-key")


class ApiError(Exception):
    """Raised when the backend returns a non-2xx status."""

    def __init__(self, method: str, path: str, status: int, body: str):
        super().__init__(f"{method} {path} -> {status}: {body[:300]}")
        self.method = method
        self.path = path
        self.status = status
        self.body = body


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {"Accept": "application/json"}
    if extra:
        h.update(extra)
    return h


def api_request(
    method: str,
    base_url: str,
    path: str,
    *,
    body: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    """Perform one HTTP request; return (status, parsed-JSON-or-text)."""
    data: bytes | None = None
    hdrs = _headers(headers)
    if body is not None and not isinstance(body, (bytes, bytearray)):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json; charset=utf-8"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body)
    req = urllib.request.Request(
        base_url.rstrip("/") + path, data=data, headers=hdrs, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype:
                return resp.status, json.loads(raw) if raw.strip() else None
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed: Any = json.loads(raw) if raw.strip() else raw
        except Exception:
            parsed = raw
        return exc.code, parsed


def api_get(base_url: str, path: str, **kw: Any) -> tuple[int, Any]:
    return api_request("GET", base_url, path, **kw)


def api_post(base_url: str, path: str, body: Any = None, **kw: Any) -> tuple[int, Any]:
    return api_request("POST", base_url, path, body=body, **kw)


def encode_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, str, bytes]]
) -> tuple[bytes, str]:
    """Build a multipart/form-data body. files: name -> (filename, mime, bytes)."""
    boundary = "----sahayta-sim-boundary-9f3a7c"
    buf = bytearray()
    for name, value in fields.items():
        buf += f"--{boundary}\r\n".encode()
        buf += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        buf += f"{value}\r\n".encode()
    for name, (filename, mime, content) in files.items():
        buf += f"--{boundary}\r\n".encode()
        buf += (
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        ).encode()
        buf += f"Content-Type: {mime}\r\n\r\n".encode()
        buf += content
        buf += b"\r\n"
    buf += f"--{boundary}--\r\n".encode()
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


def wait_for_health(base_url: str, timeout: float = 90.0) -> bool:
    """Poll /api/health until ok or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, payload = api_get(base_url, "/api/health", timeout=5.0)
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


class BackendBoot:
    """Fresh-seed + boot the backend on localhost; teardown on exit.

    Usage:
        with BackendBoot(port=8001) as base_url:
            ... drive the API ...
    """

    def __init__(self, port: int = 8001, fresh_seed: bool = True, seed_timeout: float = 600.0):
        self.port = port
        self.fresh_seed = fresh_seed
        self.seed_timeout = seed_timeout
        self.proc: subprocess.Popen[bytes] | None = None
        self.base_url = f"http://127.0.0.1:{port}"

    def _run_seed(self) -> None:
        if not self.fresh_seed:
            return
        print("[boot] seeding fresh DB (seed.py --fresh) ...", flush=True)
        cmd = [str(VENV_PY), "seed.py", "--fresh"]
        proc = subprocess.run(
            cmd, cwd=str(BACKEND_DIR), capture_output=True, text=True,
            timeout=self.seed_timeout,
        )
        if proc.returncode != 0:
            print(proc.stdout[-2000:], flush=True)
            print(proc.stderr[-2000:], flush=True)
            raise RuntimeError(f"seed.py --fresh failed (exit {proc.returncode})")
        print("[boot] seed complete.", flush=True)

    def __enter__(self) -> str:
        if not VENV_PY.exists():
            raise RuntimeError(f"backend venv python not found: {VENV_PY}")
        self._run_seed()
        if not _port_free(self.port):
            raise RuntimeError(f"port {self.port} already in use; stop the dev server first")
        print(f"[boot] starting uvicorn on :{self.port} ...", flush=True)
        self.proc = subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if not wait_for_health(self.base_url):
            self.__exit__(None, None, None)
            raise RuntimeError("backend did not become healthy in time")
        print(f"[boot] backend healthy at {self.base_url}", flush=True)
        return self.base_url

    def __exit__(self, *exc: Any) -> None:
        if self.proc is not None:
            print("[boot] stopping uvicorn ...", flush=True)
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


def load_districts() -> list[dict[str, Any]]:
    """Canonical 20 districts from data/districts.json."""
    payload = json.loads((DATA_DIR / "districts.json").read_text(encoding="utf-8"))
    return payload["districts"]


def devanagari_present(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def latin_present(text: str) -> bool:
    return any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)
