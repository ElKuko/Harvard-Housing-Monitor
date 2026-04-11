#!/bin/bash
# Harvard Housing Monitor – cron wrapper
# Ensures correct working directory, virtualenv, and log output.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create logs dir if it doesn't exist yet
mkdir -p logs data

# Activate virtualenv if present (adjust path if yours differs)
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run the monitor (single run – scheduling handled by cron)
python main.py >> logs/cron.log 2>&1
