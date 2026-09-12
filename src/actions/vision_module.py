# src/actions/vision_module.py
"""
Módulo de visión para AP0L0 (Gemini Vision)
Funciones: click, type, search_on_site, camera, browser
"""

import os
import base64
import time
import json
import asyncio
try:
    import pyautogui
except ImportError:
    pyautogui = None
try:
    import cv2
except ImportError:
    cv2 = None
from PIL import Image
from src.core.config import _get_api_key, _validate_api_key
from src.core.ai_providers import generate

# ===== CONTEXTO GLOBAL =====
_VISION_CONTEXT = {}
_WEBCAM_ACTIVE = False


def set_vision_context(context: dict):
    global _VISION_CONTEXT
    _VISION_CONTEXT.update(context)


# ===== FUNCIONES DE CAPTURA =====
def _capture_screen():
    if pyautogui:
        screenshot = pyautogui.screenshot()
        import io
        buf = io.BytesIO()
        screenshot.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    return None


def _capture_camera():
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf.tobytes()).decode('utf-8')


def _ask_vision(prompt, img_b64):
    """Envía la imagen a Gemini Vision y devuelve la respuesta."""
    try:
        # Usar el cliente de visión del contexto si existe
        client = _VISION_CONTEXT.get("client")
        if client:
            import google.genai as genai
            from google.genai import types
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    prompt,
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                ]
            )
            return response.text.strip() if response and response.text else "No se pudo analizar la imagen."
        else:
            # Fallback con generación de texto
            return generate(f"Analiza esta imagen y responde: {prompt}", provider="gemini")
    except Exception as e:
        return f"Error al analizar la imagen: {e}"


# ===== FUNCIONES EXPORTABLES =====

async def vision_click(params: dict, player=None, speak=None) -> str:
    """
    Realiza un clic en la pantalla basado en una descripción.
    """
    instruction = params.get("instruction", "")
    if not instruction:
        return "Falta la instrucción para el clic."

    if pyautogui is None:
        return "pyautogui no está instalado."

    # Capturar pantalla
    img_b64 = _capture_screen()
    if not img_b64:
        return "No se pudo capturar la pantalla."

    # Analizar con IA
    prompt = (
        f"Identifica en la imagen el elemento: '{instruction}'. "
        "Devuelve las coordenadas normalizadas (0-1000) del centro del elemento en formato JSON: "
        '{"x": 500, "y": 500, "desc": "descripción"}'
    )
    respuesta = _ask_vision(prompt, img_b64)
    try:
        # Intentar extraer JSON
        import re
        json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            x = data.get("x", 500)
            y = data.get("y", 500)
            # Convertir de 0-1000 a coordenadas de pantalla
            screen_w, screen_h = pyautogui.size()
            target_x = int((x / 1000) * screen_w)
            target_y = int((y / 1000) * screen_h)
            pyautogui.moveTo(target_x, target_y, duration=0.3)
            pyautogui.click()
            desc = data.get("desc", instruction)
            return f"Clic en {desc} en coordenadas ({target_x}, {target_y})."
        else:
            return f"No se pudo interpretar la respuesta de la IA: {respuesta[:100]}..."
    except Exception as e:
        return f"Error procesando clic: {e}"


async def vision_type(params: dict, player=None, speak=None) -> str:
    """
    Escribe texto en un campo de entrada identificado por descripción.
    """
    instruction = params.get("instruction", "")
    texte = params.get("texte", "")
    if not instruction or not texte:
        return "Faltan instrucción o texto."

    if pyautogui is None:
        return "pyautogui no está instalado."

    img_b64 = _capture_screen()
    if not img_b64:
        return "No se pudo capturar la pantalla."

    prompt = (
        f"Identifica en la imagen el campo de entrada descrito como: '{instruction}'. "
        "Devuelve las coordenadas normalizadas (0-1000) del centro del campo en formato JSON: "
        '{"x": 500, "y": 500, "desc": "descripción"}'
    )
    respuesta = _ask_vision(prompt, img_b64)
    try:
        import re
        json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            x = data.get("x", 500)
            y = data.get("y", 500)
            screen_w, screen_h = pyautogui.size()
            target_x = int((x / 1000) * screen_w)
            target_y = int((y / 1000) * screen_h)
            pyautogui.moveTo(target_x, target_y, duration=0.3)
            pyautogui.click()
            time.sleep(0.2)
            import pyperclip
            pyperclip.copy(texte)
            pyautogui.hotkey('ctrl', 'v')
            return f"Texto '{texte[:30]}...' escrito en el campo."
        else:
            return f"No se pudo interpretar la respuesta: {respuesta[:100]}..."
    except Exception as e:
        return f"Error al escribir: {e}"


async def vision_search_on_site(params: dict, player=None, speak=None) -> str:
    """
    Busca un texto en la barra de búsqueda del sitio actual.
    """
    texte = params.get("texte", "")
    if not texte:
        return "Falta el texto a buscar."

    if pyautogui is None:
        return "pyautogui no está instalado."

    img_b64 = _capture_screen()
    if not img_b64:
        return "No se pudo capturar la pantalla."

    prompt = (
        "Identifica la barra de búsqueda principal en la imagen (campo de texto con lupa o placeholder 'Buscar', 'Search', etc.). "
        "Devuelve las coordenadas normalizadas (0-1000) del centro de la barra en formato JSON: "
        '{"x": 500, "y": 500, "desc": "barra de búsqueda"}'
    )
    respuesta = _ask_vision(prompt, img_b64)
    try:
        import re
        json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            x = data.get("x", 500)
            y = data.get("y", 500)
            screen_w, screen_h = pyautogui.size()
            target_x = int((x / 1000) * screen_w)
            target_y = int((y / 1000) * screen_h)
            pyautogui.moveTo(target_x, target_y, duration=0.3)
            pyautogui.click()
            time.sleep(0.2)
            import pyperclip
            pyperclip.copy(texte)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)
            pyautogui.press('enter')
            return f"Búsqueda '{texte}' realizada en la barra de búsqueda."
        else:
            return f"No se pudo encontrar la barra de búsqueda: {respuesta[:100]}..."
    except Exception as e:
        return f"Error en búsqueda: {e}"


async def vision_camera(params: dict, player=None, speak=None) -> str:
    """
    Captura imagen desde la cámara y la analiza con Gemini Vision.
    """
    question = params.get("question", "¿Qué ves en la imagen?")
    img_b64 = _capture_camera()
    if not img_b64:
        return "No se pudo capturar la imagen de la cámara. ¿Está conectada?"

    if speak:
        await speak("Analizando imagen de la cámara...")

    respuesta = _ask_vision(question, img_b64)
    return respuesta if respuesta else "No se pudo analizar la imagen."


async def vision_browser(params: dict, player=None, speak=None) -> str:
    """
    Captura la pantalla completa y la analiza con Gemini Vision.
    """
    question = params.get("question", "Describe lo que ves en la pantalla.")
    img_b64 = _capture_screen()
    if not img_b64:
        return "No se pudo capturar la pantalla."

    if speak:
        await speak("Analizando la pantalla...")

    respuesta = _ask_vision(question, img_b64)
    return respuesta if respuesta else "No se pudo analizar la pantalla."


# ===== FUNCIONES AUXILIARES (para compatibilidad con el código original) =====
# Estas son versiones sincrónicas para ser llamadas desde otros módulos si es necesario

def jarvis_vision_cliquer(instruction):
    """Versión sincrónica de vision_click (para compatibilidad)."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(vision_click({"instruction": instruction}))
    loop.close()
    return result


def jarvis_vision_ecrire(instruction, texte):
    """Versión sincrónica de vision_type."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(vision_type({"instruction": instruction, "texte": texte}))
    loop.close()
    return result


def jarvis_vision_rechercher_sur_site(texte):
    """Versión sincrónica de vision_search_on_site."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(vision_search_on_site({"texte": texte}))
    loop.close()
    return result


def jarvis_vision_camera(question=None):
    """Versión sincrónica de vision_camera."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(vision_camera({"question": question or "¿Qué ves?"}))
    loop.close()
    return result


def jarvis_vision_navigateur(question=None):
    """Versión sincrónica de vision_browser."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(vision_browser({"question": question or "Describe la pantalla."}))
    loop.close()
    return result