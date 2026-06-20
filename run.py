"""
One-command launcher for the Migration Agent.

Usage:
    python run.py

This script:
  1. Checks Python version (>= 3.11 required)
  2. Installs dependencies from backend/requirements.txt
  3. Starts the FastAPI app, using the next free port if 8000 is busy
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 11)
DEFAULT_PORT = 8000


def check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        print(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required. You have {sys.version}")
        sys.exit(1)
    print(f"Python {sys.version.split()[0]}")


def install_dependencies() -> None:
    req_file = Path(__file__).parent / "backend" / "requirements.txt"
    if not req_file.exists():
        print("requirements.txt not found; skipping dependency install")
        return

    print("Installing dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
        capture_output=False,
    )
    if result.returncode != 0:
        print("Dependency installation failed. Run manually:")
        print(f"   pip install -r {req_file}")
        sys.exit(1)
    print("Dependencies ready")


def is_port_available(port: int) -> bool:
    """Return True when localhost can bind the requested port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def choose_port(preferred_port: int = DEFAULT_PORT) -> int:
    """Use the preferred port, or the next available port nearby."""
    if is_port_available(preferred_port):
        return preferred_port

    for port in range(preferred_port + 1, preferred_port + 50):
        if is_port_available(port):
            print(f"Port {preferred_port} is already in use. Using port {port} instead.")
            return port

    print(f"No available port found from {preferred_port} to {preferred_port + 49}.")
    sys.exit(1)


def start_server() -> None:
    os.chdir(Path(__file__).parent)
    port = choose_port(int(os.environ.get("PORT", DEFAULT_PORT)))
    url = f"http://localhost:{port}"

    print("\n" + "=" * 60)
    print("  .NET to Java Migration Agent")
    print(f"  Frontend: {url}")
    print(f"  API Docs: {url}/docs")
    print("  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--reload",
            "--reload-dir",
            "backend",
        ],
        check=False,
    )


if __name__ == "__main__":
    check_python()
    install_dependencies()
    start_server()
