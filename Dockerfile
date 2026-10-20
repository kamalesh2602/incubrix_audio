FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements.txt

# Copy application source code and configuration
COPY app/ app/
COPY tests/ tests/
COPY pytest.ini .
COPY .env.example .
COPY openapi.yaml .
COPY README.md .
COPY SOURCES.md .
COPY AI_USE.md .
COPY scripts/ scripts/

# Create storage directory for audio artifacts
RUN mkdir -p /app/storage

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
