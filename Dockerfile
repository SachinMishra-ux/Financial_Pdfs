FROM python:3.12-slim

# Copy the uv binary from the official Astral uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from cache instead of linking
ENV UV_LINK_MODE=copy

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and uv.lock configuration files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv.
# We mount the uv cache directory as a cache mount to speed up subsequent builds.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application source code
COPY src/ ./src

# Expose FastAPI application port
EXPOSE 8000

# Set default runtime environment variables
ENV PYTHONUNBUFFERED=1
ENV QDRANT_URL=http://qdrant:6333
ENV COLLECTION_NAME=financial_documents

# Ensure the virtualenv created by uv is on the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run the FastAPI server using uvicorn (which is installed inside the virtual environment)
CMD ["uvicorn", "src.generation_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
