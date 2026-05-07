#!/bin/sh

# Start OPA server in the background
# It will listen on :8181 and serve policies from the /app/policies folder
opa run --server --addr :8181 /app/policies &

# Start the Temporal Worker
# We use exec so that the Python process receives OS signals (SIGTERM/SIGINT) directly
echo "Starting Temporal Worker and OPA..."
exec python temporal_worker.py