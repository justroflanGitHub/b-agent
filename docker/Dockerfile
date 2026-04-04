FROM python:3.11-slim AS base

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libgtk-3-0 \
    libnotify-dev \
    libnss3 \
    libxss1 \
    libasound2 \
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
    fonts-liberation \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Playwright and Chromium
RUN pip install --no-cache-dir playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# Create directories
RUN mkdir -p /app/data /app/logs /app/checkpoints /app/screenshots

# ---- Development stage ----
FROM base AS development

# Install dev dependencies
RUN pip install --no-cache-dir pytest pytest-asyncio black flake8 mypy

# Copy source
COPY . /app

# Set up virtual display
ENV DISPLAY=:99
ENV BROWSER_HEADLESS=true

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["api"]

# ---- Production stage ----
FROM base AS production

# Copy only necessary files
COPY browser_agent/ /app/browser_agent/
COPY run_agent.py /app/run_agent.py
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set up virtual display
ENV DISPLAY=:99
ENV BROWSER_HEADLESS=true
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
