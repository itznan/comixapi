FROM python:3.11-slim

WORKDIR /app

# Install system dependencies: Node.js (for token signing), curl (for healthcheck), and optional aria2 accelerator
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    curl \
    aria2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/
COPY comix_signer.js .
COPY main.py .

# Create downloads volume mount point
RUN mkdir -p /app/downloads

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
