#!/usr/bin/env python
import uvicorn
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    # Get port from environment variable (required for Render, Fly.io, etc.)
    port = int(os.getenv("PORT", 8001))

    uvicorn.run(
        "main:app", host="0.0.0.0", port=port, log_level="info", access_log=True
    )
