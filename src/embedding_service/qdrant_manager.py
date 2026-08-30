import uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

class QdrantManager:
    def __init__(self, url=None, path=None, collection_name="mig_26_images"):
        if path:
            self.client = QdrantClient(path=path)
        else:
            self.client = QdrantClient(url=url or "http://localhost:6333")
        self.collection_name = collection_name
        
    def ensure_collection(self, vector_size: int = 1024):
        """
        Creates the collection if it doesn't exist.
        The default vector size for Gemini text-embedding-002 is 1024.
        """
        if self.client.collection_exists(self.collection_name):
            collection_info = self.client.get_collection(self.collection_name)
            existing_size = None
            vectors_config = collection_info.config.params.vectors
            
            # Extract existing size from config
            if hasattr(vectors_config, 'size'):
                existing_size = vectors_config.size
            elif isinstance(vectors_config, dict):
                if '' in vectors_config:
                    existing_size = vectors_config[''].size
                elif len(vectors_config) > 0:
                    existing_size = list(vectors_config.values())[0].size
            
            if existing_size != vector_size:
                print(f"Dimension mismatch: existing collection size is {existing_size}, but required size is {vector_size}.")
                print(f"Recreating collection '{self.collection_name}' with size {vector_size}...")
                self.client.delete_collection(self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            print(f"Creating collection '{self.collection_name}' with size {vector_size}...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            print(f"Collection '{self.collection_name}' already exists.")
            
    def insert_image_embeddings(self, embeddings: list[list[float]], base64_images: list[str], batch_size: int = 20):
        """
        Inserts a list of image embeddings into Qdrant in batches, along with the base64 images as payload.
        """
        print(f"Inserting {len(embeddings)} points into Qdrant in batches of {batch_size}...")
        points = []
        for emb, b64_img in zip(embeddings, base64_images):
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=emb,
                    payload={"image_base64": b64_img}
                )
            )
        
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            total_batches = (len(points) - 1) // batch_size + 1
            print(f"Uploading batch {i // batch_size + 1}/{total_batches} ({len(batch)} points)...")
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        print("Insertion complete.")
        
    def search(self, query_embedding: list[float], limit: int = 1) -> list[str]:
        """
        Searches the vector DB using the query embedding and returns the top matched base64 images.
        """
        print(f"Searching Qdrant for top {limit} matches...")
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit
        )
        
        base64_images = []
        for hit in search_result.points:
            if hit.payload and "image_base64" in hit.payload:
                base64_images.append(hit.payload["image_base64"])
        
        return base64_images
