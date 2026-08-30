import os
import sys
import argparse
import urllib.request
from dotenv import load_dotenv

# Ensure root directory is in the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, '.env'))

from src.embedding_service.embedder import GeminiEmbedder
from src.embedding_service.qdrant_manager import QdrantManager
from src.generation_service.gemini_rag_llm import GeminiRAG

def parse_args():
    parser = argparse.ArgumentParser(description="Query the Financial RAG pipeline.")
    parser.add_argument("question", type=str, help="The question you want to ask about the financial data.")
    parser.add_argument("--limit", type=int, default=3, help="Number of context pages (images) to retrieve from Qdrant.")
    return parser.parse_args()

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

def main():
    args = parse_args()
    
    # Configuration from environment variables
    collection_name = os.environ.get("COLLECTION_NAME", "financial_documents")
    
    print("=" * 60)
    print("Executing Financial RAG Query...")
    print(f"Question: '{args.question}'")
    print(f"Collection: '{collection_name}'")
    print("=" * 60)

    # 1. Initialize Clients
    try:
        qdrant_manager = init_qdrant_manager(collection_name)
        embedder = GeminiEmbedder(model_name="gemini-embedding-2")
        rag_llm = GeminiRAG()
    except Exception as e:
        print(f"Initialization error: {e}")
        sys.exit(1)

    # 2. Embed Query
    try:
        print("Embedding question...")
        query_embedding = embedder.embed_text(args.question)
    except Exception as e:
        print(f"Failed to generate query embedding: {e}")
        sys.exit(1)

    # 3. Retrieve Context from Qdrant
    try:
        print(f"Retrieving top {args.limit} matching pages from Qdrant...")
        top_base64_images = qdrant_manager.search(query_embedding, limit=args.limit)
        
        if not top_base64_images:
            print("No matching document pages found in vector DB.")
            sys.exit(0)
            
        print(f"Successfully retrieved {len(top_base64_images)} context page(s).")
    except Exception as e:
        print(f"Failed to search Qdrant: {e}")
        sys.exit(1)

    # 4. Generate Answer via Gemini LLM
    try:
        print("Submitting question and context pages to Gemini LLM...")
        answer = rag_llm.answer_question(args.question, top_base64_images)
        print("\n" + "=" * 60)
        print("Answer:")
        print(answer)
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"Failed to generate answer from LLM: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
