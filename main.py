#!/usr/bin/env python3
"""
MindWell Launcher
-----------------
Single command to start the entire stack:
  1. Checks Ollama is running (starts it if not)
  2. Starts Flask backend (port 5001)
  3. Starts React frontend (port 3000)

Usage:
    python main.py
"""

import os
import sys
import signal
import subprocess
import time
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")

OLLAMA_URL = "http://localhost:11434"
BACKEND_PORT = 5001
FRONTEND_PORT = 3000

processes = []


def cleanup(signum=None, frame=None):
    """Kill all child processes on exit."""
    print("\n\nShutting down MindWell...")
    for name, proc in processes:
        if proc.poll() is None:
            print(f"  Stopping {name} (pid {proc.pid})")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("Done.")
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def check_ollama():
    """Verify Ollama is running and the mistral model is available."""
    print("[1/3] Checking Ollama...")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        has_mistral = any("mistral" in m for m in models)
        if has_mistral:
            print("       Ollama is running, mistral model found.")
            return
        else:
            print(f"       Ollama is running but mistral not found. Available: {models}")
            print("       Run: ollama pull mistral")
            sys.exit(1)
    except requests.ConnectionError:
        print("       Ollama is not running. Attempting to start...")
        proc = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(("Ollama", proc))
        # Wait for it to come up
        for i in range(15):
            time.sleep(1)
            try:
                requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
                print("       Ollama started successfully.")
                return
            except requests.ConnectionError:
                pass
        print("       ERROR: Could not start Ollama. Install it from https://ollama.com")
        sys.exit(1)


def start_backend():
    """Start the Flask backend."""
    print(f"[2/3] Starting backend on port {BACKEND_PORT}...")
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(("Backend", proc))

    # Wait for it to be ready
    for i in range(20):
        time.sleep(1)
        try:
            resp = requests.get(f"http://localhost:{BACKEND_PORT}/therapists", timeout=2)
            if resp.status_code == 200:
                print(f"       Backend ready at http://localhost:{BACKEND_PORT}")
                return
        except requests.ConnectionError:
            pass

    # Show any startup errors
    print("       WARNING: Backend may not be fully ready. Check logs.")


def start_frontend():
    """Start the React dev server."""
    print(f"[3/3] Starting frontend on port {FRONTEND_PORT}...")
    env = os.environ.copy()
    env["PORT"] = str(FRONTEND_PORT)
    env["BROWSER"] = "none"  # Don't auto-open browser
    env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"

    proc = subprocess.Popen(
        ["npx", "react-scripts", "start"],
        cwd=FRONTEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(("Frontend", proc))

    # Wait for it to compile
    for i in range(60):
        time.sleep(1)
        try:
            resp = requests.get(f"http://localhost:{FRONTEND_PORT}", timeout=2)
            if resp.status_code == 200:
                print(f"       Frontend ready at http://localhost:{FRONTEND_PORT}")
                return
        except requests.ConnectionError:
            pass

    print(f"       Frontend starting (may take a moment)... http://localhost:{FRONTEND_PORT}")


def main():
    print("=" * 50)
    print("  MindWell - Mental Health Assistant")
    print("=" * 50)
    print()

    check_ollama()
    start_backend()
    start_frontend()

    print()
    print("=" * 50)
    print(f"  App running!")
    print(f"  Frontend : http://localhost:{FRONTEND_PORT}")
    print(f"  Backend  : http://localhost:{BACKEND_PORT}")
    print(f"  Ollama   : {OLLAMA_URL}")
    print()
    print("  Press Ctrl+C to stop everything.")
    print("=" * 50)

    # Keep alive and forward output
    try:
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n  WARNING: {name} exited with code {proc.returncode}")
                    processes.remove((name, proc))
            if not processes:
                print("\n  All processes exited.")
                break
            time.sleep(2)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
