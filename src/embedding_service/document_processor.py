import base64
from io import BytesIO
from PIL import Image
from pdf2image import convert_from_path

def pdf_to_images(pdf_path):
    """
    Converts a PDF file into a list of PIL Images, one per page.
    """
    print(f"Loading PDF and converting to images: {pdf_path}")
    # You might need poppler installed on the system (e.g., brew install poppler)
    images = convert_from_path(pdf_path, dpi=150)
    print(f"Successfully converted {len(images)} pages to images.")
    
    
    resized_images = []
    for idx, img in enumerate(images):
        w, h = img.size
        max_dim = 1500
        if w > max_dim or h > max_dim:
            if w > h:
                new_w = max_dim
                new_h = int(h * (max_dim / w))
            else:
                new_h = max_dim
                new_w = int(w * (max_dim / h))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized_images.append(img)
    return resized_images

def image_to_base64(image):
    """
    Converts a PIL Image to a Base64 encoded string.
    """
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")
