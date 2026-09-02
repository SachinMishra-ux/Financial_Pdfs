#!/bin/bash

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment .venv not found. Please create it first."
    exit 1
fi

echo "Starting S3 Ingestion Worker in unbuffered mode..."
exec .venv/bin/python -u src/embedding_service/s3_worker.py
