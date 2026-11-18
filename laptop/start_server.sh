#!/usr/bin/env bash
# Start the AI restyle engine so the PWA can call it over the network.
cd "$(dirname "$0")"
source venv/bin/activate
HOST="${1:-0.0.0.0}"
PORT="${2:-8002}"
DTYPE="${3:-float32}"
echo "AI Restyle engine: http://$HOST:$PORT  (dtype=$DTYPE)"
exec python restyle.py --serve --host "$HOST" --port "$PORT" --dtype "$DTYPE"
