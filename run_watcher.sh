#!/bin/bash

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment .venv not found. Please create it first."
    exit 1
fi

# Run the watcher script using the virtual environment python
echo "Starting watcher service using virtual environment..."
exec .venv/bin/python -u watcher.py
