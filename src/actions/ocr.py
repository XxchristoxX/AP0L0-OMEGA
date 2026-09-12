# actions/ocr.py
# Servicio OCR con Tesseract

import pytesseract
from PIL import Image
import os

try:
    pytesseract.get_tesseract_version()
except:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCRService:
    """Servicio de OCR para extraer texto de imágenes."""

    def __init__(self):
        self.supported_langs = ['spa', 'eng', 'spa+eng']
        print("[OCRService] Inicializado.")

    def extract_text_from_image(self, image_path: str, lang: str = 'spa+eng') -> str:
        if not os.path.exists(image_path):
            return f"Error: La imagen no existe en la ruta: {image_path}"

        try:
            img = Image.open(image_path)
            if lang not in self.supported_langs and '+' not in lang:
                lang = 'spa+eng'
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip() if text.strip() else "No se encontró texto en la imagen."
        except Exception as e:
            return f"Error en OCR: {str(e)}"

    def extract_text_from_bytes(self, image_bytes: bytes, lang: str = 'spa+eng') -> str:
        try:
            from io import BytesIO
            img = Image.open(BytesIO(image_bytes))
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip() if text.strip() else "No se encontró texto en la imagen."
        except Exception as e:
            return f"Error en OCR: {str(e)}"