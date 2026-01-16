FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration first for caching
COPY pyproject.toml .

# Install dependencies ONLY (using a dummy file or just installing the project deps if possible)
# We use a trick: Install dependencies by creating a dummy src layout if needed,
# or just run pip install -e . --no-deps to get metadata if possible?
# Better: generic install of pyproject dependencies.
# IMPORTANT: Since we don't have a requirements.txt, we let pip solve it.
# To allow caching, we copy ONLY the toml, then install deps.
# But `pip install .` needs source.
# Solution:
# 1. Create a requirements.txt export (best practice but extra step).
# 2. Or: Just rely on pyproject.toml if we can.
# Let's try installing just the runtime dependencies manually or via a generated requirements step.
# For now, simpler fix: Move COPY . . AFTER the heavy lifting if possible.
# Actually, the simplest fix for users is to NOT trigger --build every time.

# IMPROVED LAYERING:
# 1. Copy config
COPY pyproject.toml README.md ./

# 2. Generate requirements from pyproject.toml (hacky but works without extra tools)
# or just install the heavy hitters explicitly to cache them.
RUN pip install --no-cache-dir torch==2.9.1 sentence-transformers qdrant-client redis neo4j pandas fastapi uvicorn httpx

# 3. Model Caching Layer (Isolate this!)
# Copy ONLY the download script first so this layer is cached unless the script changes
COPY scripts/download_model.py scripts/download_model.py
ENV EMBEDDING_MODEL=BAAI/bge-m3
RUN python scripts/download_model.py

# 4. Now copy source and install the rest (project itself)
COPY . .
RUN pip install --no-cache-dir .

# Set Env Defaults
ENV FALKORDB_HOST=graphdb
ENV FALKORDB_PORT=6379

CMD ["streamlit", "run", "src/dashboard/app.py"]
