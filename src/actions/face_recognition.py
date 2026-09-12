# =====================================================================
# face_recognition.py — Servicio de reconocimiento facial (CORREGIDO)
# =====================================================================

import os
import cv2
import numpy as np
import sys
import json
from pathlib import Path
import urllib.request
import warnings
import time
import base64

# ===== SILENCIAR WARNINGS =====
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ===== CONFIGURACIÓN DE RUTAS =====
def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
LAST_CAPTURED_IMAGE = BASE_DIR / "last_captured_image.jpg"

# ===== MODELOS GEMINI (SOLO MODELOS QUE FUNCIONAN) =====
VISION_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
]

# ===== CONFIGURACIÓN DE GEMINI =====
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
    print("[FaceRecognition] ✅ google-genai disponible")
except ImportError:
    GENAI_AVAILABLE = False
    print("[FaceRecognition] ⚠️ google-genai no instalado")

def _get_api_key() -> str:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("gemini_api_key", "")
    except Exception:
        return ""

def _call_gemini_vision(image_bytes: bytes, prompt: str) -> str:
    if not GENAI_AVAILABLE:
        return "[Error] google-genai no está instalado"
    
    api_key = _get_api_key()
    if not api_key:
        return "[Error] No hay API key configurada"
    
    if not api_key.startswith(("AIza", "AQ.")):
        return "[Error] API key parece inválida (debe empezar con AIza o AQ.)"
    
    try:
        client = genai.Client(api_key=api_key)
        
        for model_name in VISION_MODELS:
            try:
                print(f"[FaceRecognition] Intentando con: {model_name}")
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=500,
                    )
                )
                
                if response and response.text:
                    text = response.text.strip()
                    if len(text) > 10:
                        print(f"[FaceRecognition] ✅ {model_name} respondió correctamente")
                        return text
                    else:
                        print(f"[FaceRecognition] ⚠️ {model_name} devolvió texto vacío o muy corto")
                        
            except Exception as e:
                error_msg = str(e).lower()
                if "404" in error_msg or "not found" in error_msg:
                    print(f"[FaceRecognition] ⚠️ {model_name} no disponible (404)")
                    continue
                elif "api key" in error_msg or "authentication" in error_msg:
                    print(f"[FaceRecognition] ❌ Error de autenticación con {model_name}")
                    return f"[Error] La API key de Gemini no es válida. Verifica src/config/api_keys.json"
                elif "quota" in error_msg or "exhausted" in error_msg:
                    print(f"[FaceRecognition] ⚠️ Cuota agotada para {model_name}")
                    continue
                else:
                    print(f"[FaceRecognition] ⚠️ {model_name} falló: {error_msg[:80]}")
                    continue
        
        return "[Error] Todos los modelos de Gemini fallaron. Verifica tu conexión a internet y la API key."
        
    except Exception as e:
        error_msg = str(e)
        if "api key" in error_msg.lower():
            return "[Error] La API key de Gemini es inválida. Revisa el archivo api_keys.json"
        return f"[Error] {error_msg[:150]}"

def _call_gemini_vision_from_path(image_path: str, prompt: str) -> str:
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        return _call_gemini_vision(image_bytes, prompt)
    except Exception as e:
        print(f"[FaceRecognition] Error leyendo imagen: {e}")
        return f"[Error] No se pudo leer la imagen: {e}"

def _find_captured_image() -> str:
    possible_paths = [
        str(LAST_CAPTURED_IMAGE),
        str(BASE_DIR / "last_captured_image.jpg"),
        "last_captured_image.jpg",
        str(Path.home() / "Desktop" / "last_captured_image.jpg"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

# =====================================================================
# DETECCIÓN FACIAL CON OPENCV
# =====================================================================

_face_cascade = None

def _get_face_cascade():
    global _face_cascade
    if _face_cascade is not None:
        return _face_cascade
    try:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        _face_cascade = cv2.CascadeClassifier(cascade_path)
        if _face_cascade.empty():
            _face_cascade = None
            print("[FaceRecognition] ⚠️ Clasificador facial no disponible")
    except Exception as e:
        print(f"[FaceRecognition] ⚠️ Error cargando clasificador: {e}")
        _face_cascade = None
    return _face_cascade

def detect_faces_in_image(image_path: str) -> list:
    cascade = _get_face_cascade()
    if cascade is None:
        return []
    try:
        img = cv2.imread(image_path)
        if img is None:
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 4)
        return faces.tolist()
    except Exception:
        return []

# =====================================================================
# CLASE PRINCIPAL
# =====================================================================

class FaceRecognitionService:
    def __init__(self, silent: bool = True):
        self.silent = silent

    def recognize(self, image_path: str) -> str:
        if not os.path.exists(image_path):
            found = _find_captured_image()
            if found:
                image_path = found
                print(f"[FaceRecognition] Usando imagen capturada: {image_path}")
            else:
                return "❌ Imagen no encontrada"

        faces = detect_faces_in_image(image_path)
        if not faces:
            result = "⚠️ No se detectaron rostros en la imagen.\n"
            result += "Asegúrate de que la imagen tenga un rostro visible y bien iluminado."
            return result

        result = f"👤 {len(faces)} rostro(s) detectado(s) en la imagen\n\n"

        prompt = """
Eres AP0L0, un asistente de IA con visión avanzada.
Analiza esta imagen y responde en español:

1. ¿Hay personas FAMOSAS en la imagen? Si es así, dime su NOMBRE COMPLETO.
2. Si son personas comunes, describe sus rasgos principales (edad aproximada, género, etnia).
3. Describe el contexto: ¿qué está pasando en la imagen? ¿Qué objetos hay?
4. Si hay texto visible, transcríbelo.

Responde en 3-4 frases claras y concisas.
"""
        gemini_result = _call_gemini_vision_from_path(image_path, prompt)
        
        if gemini_result and not gemini_result.startswith("[Error]"):
            return result + "🔍 " + gemini_result
        else:
            return result + "⚠️ No se pudo identificar usando IA. " + gemini_result

# =====================================================================
# FUNCIÓN EXPORTABLE
# =====================================================================

def face_recognize(parameters: dict, player=None, speak=None) -> str:
    image_path = parameters.get("image_path", "")
    
    if not image_path or image_path == "last_captured_image":
        found = _find_captured_image()
        if found:
            image_path = found
            if player:
                player.write_log(f"[FaceRecognition] Usando: {Path(image_path).name}")
        else:
            return "❌ No hay imagen capturada. Usa 'screen_process' primero con la cámara o sube una imagen."
    
    if not os.path.exists(image_path):
        return f"❌ Imagen no encontrada: {image_path}"
    
    service = FaceRecognitionService()
    result = service.recognize(image_path)
    
    if speak and result:
        try:
            speak(result[:200])
        except Exception:
            pass
    
    return result

# =====================================================================
# PRUEBA
# =====================================================================

if __name__ == "__main__":
    print("🧪 FaceRecognitionService")
    print("=" * 52)
    
    api_key = _get_api_key()
    if api_key:
        print(f"✅ API key: {api_key[:10]}...")
        if api_key.startswith(("AIza", "AQ.")):
            print("✅ Formato de API key válido")
        else:
            print("⚠️ Formato de API key sospechoso (debe empezar con AIza o AQ.)")
    else:
        print("❌ No hay API key")
    
    img = _find_captured_image()
    if img and os.path.exists(img):
        print(f"\n📸 Analizando: {img}")
        print("-" * 52)
        service = FaceRecognitionService()
        print(service.recognize(img))
    else:
        print("⚠️ No hay imagen. Usa 'screen_process' primero.")