FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration first for caching
COPY pyproject.toml .

# Install dependencies (including torch)
# We install the project in editable mode initially or just the deps
# Pip can install from toml directly if it has [project] table (modern standard)
# But typically we need 'pip install .'
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/
COPY scripts/ scripts/

# Re-install payload (update code without re-installing deps if possible?)
# Since we did 'pip install .' before copying src, it might have failed if src was missing but pyproject needed it?
# Actually 'pip install .' needs the source usually unless we do 'pip install -e .'
# A better pattern is to export requirements or use 'uv' or 'poetry'.
# Given standard pip: COPY . . AND THEN RUN pip install.
# To OPTIMIZE:
# We'll stick to simple COPY . . -> pip install for V1 to ensure correctness first.
# Optimization comes later (Mercenary Check: Correctness > Optimization).

COPY . .
RUN pip install --no-cache-dir .

# Bake embedding model into the image
# This ensures no network calls are needed at runtime for model loading
ENV EMBEDDING_MODEL=BAAI/bge-m3
RUN python scripts/download_model.py

# Set Env Defaults
ENV FALKORDB_HOST=graphdb
ENV FALKORDB_PORT=6379

CMD ["streamlit", "run", "src/dashboard/app.py"]
