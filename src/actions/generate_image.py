# src/actions/generate_image.py
"""
Generación de imágenes para AP0L0 con servicios gratuitos de alta calidad.
Prioridad:
1. Hugging Face (Stable Diffusion XL/SD 2.1) - Gratuito, calidad profesional.
2. DeepAI - 50 imágenes/día gratis (con clave opcional, funciona sin ella con límite).
3. Pollinations.ai - Gratuito e ilimitado (mejorado con seed aleatorio).
4. Unsplash - Imágenes de stock.
5. Pillow - Dibujo local (último recurso).
"""
import os
import sys
import time
import json
import random
import base64
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import hashlib

# Intentar importar Pillow para el fallback final
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


def _get_api_key(key_name: str) -> str:
    """Obtiene una clave API de la configuración."""
    try:
        from src.core.config import get_config
        return get_config().get(key_name, "")
    except Exception:
        return ""


def _download_image(url: str, source: str, player) -> str:
    """
    Descarga una imagen desde una URL y la guarda en el escritorio.
    Retorna el mensaje de resultado.
    """
    try:
        desktop = Path.home() / "Desktop"
        filename = f"{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = desktop / filename
        response = requests.get(url, timeout=30, stream=True)
        if response.status_code == 200:
            # Verificar que sea una imagen válida
            content_type = response.headers.get('content-type', '').lower()
            if 'image' in content_type:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                if player:
                    player.write_log(f"[Image] ✅ Imagen guardada desde {source}")
                return f"Imagen generada: {filename} (guardada en {filepath})"
            else:
                return f"[Image] Error: {source} no devolvió una imagen válida."
        return f"[Image] Error: No se pudo descargar la imagen de {source} (HTTP {response.status_code})"
    except Exception as e:
        return f"[Image] Error descargando imagen: {e}"


def _generate_with_huggingface(prompt: str, player) -> str:
    """
    Genera imagen usando Hugging Face Inference API.
    Modelos: stabilityai/stable-diffusion-xl-base-1.0 (premium) o sd-2-1.
    Es COMPLETAMENTE GRATUITO, solo requiere esperar si el modelo está frío (503).
    """
    # Modelos disponibles en Hugging Face (orden de preferencia)
    models = [
        "stabilityai/stable-diffusion-xl-base-1.0",  # Mejor calidad
        "stabilityai/stable-diffusion-2-1",          # Más estable
        "runwayml/stable-diffusion-v1-5",            # Clásico
    ]

    for model_id in models:
        if player:
            player.write_log(f"[Image] Hugging Face: probando {model_id.split('/')[-1]}...")

        api_url = f"https://api-inference.huggingface.co/models/{model_id}"
        headers = {"Content-Type": "application/json"}

        # Mejorar el prompt para SD
        improved_prompt = f"{prompt}, high quality, detailed, 8k, professional photography, sharp focus"
        payload = {
            "inputs": improved_prompt,
            "parameters": {
                "negative_prompt": "deformed, ugly, blurry, low quality, distorted, watermark, text, signature",
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "width": 512,
                "height": 512,
            }
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    # Guardar la imagen directamente
                    desktop = Path.home() / "Desktop"
                    filename = f"hf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    filepath = desktop / filename
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    if player:
                        player.write_log(f"[Image] ✅ Imagen generada con Hugging Face ({model_id.split('/')[-1]})")
                    return f"Imagen generada: {filename} (guardada en {filepath})"
                else:
                    # Puede ser un error en formato JSON
                    try:
                        error_data = response.json()
                        if 'error' in error_data:
                            # Si el modelo está cargando, esperar y reintentar una vez
                            if 'loading' in str(error_data).lower():
                                if player:
                                    player.write_log("[Image] Modelo cargando, esperando 15s...")
                                time.sleep(15)
                                # Reintentar una vez
                                response2 = requests.post(api_url, headers=headers, json=payload, timeout=120)
                                if response2.status_code == 200 and 'image' in response2.headers.get('content-type', ''):
                                    desktop = Path.home() / "Desktop"
                                    filename = f"hf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                    filepath = desktop / filename
                                    with open(filepath, "wb") as f:
                                        f.write(response2.content)
                                    if player:
                                        player.write_log(f"[Image] ✅ Imagen generada con Hugging Face (tras espera)")
                                    return f"Imagen generada: {filename} (guardada en {filepath})"
                            continue
                    except:
                        pass
            elif response.status_code == 503:
                # Modelo cargando (común en HF gratuito)
                if player:
                    player.write_log("[Image] Hugging Face: modelo cargando, esperando 20s...")
                time.sleep(20)
                # Reintentar una vez más
                retry_response = requests.post(api_url, headers=headers, json=payload, timeout=120)
                if retry_response.status_code == 200 and 'image' in retry_response.headers.get('content-type', ''):
                    desktop = Path.home() / "Desktop"
                    filename = f"hf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    filepath = desktop / filename
                    with open(filepath, "wb") as f:
                        f.write(retry_response.content)
                    if player:
                        player.write_log("[Image] ✅ Imagen generada con Hugging Face (tras carga)")
                    return f"Imagen generada: {filename} (guardada en {filepath})"
        except Exception as e:
            if player:
                player.write_log(f"[Image] Hugging Face error con {model_id}: {str(e)[:60]}")
            continue

    return "[Image] Error: Todos los modelos de Hugging Face fallaron."


def _generate_with_deepai(prompt: str, player) -> str:
    """
    Genera imagen usando DeepAI.
    Plan gratuito: 50 imágenes/día (funciona sin clave, pero con clave es más estable).
    """
    try:
        # DeepAI permite solicitudes sin clave (con límite)
        # Si tienes clave, se puede añadir en el header
        api_key = _get_api_key("deepai_api_key")
        url = "https://api.deepai.org/api/text2img"

        # Mejorar prompt para DeepAI
        improved_prompt = f"{prompt}, high quality, detailed"

        if api_key:
            headers = {"api-key": api_key}
        else:
            headers = {}

        payload = {'text': improved_prompt}

        response = requests.post(url, data=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            # DeepAI devuelve 'output_url' o directamente 'image_data' (base64)
            if 'output_url' in data:
                return _download_image(data['output_url'], "deepai", player)
            elif 'image_data' in data:
                # Decodificar base64
                image_data = base64.b64decode(data['image_data'])
                desktop = Path.home() / "Desktop"
                filename = f"deepai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                filepath = desktop / filename
                with open(filepath, "wb") as f:
                    f.write(image_data)
                if player:
                    player.write_log("[Image] ✅ Imagen generada con DeepAI")
                return f"Imagen generada: {filename} (guardada en {filepath})"
        elif response.status_code == 429:
            return "[Image] Error: Límite diario de DeepAI agotado. Intenta mañana."
        else:
            return f"[Image] Error: DeepAI falló (HTTP {response.status_code})"
    except Exception as e:
        return f"[Image] Error en DeepAI: {e}"


def _generate_with_pollinations(prompt: str, size: str, player) -> str:
    """
    Genera imagen usando Pollinations.ai.
    Completamente gratuito e ilimitado. Calidad mejorada con parámetros.
    """
    try:
        width, height = 512, 512
        if 'x' in size:
            try:
                w, h = size.split('x')
                width = int(w)
                height = int(h)
            except:
                pass
        width = min(width, 1024)
        height = min(height, 1024)

        # Añadir seed aleatorio para variedad y mejorar el prompt
        seed = random.randint(1, 999999)
        improved_prompt = f"{prompt}, high quality, beautiful, detailed"
        encoded_prompt = quote(improved_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true&enhance=true"

        if player:
            player.write_log(f"[Image] Pollinations: intentando generación...")

        response = requests.get(url, timeout=45)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type:
                return _download_image_from_response(response.content, "pollinations", player)
            else:
                # Pollinations a veces devuelve texto de error
                try:
                    error_text = response.text[:100]
                    if 'error' in error_text.lower():
                        return f"[Image] Error: Pollinations dice: {error_text}"
                except:
                    pass
                return "[Image] Error: Pollinations no devolvió una imagen."
        return f"[Image] Error: Pollinations (HTTP {response.status_code})"
    except Exception as e:
        return f"[Image] Error en Pollinations: {e}"


def _download_image_from_response(content: bytes, source: str, player) -> str:
    """Guarda imagen desde bytes."""
    try:
        desktop = Path.home() / "Desktop"
        filename = f"{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = desktop / filename
        with open(filepath, "wb") as f:
            f.write(content)
        if player:
            player.write_log(f"[Image] ✅ Imagen guardada desde {source}")
        return f"Imagen generada: {filename} (guardada en {filepath})"
    except Exception as e:
        return f"[Image] Error guardando imagen: {e}"


def _generate_with_unsplash(prompt: str, player) -> str:
    """Fallback: imágenes de stock de Unsplash."""
    try:
        query = quote(prompt)
        # Clave de demostración de Unsplash (pública, limitada)
        client_id = "z8kHt1Hh3gP7pG7V5sXg0xYzQ9v3U5z7H0fG1l2M3="
        url = f"https://api.unsplash.com/search/photos?query={query}&per_page=1&client_id={client_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('results') and len(data['results']) > 0:
                image_url = data['results'][0]['urls']['regular']
                return _download_image(image_url, "unsplash", player)
        return "[Image] Error: Unsplash falló."
    except Exception as e:
        return f"[Image] Error en Unsplash: {e}"


def _generate_with_pillow(prompt: str, player) -> str:
    """Último recurso: dibujo con Pillow (mejorado con colores y formas)."""
    if not HAS_PILLOW:
        return "No se pudo generar imagen. Instala Pillow: pip install Pillow"

    try:
        import math
        desktop = Path.home() / "Desktop"
        filename = f"generated_draw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = desktop / filename

        width, height = 800, 600
        img = Image.new('RGB', (width, height), color=(15, 25, 45))
        draw = ImageDraw.Draw(img)

        # Fondo con degradado de colores
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
        block_height = height // len(colors)
        for i, color in enumerate(colors):
            y0 = i * block_height
            y1 = (i + 1) * block_height if i < len(colors) - 1 else height
            draw.rectangle([0, y0, width, y1], fill=color)

        # Círculo central con gradiente simulado
        center_x, center_y = width // 2, height // 2
        radius = 140
        # Círculo exterior
        draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                     outline='white', width=6)
        # Círculo interior
        draw.ellipse([center_x - radius + 20, center_y - radius + 20,
                      center_x + radius - 20, center_y + radius - 20],
                     outline='#FFD700', width=3)

        # Estrella de 5 puntas
        star_points = []
        for i in range(10):
            angle = i * 3.14159 / 5 - 3.14159 / 2
            r = radius * 0.6 if i % 2 == 0 else radius * 0.25
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            star_points.append((x, y))
        draw.polygon(star_points, outline='yellow', width=3, fill='rgba(255,215,0,80)')

        # Texto del prompt
        try:
            font = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
            font_small = font

        # Dividir el prompt en líneas
        max_chars = 45
        words = prompt.split()
        lines = []
        current = ""
        for w in words:
            if len(current) + len(w) + 1 <= max_chars:
                current += (" " + w) if current else w
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)

        # Dibujar texto
        y_text = height - len(lines) * 28 - 30
        for line in lines:
            text_width = draw.textlength(line, font=font)
            x = (width - text_width) // 2
            # Sombra negra detrás del texto para contraste
            draw.text((x+1, y_text+1), line, fill='black', font=font)
            draw.text((x, y_text), line, fill='white', font=font)
            y_text += 28

        # Pie de página
        footer = "Generado por AP0L0 IA"
        draw.text((10, height - 25), footer, fill=(180, 180, 180), font=font_small)
        draw.text((width - 150, height - 25), datetime.now().strftime("%H:%M:%S"),
                  fill=(150, 150, 150), font=font_small)

        img.save(filepath)
        if player:
            player.write_log("[Image] ✅ Imagen de dibujo generada con Pillow")
        return f"Imagen de dibujo generada: {filename} (guardada en {filepath})"
    except Exception as e:
        return f"[Image] Error en Pillow: {e}"


# ===== FUNCIÓN PRINCIPAL =====
def generate_image(parameters: dict, player=None, speak=None) -> str:
    """
    Genera una imagen a partir de un prompt.
    Prioriza servicios gratuitos de alta calidad.
    """
    prompt = parameters.get("prompt", "").strip()
    if not prompt:
        return "No se proporcionó un prompt para generar la imagen."

    size = parameters.get("size", "512x512")
    style = parameters.get("style", "")

    # Añadir estilo al prompt si se especifica
    final_prompt = f"{prompt}, {style} style" if style else prompt

    if player:
        player.write_log(f"[Image] Generando: {final_prompt[:60]}...")

    # 1. Hugging Face (mejor calidad, totalmente gratuito)
    if player:
        player.write_log("[Image] Intentando con Hugging Face...")
    result = _generate_with_huggingface(final_prompt, player)
    if result and not result.startswith("[Image] Error"):
        return result

    # 2. DeepAI (50 imágenes/día gratis)
    if player:
        player.write_log("[Image] Intentando con DeepAI...")
    result = _generate_with_deepai(final_prompt, player)
    if result and not result.startswith("[Image] Error"):
        return result

    # 3. Pollinations.ai (ilimitado, calidad media)
    if player:
        player.write_log("[Image] Intentando con Pollinations.ai...")
    result = _generate_with_pollinations(final_prompt, size, player)
    if result and not result.startswith("[Image] Error"):
        return result

    # 4. Unsplash (stock images)
    if player:
        player.write_log("[Image] Intentando con Unsplash...")
    result = _generate_with_unsplash(final_prompt, player)
    if result and not result.startswith("[Image] Error"):
        return result

    # 5. Pillow (dibujo local)
    if player:
        player.write_log("[Image] Usando generación local con Pillow...")
    return _generate_with_pillow(final_prompt, player)