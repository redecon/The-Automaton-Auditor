# src/tools/vision_tools.py
import pdfplumber
from PIL import Image
import io

def extract_images_from_pdf(path: str) -> list:
    """Extract images from PDF and return list of PIL Image objects."""
    images = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for img in page.images:
                # Extract raw image bytes
                x0, top, x1, bottom = img["x0"], img["top"], img["x1"], img["bottom"]
                cropped = page.within_bbox((x0, top, x1, bottom)).to_image(resolution=150)
                img_bytes = cropped.original
                pil_img = Image.open(io.BytesIO(img_bytes))
                images.append(pil_img)
    return images

def classify_diagram_flow(image: Image.Image) -> str:
    """
    Placeholder classification logic.
    In production, you’d send the image to a multimodal LLM (e.g., Gemini Pro Vision).
    For now, return a dummy classification.
    """
    # TODO: integrate multimodal model
    return "Generic flowchart (placeholder)"
