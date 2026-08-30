import os
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

    def embed_image(self, image: Image.Image) -> list[float]:
        """
        Embeds a single PIL Image.
        """
        print(f"Embedding image using model: {self.model_name}...")
        try:
            result = self.client.models.embed_content(
                model=self.model_name,
                contents=image
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Error embedding image: {e}")
            raise e

    def embed_text(self, text: str) -> list[float]:
        """
        Embeds a text query.
        """
        print(f"Embedding text using model: {self.model_name}...")
        try:
            result = self.client.models.embed_content(
                model=self.model_name,
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Error embedding text: {e}")
            raise e

