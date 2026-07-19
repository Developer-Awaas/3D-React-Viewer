# Drishti API - vector-only production image (slim, no torch).
# Build from the server/ directory:  docker build -t drishti-api .
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# opencv-headless runtime needs libglib on slim images
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# LibreDWG's dwg2dxf enables direct .dwg uploads (DXF's closed binary twin).
# BEST-EFFORT: if the build fails the image still ships - DWG uploads then get
# a friendly "export DXF instead" message (cad_vector.DWG_HELP). No deploy risk.
RUN (apt-get update \
     && apt-get install -y --no-install-recommends build-essential curl xz-utils \
     && curl -fsSL -o /tmp/libredwg.tar.xz \
        https://ftp.gnu.org/gnu/libredwg/libredwg-0.13.3.tar.xz \
     && tar -xJf /tmp/libredwg.tar.xz -C /tmp \
     && cd /tmp/libredwg-* \
     && ./configure --disable-bindings --disable-docs --prefix=/usr/local \
     && make -j"$(nproc)" && make install && ldconfig \
     && cd / && rm -rf /tmp/libredwg* \
     && apt-get purge -y build-essential && apt-get autoremove -y \
     && rm -rf /var/lib/apt/lists/* \
     && dwg2dxf --version) \
    || echo "WARNING: libredwg build skipped - DWG uploads will ask for DXF"

COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

# Render/Railway inject PORT; default 8000 for local runs
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
