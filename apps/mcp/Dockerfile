FROM python:3.12-slim

WORKDIR /app

# Install CA certificates and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py schemas.py legacy_tools.py ./
COPY services/ services/
COPY middleware/ middleware/
COPY startup.sh .

EXPOSE 8100

CMD ["hypercorn", "app:app", "--bind", "0.0.0.0:8100", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
