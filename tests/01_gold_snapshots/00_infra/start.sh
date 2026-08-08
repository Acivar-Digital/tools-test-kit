#!/usr/bin/env bash
set -euo pipefail

# Define variables
SESSION_NAME="bazi-infra"
PROD_PORT=8445
DOCKER_COMPOSE_FILE="infrastructure/docker/docker-compose.yml"

echo "=== BaziForecaster Infra Manager ==="

# 1. Clean up any existing tmux session to avoid conflicts
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Killing existing tmux session: $SESSION_NAME..."
    tmux kill-session -t "$SESSION_NAME"
fi

# 2. Check and clean ports
clean_port() {
    local port=$1
    local pid
    pid=$(lsof -t -i:"$port" || true)
    if [ -n "$pid" ]; then
        echo "Port $port is occupied by PID $pid. Killing process..."
        kill -9 "$pid" || true
    fi
}
echo "Ensuring ports are clear..."
clean_port "$PROD_PORT"

# 3. Check and start Docker containers
echo "Verifying Docker services..."
if ! docker compose -f "$DOCKER_COMPOSE_FILE" up -d; then
    echo "🚨 ERROR: Docker services failed to start! Failing loudly." >&2
    exit 1
fi

# Wait for database healthcheck (basic check)
echo "Checking Docker container status..."
if ! docker compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "Up"; then
    echo "🚨 ERROR: Docker containers are not in 'Up' status! Failing loudly." >&2
    exit 1
fi

# 4. Start Tmux Session (single production server; Gold E2E hits /webhook/test on same instance)
echo "Creating tmux session: $SESSION_NAME..."
tmux new-session -d -s "$SESSION_NAME" -n "services" "uv run start2.py --skip-preflight"

# Enable mouse mode for easy scrolling
tmux set-option -g -t "$SESSION_NAME" mouse on

# Auto-teardown cleanup function
cleanup() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo -e "\nShutting down tmux session $SESSION_NAME..."
        tmux kill-session -t "$SESSION_NAME"
        # Make sure ports are cleared
        clean_port "$PROD_PORT"
    fi
}

# Trap signals to clean up
trap cleanup INT TERM

# Attach to the tmux session to let the user view logs.
# Detaching (Ctrl-B d) must NOT kill the server — only INT/TERM (the trap) does.
echo "Attaching to tmux session..."
if tmux attach-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Detached. Server is still running in session $SESSION_NAME."
    echo "To stop the servers, run: tmux kill-session -t $SESSION_NAME"
else
    echo "Running in background (non-interactive shell)."
    echo "To view logs, run: tmux attach -t $SESSION_NAME"
    echo "To stop the servers, run: tmux kill-session -t $SESSION_NAME"
fi
