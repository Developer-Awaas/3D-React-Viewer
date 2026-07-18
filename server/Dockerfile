# Drishti API - vector-only production image (slim, no torch).
# Build from the server/ directory:  docker build -t drishti-api .
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# opencv-headless runtime needs libglib on slim images
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

# Render/Railway inject PORT; default 8000 for local runs
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
