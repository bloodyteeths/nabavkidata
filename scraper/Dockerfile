# Multi-stage build for Scrapy scraper
# Stage 1: Builder
FROM python:3.11-slim as builder

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install build dependencies and Playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    python3-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Stage 2: Runtime
FROM python:3.11-slim

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    curl \
    wget \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR $APP_HOME

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /ms-playwright /ms-playwright

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/pdfs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command: run scheduler
CMD ["python", "scheduler.py", "run", "--incremental"]
