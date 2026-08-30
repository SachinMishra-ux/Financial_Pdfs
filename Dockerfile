FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy embedding service requirements file
COPY src/embedding_service/requirements.txt ./requirements.txt

# Install python packages
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi uvicorn pydantic python-dotenv

# Copy application source code
COPY src/ ./src

# Expose FastAPI application port
EXPOSE 8000

# Set default runtime environment variables
ENV PYTHONUNBUFFERED=1
ENV QDRANT_URL=http://qdrant:6333
ENV COLLECTION_NAME=financial_documents

# Run the FastAPI server using uvicorn
CMD ["uvicorn", "src.generation_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
