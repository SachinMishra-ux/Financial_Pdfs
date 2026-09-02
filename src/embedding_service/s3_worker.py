import os
import sys
import json
import time
import signal
import tempfile
import urllib.parse
import urllib.request
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Ensure root directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, 'src', '.env'))

from src.embedding_service.document_processor import iter_pdf_pages, image_to_base64, get_pdf_page_count
from src.embedding_service.embedder import GeminiEmbedder
from src.embedding_service.qdrant_manager import QdrantManager

AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "financial_documents")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

running = True

def handle_exit(signum, frame):
    global running
    print("\nReceived termination signal. Shutting down S3 worker gracefully...")
    running = False

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

def init_qdrant_manager():
    """Initializes and returns a QdrantManager instance."""
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
        print(f"Qdrant server not detected at {QDRANT_URL}. Falling back to local persistent path: {qdrant_path}")
        return QdrantManager(path=qdrant_path, collection_name=COLLECTION_NAME)

def ingest_pdf_file(pdf_path, filename, qdrant_manager, embedder, batch_size=5):
    """Converts a local PDF file page-by-page, generates Gemini embeddings, and batches upserts into Qdrant."""
    try:
        print(f"\n--- Ingesting {filename} ---")
        total_pages = get_pdf_page_count(pdf_path)
        if total_pages == 0:
            print(f"No pages found or empty PDF: {filename}")
            return False

        print(f"Streaming {filename} page-by-page (Total pages: {total_pages})...")
        batch_embeddings = []
        batch_images = []
        processed_count = 0

        for page_num, total, page_img in iter_pdf_pages(pdf_path):
            print(f"Embedding page {page_num}/{total}...")
            b64_str = image_to_base64(page_img)
            emb = embedder.embed_image(page_img)

            batch_embeddings.append(emb)
            batch_images.append(b64_str)
            processed_count += 1

            if len(batch_embeddings) >= batch_size or page_num == total:
                vector_size = len(batch_embeddings[0]) if batch_embeddings else 3072
                qdrant_manager.ensure_collection(vector_size=vector_size)
                qdrant_manager.insert_image_embeddings(batch_embeddings, batch_images)
                print(f"✅ Upserted {len(batch_embeddings)} pages to Qdrant (Progress: {page_num}/{total})")
                batch_embeddings = []
                batch_images = []

        print(f"🎉 Successfully completed ingestion for {filename} ({processed_count} pages) into Qdrant collection '{COLLECTION_NAME}'")
        return True
    except Exception as e:
        print(f"Error during ingestion of {filename}: {e}")
        return False

def process_message(message_body, s3_client, qdrant_manager, embedder):
    """Parses an S3 event message and ingests any referenced PDF objects."""
    try:
        data = json.loads(message_body)
    except Exception as e:
        print(f"Error parsing SQS message JSON: {e}")
        return True  # Acknowledge unparseable messages to remove them from queue

    # Handle S3 test event
    if "Event" in data and data["Event"] == "s3:TestEvent":
        print("Received S3 Test Event. Connection verified.")
        return True

    records = data.get("Records", [])
    if not records:
        print("Message contains no S3 records. Skipping.")
        return True

    success = True
    for record in records:
        event_name = record.get("eventName", "")
        if not event_name.startswith("ObjectCreated:"):
            print(f"Ignoring non-creation event: {event_name}")
            continue

        s3_info = record.get("s3", {})
        bucket_name = s3_info.get("bucket", {}).get("name")
        raw_key = s3_info.get("object", {}).get("key", "")
        object_key = urllib.parse.unquote_plus(raw_key)

        if not object_key.lower().endswith(".pdf"):
            print(f"Ignoring non-PDF file: {object_key}")
            continue

        print(f"\n[Event: {event_name}] New PDF detected in S3: s3://{bucket_name}/{object_key}")
        
        # Download object to a temporary file
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(tmp_fd)
        try:
            print(f"Downloading s3://{bucket_name}/{object_key}...")
            s3_client.download_file(bucket_name, object_key, tmp_path)
            print(f"Downloaded to {tmp_path}")
            
            ingested = ingest_pdf_file(tmp_path, object_key, qdrant_manager, embedder)
            if not ingested:
                success = False
        except Exception as e:
            print(f"Error downloading or processing s3://{bucket_name}/{object_key}: {e}")
            success = False
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return success

def start_worker():
    """Main worker loop that long-polls SQS for S3 event notifications."""
    if not SQS_QUEUE_URL:
        print("ERROR: SQS_QUEUE_URL environment variable is not set. Exiting.")
        sys.exit(1)

    print("=" * 60)
    print("🚀 Starting S3 Ingestion Worker Daemon")
    print(f"  AWS Region:   {AWS_REGION}")
    print(f"  SQS Queue:    {SQS_QUEUE_URL}")
    print(f"  Qdrant URL:   {QDRANT_URL}")
    print(f"  Collection:   {COLLECTION_NAME}")
    print("=" * 60)

    # Initialize clients
    sqs_client = boto3.client("sqs", region_name=AWS_REGION)
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    qdrant_manager = init_qdrant_manager()
    embedder = GeminiEmbedder(model_name="gemini-embedding-2")

    print("\nWaiting for S3 upload events (long-polling SQS 20s)... Press Ctrl+C to stop.")
    while running:
        try:
            response = sqs_client.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=900
            )

            messages = response.get("Messages", [])
            if not messages:
                continue

            for message in messages:
                receipt_handle = message["ReceiptHandle"]
                body = message["Body"]

                print("\n📨 Received message from SQS.")
                processed_ok = process_message(body, s3_client, qdrant_manager, embedder)

                if processed_ok:
                    sqs_client.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=receipt_handle
                    )
                    print("✅ SQS message successfully processed and removed from queue.")
                else:
                    print("⚠️ Ingestion had errors. Message left in queue for retry.")

        except ClientError as e:
            print(f"AWS ClientError: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error in worker loop: {e}")
            time.sleep(5)

    print("S3 Ingestion Worker stopped.")

if __name__ == "__main__":
    start_worker()
