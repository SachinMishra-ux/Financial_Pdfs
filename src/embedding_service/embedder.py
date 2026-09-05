import os
import time
import random
from google import genai
from PIL import Image

class GeminiEmbedder:
    def __init__(self, model_name="gemini-embedding-2"):
        """
        Initializes the Google GenAI client and sets the model.
        The user specified "gemini-embedding-2".
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def embed_image(self, image: Image.Image, max_retries: int = 6, initial_backoff: float = 4.0) -> list[float]:
        """
        Embeds a single PIL Image with automatic exponential backoff retry for rate limits (429).
        """
        print(f"Embedding image using model: {self.model_name}...")
        for attempt in range(max_retries):
            try:
                result = self.client.models.embed_content(
                    model=self.model_name,
                    contents=image
                )
                return result.embeddings[0].values
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    sleep_time = (initial_backoff * (2 ** attempt)) + random.uniform(1.0, 3.0)
                    print(f"⏳ Rate limit (429) hit. Backing off for {sleep_time:.1f}s (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    print(f"Error embedding image: {e}")
                    raise e

        # Final attempt
        result = self.client.models.embed_content(
            model=self.model_name,
            contents=image
        )
        return result.embeddings[0].values

    def embed_text(self, text: str, max_retries: int = 5, initial_backoff: float = 2.0) -> list[float]:
        """
        Embeds a text query with automatic retry on rate limits (429).
        """
        print(f"Embedding text using model: {self.model_name}...")
        for attempt in range(max_retries):
            try:
                result = self.client.models.embed_content(
                    model=self.model_name,
                    contents=text
                )
                return result.embeddings[0].values
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    sleep_time = (initial_backoff * (2 ** attempt)) + random.uniform(0.5, 1.5)
                    print(f"⏳ Rate limit (429) hit on text embedding. Retrying in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                else:
                    print(f"Error embedding text: {e}")
                    raise e

        result = self.client.models.embed_content(
            model=self.model_name,
            contents=text
        )
        return result.embeddings[0].values
