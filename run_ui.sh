#!/bin/bash

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "============================================================"
echo "Starting UI Web Server at http://localhost:8080 ..."
echo "Press Ctrl+C to stop the server."
echo "============================================================"

# Serve the static UI files using Python's built-in server
python3 -m http.server 8080 --directory UI
