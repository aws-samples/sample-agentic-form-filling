FROM --platform=linux/arm64 python:3.11-slim-bookworm

# Install system dependencies (cached unless OS packages change)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libgtk-3-0 \
    libx11-xcb1 libxcb-dri3-0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright globally (cached, ~300MB download, no project deps)
RUN pip install --no-cache-dir playwright && \
    playwright install chromium

WORKDIR /app

# Copy only dependency definitions (cached unless dependencies change)
COPY pyproject.toml ./

# Install Python dependencies (cached unless pyproject.toml changes)
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir aws-opentelemetry-distro>=0.10.1

# Copy source code (invalidates cache on code changes, but deps already installed)
COPY src/ ./src/

# Environment for container
ENV STRANDS_BROWSER_HEADLESS=true
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "src/agentcore_server.py"]
