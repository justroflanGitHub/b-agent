#!/bin/bash
set -e

echo "🤖 Browser Agent - Starting"
echo "============================"

# Start virtual display (Xvfb) for headless browser
Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 &
XVFB_PID=$!
sleep 1

# Verify display is running
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "❌ Failed to start Xvfb"
    exit 1
fi
echo "✅ Virtual display ready (DISPLAY=:99)"

export DISPLAY=:99
export PYTHONPATH=/app

MODE="${1:-api}"

case "$MODE" in
    api)
        echo "🌐 Starting API server on port 8080..."
        exec python -m browser_agent.api.app
        ;;
    cli)
        shift
        if [ -z "$1" ]; then
            echo "Usage: docker run <image> cli \"your task description\""
            exit 1
        fi
        echo "🎯 Running task: $*"
        exec python run_agent.py --headless "$@"
        ;;
    test)
        echo "🧪 Running tests..."
        exec python -m pytest tests/ -v --tb=short -x
        ;;
    test-integration)
        echo "🧪 Running integration tests..."
        exec python -m pytest tests/test_integration_use_cases.py -v --tb=short
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: docker run <image> [api|cli|test|test-integration]"
        exit 1
        ;;
esac
