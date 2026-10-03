#!/usr/bin/env python3
"""
ComixAPI - Production FastAPI REST service for Comix.to.
"""
import os
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    print(f"Starting ComixAPI server on http://{host}:{port} (docs: http://{host}:{port}/docs)")
    uvicorn.run("src.server:app", host=host, port=port, reload=True)
