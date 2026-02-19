FROM python:3.12-slim

WORKDIR /app

# Install CA certificates and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py cosmos.py schemas.py ./
COPY middleware/ middleware/
COPY routes/ routes/
COPY services/ services/
COPY startup.sh .

EXPOSE 8000

CMD ["hypercorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
