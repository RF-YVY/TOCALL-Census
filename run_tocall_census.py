from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
import webbrowser

import uvicorn


def configure_windows_event_loop() -> None:
    if sys.platform != "win32":
        return
    with contextlib.suppress(AttributeError):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    configure_windows_event_loop()
    from app.main import app

    parser = argparse.ArgumentParser(description="Run TOCALL Census")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", default=14502, type=int, help="Web server port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser on startup")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser and os.environ.get("TOCALL_CENSUS_NO_BROWSER") != "1":
        webbrowser.open(url)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
