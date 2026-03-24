FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for browser automation
RUN apt-get update && apt-get install -y \
    xvfb \
    libgtk-3-0 \
    libnotify-dev \
    libnss3 \
    libxss1 \
    libasound2 \
    wget \
    curl \
    fonts-liberation \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-browser.txt /tmp/requirements-browser.txt
RUN pip install --no-cache-dir -r /tmp/requirements-browser.txt

# Install additional dependencies for interactive input
RUN pip install --no-cache-dir aiohttp

# Set up virtual display for headless browser operation
ENV DISPLAY=:99
ENV BROWSER_HEADLESS=true

# Install Playwright and browsers
RUN pip install playwright
RUN playwright install chromium

# Create necessary directories
RUN mkdir -p /app/data/screenshots /app/logs /app/models

# Copy application code
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY simple_browser_agent.py /app/simple_browser_agent.py
COPY simple_browser_api.py /app/simple_browser_api.py
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV BROWSER_AGENT_DEBUG=false
ENV BROWSER_AGENT_MOCK_ACTIONS=false

# Set entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
