#!/usr/bin/env python
"""Script to run the Phase II backend server."""
import sys
import os
from pathlib import Path

# Get the directory where this script is located
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir

# Add backend directory to Python path
sys.path.insert(0, str(backend_dir))

# Change to backend directory
os.chdir(backend_dir)

# Now run uvicorn
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
