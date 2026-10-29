#!/usr/bin/env python3
"""TerraQuest launcher (Linux, macOS, Windows): starts the local game server and opens your browser."""

import argparse
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if sys.version_info < (3, 11):
    sys.exit(f"❌ Python 3.11 or newer is required (found {sys.version.split()[0]}).")


def port_in_use(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_when_ready(url, port):
    for _ in range(100):
        if port_in_use(port):
            webbrowser.open(url)
            return
        time.sleep(0.1)


def main():
    ap = argparse.ArgumentParser(description="TerraQuest: learn Terraform Associate (004) as a game")
    ap.add_argument("-p", "--port", type=int, default=8080, help="port to listen on (default 8080)")
    ap.add_argument("--host", default="127.0.0.1", help="address to bind (default 127.0.0.1)")
    ap.add_argument("--no-browser", action="store_true", help="don't open the browser automatically")
    ap.add_argument("--check", action="store_true", help="validate content files and exit")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / "server"))
    import app  # noqa: E402  (imported after the version check above)

    if args.check:
        sys.argv = ["app.py", "--check-content"]
        return app.main()

    if shutil.which("terraform"):
        version = subprocess.run(["terraform", "version"], capture_output=True, text=True).stdout.splitlines()
        print(f"✅ {version[0] if version else 'terraform'} found: hands-on labs are available.")
    else:
        print("⚠️  terraform not found on PATH. Quizzes work, but labs need it.")
        print("    Install: https://developer.hashicorp.com/terraform/install")

    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}"
    if port_in_use(args.port):
        sys.exit(f"❌ Port {args.port} is already in use. Is TerraQuest already running? Open {url}, or use --port 8081")

    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url, args.port), daemon=True).start()

    sys.argv = ["app.py", "--host", args.host, "--port", str(args.port)]
    app.main()


if __name__ == "__main__":
    main()
