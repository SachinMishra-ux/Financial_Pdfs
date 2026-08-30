import os
import base64
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(dotenv_path='../.env')

from src.embedding_service.document_processor import pdf_to_images, image_to_base64
from src.embedding_service.embedder import GeminiEmbedder
from src.embedding_service.qdrant_manager import QdrantManager

from src.embedding_service.gemini_rag_llm import GeminiRAG

load_dotenv(override=True)


def main():
    pdf_path = "/Users/sachinmishra/Desktop/MultiModal_RAG/pdfs/MIG29-Flight-Manual-Pt-1.pdf"
    if not os.path.exists(pdf_path):
        pdf_path = "/Users/sachinmishra/Desktop/MultiModal_RAG/pdfs/MIG29-Flight-Manual-Pt-1.pdf"
        
    collection_name = "mig_26_images"
    qdrant_url = "http://localhost:6333"
    
    # Try connecting to Qdrant Docker server, fallback to local path storage if not running
    import urllib.request
    use_server = False
    try:
        with urllib.request.urlopen(f"{qdrant_url.rstrip('/')}/healthz", timeout=1.0) as response:
            if response.status == 200:
                use_server = True
    except Exception:
        pass
        
    if use_server:
        print("Successfully connected to Qdrant server running on Docker (localhost:6333)")
        qdrant_manager = QdrantManager(url=qdrant_url, collection_name=collection_name)
    else:
        qdrant_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qdrant_storage")
        print(f"Qdrant Docker server not detected. Falling back to local persistent path: {qdrant_path}")
        qdrant_manager = QdrantManager(path=qdrant_path, collection_name=collection_name)
        
    # Check if collection exists and has points (skip embedding step if already populated)
    has_vectors = False
    if qdrant_manager.client.collection_exists(collection_name):
        try:
            info = qdrant_manager.client.get_collection(collection_name)
            has_vectors = info.points_count > 0
        except Exception:
            pass

    embedder = GeminiEmbedder(model_name="gemini-embedding-2")

    if not has_vectors:
        print("\nQdrant database is empty. Starting document processing & embedding pipeline...")
        # 1. Convert PDF to images
        images = pdf_to_images(pdf_path)
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
    else:
        print("\nVectors already present in Qdrant database. Skipping document ingestion.")

    # 4. Interactive loop to wait for user questions
    print("\n" + "="*50)
    print("Qdrant RAG system is ready!")
    print("Type your question below. Type 'exit' or 'quit' to stop.")
    print("="*50)
    
    while True:
        try:
            question = input("\nAsk a question: ").strip()
            if not question:
                continue
            if question.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
                
            print("Embedding query text...")
            query_embedding = embedder.embed_text(question)
            
            print("Retrieving most relevant image from Qdrant...")
            top_base64_images = qdrant_manager.search(query_embedding, limit=1)
            
            if not top_base64_images:
                print("No relevant images found in the vector database.")
                continue
                
            # 5. Answer using Groq Vision LLM
            
            rag_llm = GeminiRAG()
            answer = rag_llm.answer_question(question, top_base64_images)
            
            print("\n" + "="*50)
            print("Answer:")
            print(answer)
            print("="*50)
            
            # 6. Save the reference image for viewing
            reference_img_path = "reference_output.jpg"
            with open(reference_img_path, "wb") as f:
                f.write(base64.b64decode(top_base64_images[0]))
            print(f"\nSaved the matched reference image to '{reference_img_path}'.")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
