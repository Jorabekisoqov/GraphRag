# Multi-stage build for GraphRAG application
FROM python:3.10-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
COPY constraints-langchain.txt .
RUN pip install --no-cache-dir --user -r requirements.txt -c constraints-langchain.txt

# Runtime stage
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY .env.example .env.example

# Make sure scripts are executable
RUN chmod +x src/bot/telegram_bot.py || true

# Add local bin to PATH
ENV PATH=/root/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "src.bot.telegram_bot"]
