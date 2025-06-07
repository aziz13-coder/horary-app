#!/bin/bash

# Render start script
echo "Starting Horary Astrology API on port $PORT"

# Install dependencies if not cached
if [ ! -d "/opt/render/project/.venv" ]; then
    echo "Installing dependencies..."
    pip install -r horary77-main/horary4/backend/requirements.txt
fi

# Start the application
exec gunicorn horary77-main.horary4.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -