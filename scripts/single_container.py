"""Start the four prototype processes and stop the container if any exits."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path("/workspace")
SECRETS = {
    "DATABASE_URL", "REDIS_URL", "GROQ_API_KEY", "SECRET_KEY",
    "SHELTER_BACKEND_API_KEY", "ADMIN_API_KEY",
}
CHILDREN: list[tuple[str, subprocess.Popen[bytes]]] = []


def service_env(*keys: str, **values: str) -> dict[str, str]:
    """Pass each service only the credentials it actually needs."""
    environment = {key: value for key, value in os.environ.items() if key not in SECRETS}
    environment.update({key: os.environ[key] for key in keys if key in os.environ})
    environment.update(values)
    return environment


def start(name: str, command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    process = subprocess.Popen(command, cwd=cwd, env=environment)
    CHILDREN.append((name, process))
    print(f"Started {name} (pid {process.pid})", flush=True)


def wait_for_port(name: str, port: int, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for child_name, process in CHILDREN:
            if process.poll() is not None:
                raise RuntimeError(f"{child_name} exited during startup ({process.returncode})")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError(f"{name} did not listen on port {port} within {timeout} seconds")


def stop_all(*_args: object) -> None:
    for _, process in CHILDREN:
        if process.poll() is None:
            process.terminate()
    for _, process in CHILDREN:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main() -> int:
    missing = sorted(key for key in SECRETS - {"ADMIN_API_KEY"} if not os.environ.get(key))
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2
    if os.environ["SECRET_KEY"] == "changeme-jwt-secret" or os.environ["SHELTER_BACKEND_API_KEY"] == "changeme-dev-secret":
        print("Replace the development secrets before starting", file=sys.stderr)
        return 2

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    gateway_dir = ROOT / "gateway"
    agent_dir = ROOT / "agent"
    web_dir = ROOT / "web"
    gateway_python = str(gateway_dir / ".venv/bin/python")
    agent_python = str(agent_dir / ".venv/bin/python")
    port = int(os.environ.get("PORT", "10000"))
    if port in {8000, 8001, 9000}:
        print("PORT conflicts with an internal service", file=sys.stderr)
        return 2

    try:
        gateway_env = service_env(
            "DATABASE_URL", "REDIS_URL", "SECRET_KEY", "SHELTER_BACKEND_API_KEY", "ADMIN_API_KEY",
            AGENT_SERVICE_URL="http://127.0.0.1:8000", CORS_ORIGINS="[]",
            ENABLE_DEFERRED_FEATURES="false",
        )
        subprocess.run([gateway_python, "-m", "db.migrate"], cwd=gateway_dir, env=gateway_env, check=True)

        mcp_env = service_env(
            "SHELTER_BACKEND_API_KEY",
            MCP_SERVER_HOST="127.0.0.1", MCP_SERVER_PORT="9000",
            POSTGRES_SERVICE_URL="http://127.0.0.1:8001", ENABLE_DEFERRED_FEATURES="false",
        )
        start("mcp", [agent_python, "-m", "mcp_server.server"], agent_dir, mcp_env)
        wait_for_port("mcp", 9000)

        agent_env = service_env(
            "GROQ_API_KEY", "REDIS_URL", "SHELTER_BACKEND_API_KEY",
            LLM_PROVIDER="groq", SESSION_BACKEND="redis", MCP_TRANSPORT="sse",
            MCP_SERVER_URL="http://127.0.0.1:9000/sse",
            POSTGRES_SERVICE_URL="http://127.0.0.1:8001", ENABLE_DEFERRED_FEATURES="false",
        )
        start("agent", [agent_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], agent_dir, agent_env)
        wait_for_port("agent", 8000)

        start("gateway", [gateway_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"], gateway_dir, gateway_env)
        wait_for_port("gateway", 8001)

        web_env = service_env(NODE_ENV="production", BACKEND_INTERNAL_URL="http://127.0.0.1:8001", NEXT_PUBLIC_USE_SAME_ORIGIN_API="true")
        start("web", ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0", "--port", str(port)], web_dir, web_env)
        wait_for_port("web", port)

        while True:
            for name, process in CHILDREN:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited ({process.returncode})")
            time.sleep(1)
    except (OSError, RuntimeError, TimeoutError, subprocess.CalledProcessError) as exc:
        print(f"Prototype startup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
