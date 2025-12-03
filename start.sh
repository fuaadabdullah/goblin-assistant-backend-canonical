#!/bin/bash
# Startup script for GoblinOS Assistant Backend
# This ensures proper Python path setup for package imports

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Resolve venv Python (one level up from backend/)
VENV_PY="$(cd .. && pwd)/venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
	echo "❌ Could not find virtualenv python at $VENV_PY"
	echo "Please create/activate the venv first: python3 -m venv ../venv && ../venv/bin/pip install -r ../requirements.txt"
	exit 1
fi

# Set PYTHONPATH to include the backend directory
export PYTHONPATH="${PWD}:${PYTHONPATH}"

echo "✅ Using interpreter: $VENV_PY"
echo "✅ PYTHONPATH: $PYTHONPATH"

# Start uvicorn with proper module path
exec "$VENV_PY" -m uvicorn main:app --reload --host 127.0.0.1 --port 8001

