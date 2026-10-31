"""Run a local teacher workspace: python -m src.ui [--fake]."""

import argparse
import os
import secrets
from threading import Thread
import time
from urllib.parse import quote
import webbrowser

import uvicorn

from src.api.main import create_app


def main():
    parser = argparse.ArgumentParser(description="Local mathematics exam workspace")
    parser.add_argument("--fake", action="store_true", help="Use existing M3 questions without calling Qwen")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Require a configured teacher token; do not open a browser")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    token = os.getenv("API_TEACHER_TOKEN") or os.getenv("FAKE_API_TEACHER_TOKEN")
    if args.no_browser and not token:
        parser.error("Set API_TEACHER_TOKEN when using --no-browser")
    token = token or secrets.token_urlsafe(32)
    # The local MVP launcher opts into experimental wording. Plain API deployments
    # remain strict unless explicitly enabled; an explicit 0 always wins.
    os.environ.setdefault("KORO_EXPERIMENTAL_INDIRECT", "1")
    app = create_app(backend="fake" if args.fake else "qwen", profile_source="m3", teacher_token=token)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port))
    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        def open_workspace():
            for _ in range(150):
                if server.started:
                    # Fragment is not sent to HTTP logs. The UI removes it
                    # immediately and retains the credential only in memory.
                    webbrowser.open(url + "#token=" + quote(token, safe=""))
                    return
                time.sleep(0.1)
        Thread(target=open_workspace, daemon=True).start()
    print(f"Teacher workspace: {url}")
    print("Demo: no Qwen inference." if args.fake else "Generation requires local Ollama with the configured Qwen model.")
    server.run()


if __name__ == "__main__":
    main()
