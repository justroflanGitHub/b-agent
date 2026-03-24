#!/bin/bash

echo "🚀 Starting Simple Browser Agent Docker Container"
echo "=================================================="

# Set up virtual display for headless browser operation
export DISPLAY=:99
echo "Setting up virtual display..."
Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 &

# Wait for Xvfb to start
sleep 2
echo "✅ Virtual display ready"

# Ensure Playwright browsers are available
echo "Checking Playwright browsers..."
if ! playwright install --dry-run chromium >/dev/null 2>&1; then
    echo "Installing Playwright browsers..."
    playwright install chromium
    echo "✅ Playwright browsers installed"
else
    echo "✅ Playwright browsers already available"
fi

# Change to app directory
cd /app

# Determine run mode
if [ "$1" = "api" ]; then
    echo "🌐 Starting API server mode..."
    python simple_browser_api.py
elif [ "$1" = "test" ]; then
    echo "🧪 Starting test mode..."
    # For test mode, we can pass a search query via environment variable
    if [ -n "$SEARCH_QUERY" ]; then
        echo "🔍 Using search query from environment: '$SEARCH_QUERY'"
        python -c "
import asyncio
from simple_browser_agent import execute_browser_task

async def run_test():
    result = await execute_browser_task('$SEARCH_QUERY', 'https://www.google.com')
    print('Test completed:', result)

asyncio.run(run_test())
"
    else
        echo "❌ SEARCH_QUERY environment variable not set for test mode"
        echo "Usage: docker run -e SEARCH_QUERY='your search query' <image> test"
        exit 1
    fi
else
    echo "🤖 Starting interactive mode..."
    echo ""
    echo "Simple Browser Agent - Docker Interactive Mode"
    echo "=============================================="
    echo ""
    echo "This mode allows you to enter search queries interactively."
    echo "However, Docker containers may not support interactive input by default."
    echo ""
    echo "For interactive usage, consider:"
    echo "1. Using API mode: docker run -p 8080:8080 <image> api"
    echo "2. Using test mode: docker run -e SEARCH_QUERY='your query' <image> test"
    echo ""
    echo "Starting API server instead for web access..."
    python simple_browser_api.py
fi
