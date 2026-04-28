FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (for Reflex and Playwright/Node if needed)
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    build-essential \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . /app

# Expose the Hugging Face Spaces default port
EXPOSE 7860

# Run Reflex app in production mode with single port configuration
CMD reflex run --env prod --backend-port 7860
