import os
import sys
import urllib.request
from fastapi import FastAPI, HTTPException, status, UploadFile, File
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Ensure root directory is in the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, '.env'))

from src.embedding_service.embedder import GeminiEmbedder
from src.embedding_service.qdrant_manager import QdrantManager
from src.generation_service.gemini_rag_llm import GeminiRAG
from src.generation_service.validation import QueryRequest, QueryResponse, UploadResponse

from fastapi.middleware.cors import CORSMiddleware

AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "financial-rag-documents-001")

# Initialize FastAPI App
app = FastAPI(
    title="Financial RAG Generation Service",
    description="REST API for answering questions about financial PDFs using Qdrant vector DB and Gemini LLM.",
    version="1.0.0"
)

# Enable CORS for frontend web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global clients
qdrant_manager = None
embedder = None
rag_llm = None

def init_qdrant_manager(collection_name):
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    use_server = False
    try:
        with urllib.request.urlopen(f"{qdrant_url.rstrip('/')}/healthz", timeout=1.0) as response:
            if response.status == 200:
                use_server = True
    except Exception:
        pass
        
    if use_server:
        print(f"Connected to Qdrant Docker server at {qdrant_url}")
        return QdrantManager(url=qdrant_url, collection_name=collection_name)
    else:
        qdrant_path = os.path.join(PROJECT_ROOT, "qdrant_storage")
        print(f"Qdrant Docker server not detected. Using local path: {qdrant_path}")
        return QdrantManager(path=qdrant_path, collection_name=collection_name)

@app.on_event("startup")
def startup_event():
    global qdrant_manager, embedder, rag_llm
    collection_name = os.environ.get("COLLECTION_NAME", "financial_documents")
    print("Initializing clients for generation service...")
    try:
        qdrant_manager = init_qdrant_manager(collection_name)
        embedder = GeminiEmbedder(model_name="gemini-embedding-2")
        rag_llm = GeminiRAG()
        print("All clients successfully initialized.")
    except Exception as e:
        print(f"ERROR: Initialization failed during startup: {e}")
        # Note: We do not fail hard immediately to allow debugging/health checks to run,
        # but queries will fail.



@app.options("/query")
def options_query():
    return {}

@app.post("/query", response_model=QueryResponse, status_code=status.HTTP_200_OK)
def query_rag(request: QueryRequest):
    global qdrant_manager, embedder, rag_llm
    
    if not qdrant_manager or not embedder or not rag_llm:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service clients are not initialized. Check API keys and DB connection."
        )

    # 1. Embed query
    try:
        query_embedding = embedder.embed_text(request.question)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {e}"
        )

    # 2. Retrieve matched pages from Qdrant
    try:
        top_base64_images = qdrant_manager.search(query_embedding, limit=request.limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search Qdrant vector DB: {e}"
        )

    if not top_base64_images:
        return QueryResponse(
            question=request.question,
            answer="No matching document context was found in the database.",
            pages_retrieved=0,
            images=[]
        )

    # 3. Generate answer via Gemini LLM
    try:
        answer = rag_llm.answer_question(request.question, top_base64_images)
        return QueryResponse(
            question=request.question,
            answer=answer,
            pages_retrieved=len(top_base64_images),
            images=top_base64_images
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer from Gemini LLM: {e}"
        )

@app.options("/upload")
def options_upload():
    return {}

@app.post("/upload", response_model=UploadResponse, status_code=status.HTTP_200_OK)
async def upload_document(file: UploadFile = File(...)):
    """Uploads a PDF document to S3, triggering the automatic ingestion pipeline."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported for ingestion."
        )

    try:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        s3_key = os.path.basename(file.filename)
        
        print(f"Uploading {file.filename} to s3://{S3_BUCKET_NAME}/{s3_key}...")
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": "application/pdf"}
        )
        print(f"Successfully uploaded {s3_key} to S3.")

        return UploadResponse(
            status="success",
            filename=file.filename,
            bucket=S3_BUCKET_NAME,
            s3_key=s3_key,
            message=f"Successfully uploaded {file.filename} to s3://{S3_BUCKET_NAME}/{s3_key}. Ingestion has been automatically triggered."
        )
    except ClientError as e:
        print(f"S3 ClientError during upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AWS S3 error: {e}"
        )
    except Exception as e:
        print(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {e}"
        )

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    global qdrant_manager, embedder, rag_llm
    
    qdrant_ok = qdrant_manager is not None
    embedder_ok = embedder is not None
    llm_ok = rag_llm is not None
    
    status_str = "healthy" if (qdrant_ok and embedder_ok and llm_ok) else "degraded"
    
    return {
        "status": status_str,
        "details": {
            "qdrant_connected": qdrant_ok,
            "embedder_initialized": embedder_ok,
            "llm_initialized": llm_ok
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Use reload=False when running directly, or "src.generation_service.app:app" with reload=True for development
    uvicorn.run(app, host="0.0.0.0", port=8000)
