import os
import sys
import time
import json
import urllib.request
from dotenv import load_dotenv

# Ensure the root project path is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, 'src', '.env'))

from src.embedding_service.document_processor import pdf_to_images, image_to_base64
from src.embedding_service.embedder import GeminiEmbedder
from src.embedding_service.qdrant_manager import QdrantManager

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
STATE_FILE = os.path.join(DATA_DIR, ".processed_files.json")
COLLECTION_NAME = "financial_documents"
QDRANT_URL = "http://localhost:6333"

def load_processed_state():
    """Loads the dictionary of processed files from the local state file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read processed state file, starting fresh: {e}")
    return {}

def save_processed_state(state):
    """Saves the dictionary of processed files to the local state file."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"Error: Could not save processed state file: {e}")

def init_qdrant_manager():
    """Initializes and returns a QdrantManager, connecting to Docker if available."""
    use_server = False
    try:
        with urllib.request.urlopen(f"{QDRANT_URL.rstrip('/')}/healthz", timeout=1.0) as response:
            if response.status == 200:
                use_server = True
    except Exception:
        pass
        
    if use_server:
        print(f"Connecting to Qdrant Docker server at {QDRANT_URL}...")
        return QdrantManager(url=QDRANT_URL, collection_name=COLLECTION_NAME)
    else:
        qdrant_path = os.path.join(PROJECT_ROOT, "qdrant_storage")
        print(f"Qdrant Docker server not detected. Falling back to local persistent path: {qdrant_path}")
        return QdrantManager(path=qdrant_path, collection_name=COLLECTION_NAME)

def ingest_pdf(pdf_path, qdrant_manager, embedder):
    """Converts a PDF to images, generates Gemini embeddings, and saves to Qdrant."""
    filename = os.path.basename(pdf_path)
    try:
        print(f"\n--- Ingesting {filename} ---")
        # 1. Convert PDF to images
        images = pdf_to_images(pdf_path)
        if not images:
            print(f"No pages found or error converting PDF: {pdf_path}")
            return False
            
        base64_images = [image_to_base64(img) for img in images]
        
        # 2. Embed the images using Gemini
        image_embeddings = []
        for idx, img in enumerate(images):
            print(f"Embedding page {idx + 1}/{len(images)}...")
            emb = embedder.embed_image(img)
            image_embeddings.append(emb)
            
        vector_size = len(image_embeddings[0]) if image_embeddings else 768
        
        # 3. Store in Qdrant
        qdrant_manager.ensure_collection(vector_size=vector_size)
        qdrant_manager.insert_image_embeddings(image_embeddings, base64_images)
        print(f"Successfully ingested {filename} into Qdrant collection '{COLLECTION_NAME}'")
        return True
    except Exception as e:
        print(f"Error during ingestion of {filename}: {e}")
        return False

def check_and_process_folder(qdrant_manager, embedder):
    """Scans the data directory and processes any new or updated PDF files."""
    if not os.path.exists(DATA_DIR):
        print(f"Creating data directory: {DATA_DIR}")
        os.makedirs(DATA_DIR, exist_ok=True)
        return

    processed_state = load_processed_state()
    state_changed = False

    # Get all PDF files in the data directory
    pdf_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".pdf")]
    
    for filename in pdf_files:
        pdf_path = os.path.join(DATA_DIR, filename)
        
        # Gather file stats for change detection
        stat = os.stat(pdf_path)
        mtime = stat.st_mtime
        size = stat.st_size
        
        # Check if we should process the file (not processed, or file changed)
        should_process = True
        if filename in processed_state:
            old_mtime = processed_state[filename].get("mtime")
            old_size = processed_state[filename].get("size")
            if old_mtime == mtime and old_size == size:
                should_process = False

        if should_process:
            print(f"New or modified PDF detected: {filename}")
            success = ingest_pdf(pdf_path, qdrant_manager, embedder)
            if success:
                processed_state[filename] = {
                    "mtime": mtime,
                    "size": size,
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                state_changed = True

    if state_changed:
        save_processed_state(processed_state)

def main():
    print("=" * 60)
    print("Starting PDF Ingestion Watcher Service...")
    print(f"Watching directory: {DATA_DIR}")
    print(f"Using collection: {COLLECTION_NAME}")
    print("=" * 60)

    # Verify Gemini API Key configuration
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\nERROR: GEMINI_API_KEY environment variable is not set.")
        print("Please configure it in a .env file at the project root or export it in your shell environment.")
        sys.exit(1)

    try:
        qdrant_manager = init_qdrant_manager()
        embedder = GeminiEmbedder(model_name="gemini-embedding-2")
    except Exception as e:
        print(f"\nFailed to initialize embedding or database client: {e}")
        sys.exit(1)

    print("\nInitialization complete. Running initial folder scan...")
    check_and_process_folder(qdrant_manager, embedder)
    print("\nInitial scan complete. Watcher is now active. Monitoring for updates...")

    # Main watching loop
    try:
        while True:
            time.sleep(5)
            check_and_process_folder(qdrant_manager, embedder)
    except KeyboardInterrupt:
        print("\nWatcher service stopped by user.")
    except Exception as e:
        print(f"\nWatcher service stopped due to an error: {e}")

if __name__ == "__main__":
    main()
