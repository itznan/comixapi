#!/usr/bin/env python3
"""
ComixAPI - CLI and FastAPI entry point.
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--server", "server", "-s"):
        import uvicorn
        port = 8000
        for i, arg in enumerate(sys.argv):
            if arg in ("--port", "-p") and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    pass
        print(f"Starting ComixAPI server on http://localhost:{port} (docs: http://localhost:{port}/docs)")
        uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=True)
    else:
        from comix_downloader import main
        main()
