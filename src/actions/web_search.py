# src/actions/web_search.py
"""
Módulo de búsqueda web para AP0L0.
Soporta: search, news, images, videos, research, price, compare, define, trending, summarize, translate, calculate, citations.
"""

import json
import sys
import time
import re
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# ===== CONFIGURACIÓN =====
def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# Modelos de Gemini para generateContent (texto)
GEMINI_MODELS = [
    "models/gemini-1.5-flash",
    "models/gemini-1.5-pro",
    "models/gemini-2.0-flash-exp",
    "models/gemini-2.0-pro-exp",
]

# Caché en memoria
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300  # 5 minutos

def _get_api_key(key_name: str = "gemini_api_key") -> Optional[str]:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get(key_name)
    except Exception:
        return None

# ===== IMPORTACIÓN DDGS =====
try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        DDGS = None
        _DDGS_AVAILABLE = False
        print("[WebSearch] ⚠️ DuckDuckGo no disponible. Instala: pip install ddgs")

# ===== CACHÉ MEJORADO =====
def _cache_get(key: str) -> Optional[str]:
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry["time"] < CACHE_TTL:
            return entry["data"]
        else:
            del _cache[key]
    return None

def _cache_set(key: str, data: str) -> None:
    _cache[key] = {"data": data, "time": time.time()}

# ===== GEMINI CON REINTENTOS =====
def _gemini_generate(prompt: str, max_retries: int = 2) -> Optional[str]:
    """Genera contenido con Gemini, probando varios modelos."""
    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except ImportError:
        return None

    for model in GEMINI_MODELS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if response and response.candidates:
                    parts = response.candidates[0].content.parts
                    text = "".join(p.text for p in parts if hasattr(p, "text") and p.text)
                    if text.strip():
                        return text.strip()
                print(f"[WebSearch] ⚠️ Respuesta vacía de {model}, reintentando...")
            except Exception as e:
                print(f"[WebSearch] ⚠️ Falló {model} (intento {attempt+1}): {e}")
                time.sleep(1)
        print(f"[WebSearch] ⚠️ Modelo {model} falló, probando siguiente...")
    return None

# ===== BÚSQUEDAS DDG (MEJORADAS CON CITAS) =====
def _ddg_search_with_citations(query: str, max_results: int = 6) -> dict:
    """
    Búsqueda en DuckDuckGo con formato de citas.
    Retorna: {"results": lista, "sources": lista_de_urls}
    """
    if not _DDGS_AVAILABLE:
        return {"results": [], "sources": []}

    results = []
    sources = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                snippet = r.get("body", "")
                url = r.get("href", "")
                if title:
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": url,
                    })
                    if url:
                        sources.append(url)
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG text search falló: {e}")

    return {"results": results, "sources": sources[:5]}

def _ddg_search(query: str, max_results: int = 6) -> List[Dict]:
    """Búsqueda web con DuckDuckGo (compatibilidad con código existente)."""
    if not _DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG text search falló: {e}")
    return results

def _ddg_news(query: str, max_results: int = 8, region: str = "wt-es") -> List[Dict]:
    """Búsqueda de noticias con DuckDuckGo."""
    if not _DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results, region=region):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("url",    ""),
                    "source":  r.get("source", ""),
                    "date":    r.get("date",   ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG news falló ({e}), usando text search...")
        results = _ddg_search(query, max_results=max_results)
    return results

def _ddg_images(query: str, max_results: int = 6) -> List[Dict]:
    if not _DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url":   r.get("url", ""),
                    "image": r.get("image", ""),
                    "source": r.get("source", ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG images falló: {e}")
    return results

def _ddg_videos(query: str, max_results: int = 5) -> List[Dict]:
    if not _DDGS_AVAILABLE:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.videos(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url":   r.get("url", ""),
                    "duration": r.get("duration", ""),
                    "source": r.get("source", ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG videos falló: {e}")
    return results

def _ddg_answers(query: str) -> Optional[str]:
    if not _DDGS_AVAILABLE:
        return None
    try:
        with DDGS() as ddgs:
            for r in ddgs.answers(query):
                if r.get("text"):
                    return r["text"]
    except Exception:
        pass
    return None

# ===== PERPLEXITY API (OPCIONAL, PLAN GRATUITO) =====
def _perplexity_search(query: str) -> Optional[str]:
    """
    Búsqueda con Perplexity API (plan gratuito: $1 de crédito inicial).
    """
    api_key = _get_api_key("perplexity_api_key")
    if not api_key:
        return None

    try:
        import requests
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3-sonar-small-32k-online",
            "messages": [
                {"role": "system", "content": "Eres un asistente de búsqueda. Proporciona respuestas concisas con citas de fuentes."},
                {"role": "user", "content": query}
            ],
            "return_citations": True,
            "temperature": 0.2,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = data.get("citations", [])
            if citations:
                content += "\n\n**Fuentes:**\n" + "\n".join(f"- {c}" for c in citations[:5])
            return content
        return None
    except Exception as e:
        print(f"[WebSearch] Perplexity error: {e}")
        return None

# ===== FORMATEO =====
def _format_ddg(query: str, results: List[Dict]) -> str:
    if not results:
        return f"No se encontraron resultados para: {query}"
    lines = [f"🔍 Resultados para: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):
            lines.append(f"{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        if r.get("url"):
            lines.append(f"   🔗 {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()

def _format_citations(query: str, data: dict) -> str:
    """Formatea resultados con citas y fuentes."""
    results = data.get("results", [])
    sources = data.get("sources", [])
    if not results:
        return f"No se encontraron resultados para: {query}"

    lines = [f"🔍 Resultados para: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):
            lines.append(f"{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        if r.get("url"):
            lines.append(f"   🔗 {r['url']}")
        lines.append("")
    
    if sources:
        lines.append("\n📚 **Fuentes:**")
        for src in sources[:5]:
            lines.append(f"  - {src}")
    
    return "\n".join(lines).strip()

def _format_news(query: str, results: List[Dict]) -> str:
    if not results:
        return f"No se encontraron noticias para: {query}"
    lines = [f"📰 Noticias: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        if not title:
            continue
        src = f"  [{r.get('source', '')}]" if r.get("source") else ""
        lines.append(f"{i}. {title}{src}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:140]}...")
        if r.get("url"):
            lines.append(f"   🔗 {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()

def _format_images(query: str, results: List[Dict]) -> str:
    if not results:
        return f"No se encontraron imágenes para: {query}"
    lines = [f"🖼️ Imágenes para: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):
            lines.append(f"{i}. {r['title']}")
        if r.get("image"):
            lines.append(f"   📷 {r['image']}")
        if r.get("source"):
            lines.append(f"   Fuente: {r['source']}")
        lines.append("")
    return "\n".join(lines).strip()

def _format_videos(query: str, results: List[Dict]) -> str:
    if not results:
        return f"No se encontraron videos para: {query}"
    lines = [f"🎬 Videos para: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):
            lines.append(f"{i}. {r['title']}")
        if r.get("duration"):
            lines.append(f"   ⏱️ {r['duration']}")
        if r.get("url"):
            lines.append(f"   🔗 {r['url']}")
        if r.get("source"):
            lines.append(f"   Fuente: {r['source']}")
        lines.append("")
    return "\n".join(lines).strip()

# ===== RSS FALLBACK =====
def _rss_news(query: str = "top world news today", max_results: int = 10) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return "RSS news requiere 'requests' y 'beautifulsoup4'. Instálalos."

    try:
        rss_url = "https://news.google.com/rss?hl=es-419&gl=PE&ceid=PE:es-419"
        resp = requests.get(rss_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item")
        if not items:
            return "No se encontraron noticias en el RSS."

        headlines = []
        for i, item in enumerate(items[:max_results], 1):
            title = item.title.text if item.title else ""
            if title:
                headlines.append(f"{i}. {title}")
        if headlines:
            return "📰 Noticias (RSS):\n" + "\n".join(headlines)
        else:
            return "No se encontraron titulares en el RSS."
    except Exception as e:
        return f"Error al obtener noticias desde RSS: {e}"

# ===== FUNCIONES DE BÚSQUEDA =====
def _search(query: str) -> str:
    """Búsqueda general: DDGS principal, Gemini como mejora opcional."""
    cache_key = f"search_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # 1. Intentar con Perplexity (mejor calidad)
    perplexity_result = _perplexity_search(query)
    if perplexity_result:
        _cache_set(cache_key, perplexity_result)
        return perplexity_result

    # 2. Intentar respuesta directa de DDG
    answer = _ddg_answers(query)
    if answer:
        result = f"💡 {answer}"
        _cache_set(cache_key, result)
        return result

    # 3. Búsqueda DDG con citas
    data = _ddg_search_with_citations(query, max_results=6)
    if data["results"]:
        formatted = _format_citations(query, data)
        _cache_set(cache_key, formatted)
        return formatted

    # 4. Fallback: intentar con Gemini
    gemini_result = _gemini_generate(query)
    if gemini_result:
        _cache_set(cache_key, gemini_result)
        return gemini_result

    return f"No se encontraron resultados para: {query}"

def _news(query: str) -> str:
    cache_key = f"news_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if "peru" in query.lower() and ("world" in query.lower() or "international" in query.lower()):
        mundiales = _ddg_news("world news", max_results=6, region="wt-es")
        peruanas = _ddg_news("Peru news", max_results=6, region="pe-es")
        results = mundiales + peruanas
        if results:
            formatted = _format_news("Noticias Internacionales y de Perú", results)
            _cache_set(cache_key, formatted)
            return formatted

    ddg_results = _ddg_news(query if query else "world news", max_results=8, region="wt-es")
    if ddg_results:
        formatted = _format_news(query, ddg_results)
        _cache_set(cache_key, formatted)
        return formatted

    formatted = _rss_news(query, max_results=10)
    _cache_set(cache_key, formatted)
    return formatted

def _research(query: str) -> str:
    cache_key = f"research_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # Intentar con Perplexity primero
    perplexity_result = _perplexity_search(query)
    if perplexity_result:
        _cache_set(cache_key, perplexity_result)
        return perplexity_result

    prompt = (
        f"Proporciona una explicación detallada y completa sobre: {query}. "
        "Incluye contexto, hechos clave, estado actual, matices importantes y perspectivas futuras. "
        "Estructura con títulos claros y viñetas."
    )
    gemini_result = _gemini_generate(prompt)
    if gemini_result:
        _cache_set(cache_key, gemini_result)
        return gemini_result

    results = _ddg_search(query, max_results=10)
    formatted = _format_ddg(query, results)
    _cache_set(cache_key, formatted)
    return formatted

def _price(query: str) -> str:
    cache_key = f"price_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    prompt = f"Precio actual de {query} en USD y EUR. Incluye tendencias si está disponible."
    gemini_result = _gemini_generate(prompt)
    if gemini_result:
        _cache_set(cache_key, gemini_result)
        return gemini_result

    results = _ddg_search(f"{query} price buy", max_results=6)
    formatted = _format_ddg(query, results)
    _cache_set(cache_key, formatted)
    return formatted

def _compare(items: List[str], aspect: str) -> str:
    cache_key = f"compare_{','.join(items)}_{aspect}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    prompt = (
        f"Compara {', '.join(items)} en términos de {aspect}. "
        "Proporciona una comparación detallada con pros y contras, precios, características y recomendaciones. "
        "Usa formato de tabla si es posible."
    )
    gemini_result = _gemini_generate(prompt)
    if gemini_result:
        _cache_set(cache_key, gemini_result)
        return gemini_result

    all_results = []
    for item in items:
        all_results.extend(_ddg_search(f"{item} {aspect}", max_results=2))
    lines = [f"📊 Comparación de {', '.join(items)} — {aspect}"]
    for r in all_results[:10]:
        if r.get("title"):
            lines.append(f"• {r['title']}")
        if r.get("snippet"):
            lines.append(f"  {r['snippet'][:120]}...")
    formatted = "\n".join(lines)
    _cache_set(cache_key, formatted)
    return formatted

def _image_search(query: str) -> str:
    cache_key = f"images_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    results = _ddg_images(query, max_results=6)
    if results:
        formatted = _format_images(query, results)
        _cache_set(cache_key, formatted)
        return formatted

    return f"No se encontraron imágenes para: {query}"

def _video_search(query: str) -> str:
    cache_key = f"videos_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    results = _ddg_videos(query, max_results=5)
    if results:
        formatted = _format_videos(query, results)
        _cache_set(cache_key, formatted)
        return formatted

    return f"No se encontraron videos para: {query}"

def _definition(query: str) -> str:
    cache_key = f"definition_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    prompt = f"Define '{query}' de forma clara y sencilla. Incluye origen, ejemplos de uso y términos relacionados."
    gemini_result = _gemini_generate(prompt)
    if gemini_result:
        _cache_set(cache_key, gemini_result)
        return gemini_result

    results = _ddg_search(f"define {query}", max_results=3)
    formatted = _format_ddg(query, results)
    _cache_set(cache_key, formatted)
    return formatted

def _trending() -> str:
    cache_key = "trending"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    prompt = "Lista los 10 temas o búsquedas más populares en este momento a nivel global. Agrupa por categoría (Tecnología, Ciencia, Entretenimiento, Política, etc.)."
    gemini_result = _gemini_generate(prompt)
    if gemini_result:
        _cache_set(cache_key, gemini_result)
        return gemini_result

    results = _ddg_search("trending topics today", max_results=10)
    formatted = _format_ddg("Tendencias", results)
    _cache_set(cache_key, formatted)
    return formatted

def _webpage_summary(url: str) -> str:
    cache_key = f"summary_{url}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        prompt = f"Resume el siguiente contenido web en 3-4 puntos clave (máx 200 palabras):\n\n{text[:3000]}"
        summary = _gemini_generate(prompt)
        if summary:
            result = f"📄 Resumen de {url}:\n{summary}"
        else:
            result = f"📄 Extracto de {url}:\n\n{text[:800]}..."
        _cache_set(cache_key, result)
        return result

    except Exception as e:
        return f"Error al obtener la página: {e}"

def _translate_search(query: str, target_lang: str = "es") -> str:
    prompt = f"Traduce al {target_lang} esta consulta de búsqueda: '{query}'. Devuelve solo la traducción."
    translated = _gemini_generate(prompt)
    if translated:
        return _search(translated)
    else:
        return _search(query)

def _calculate(expression: str) -> str:
    try:
        allowed = set("0123456789+-*/().%^ ")
        if not all(c in allowed for c in expression):
            return "Expresión contiene caracteres no permitidos."
        expr = expression.replace("^", "**")
        result = eval(expr, {"__builtins__": {}}, {"math": math})
        return f"El resultado de {expression} es {result}"
    except Exception as e:
        return f"Error al calcular: {e}"

# ===== PUNTO DE ENTRADA PRINCIPAL =====
def web_search(
    parameters: Dict[str, Any],
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Punto de entrada principal.
    Modos: search, news, research, price, compare, images, videos, define, trending, summarize, translate, calculate, citations.
    """
    params = parameters or {}
    query = params.get("query", "").strip()
    mode = params.get("mode", "search").lower().strip()
    items = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"
    url = params.get("url", "").strip()
    target_lang = params.get("target_lang", "es").strip()

    if not query and not items and mode not in ("trending", "summarize", "calculate"):
        return "❌ Por favor, proporciona una consulta de búsqueda."

    if items and mode not in ("compare",):
        mode = "compare"

    if player:
        player.write_log(f"[Search:{mode}] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 mode={mode!r}  query={query!r}")

    try:
        if mode == "compare" and items:
            return _compare(items, aspect)
        if mode == "news":
            return _news(query)
        if mode == "research":
            return _research(query)
        if mode == "price":
            return _price(query)
        if mode == "images":
            return _image_search(query)
        if mode == "videos":
            return _video_search(query)
        if mode == "define":
            return _definition(query)
        if mode == "trending":
            return _trending()
        if mode == "summarize":
            if url:
                return _webpage_summary(url)
            else:
                return "❌ Para resumir, proporciona una URL en el parámetro 'url'."
        if mode == "translate":
            if query:
                return _translate_search(query, target_lang)
            else:
                return "❌ Para traducir, proporciona una consulta en 'query'."
        if mode == "calculate":
            if query:
                return _calculate(query)
            else:
                return "❌ Para calcular, proporciona una expresión en 'query'."
        if mode == "citations":
            # Nuevo modo: devuelve resultados con citas y fuentes
            data = _ddg_search_with_citations(query, max_results=8)
            if data["results"]:
                return _format_citations(query, data)
            return f"No se encontraron resultados con citas para: {query}"
        # Modo predeterminado
        return _search(query)

    except Exception as e:
        print(f"[WebSearch] ❌ Error en {mode}: {e}")
        return f"❌ Búsqueda fallida: {e}"

# ===== ALIAS PARA COMPATIBILIDAD CON main.py =====
def web_search_action(parameters: Dict[str, Any], player=None) -> str:
    return web_search(parameters, player=player)

# ===== PRUEBAS =====
if __name__ == "__main__":
    print("🌐 Probando web_search...")
    tests = [
        {"query": "inteligencia artificial", "mode": "search"},
        {"query": "tecnología", "mode": "news"},
        {"query": "Python", "mode": "research"},
        {"query": "iPhone 15", "mode": "price"},
        {"items": ["Python", "JavaScript"], "mode": "compare", "aspect": "popularidad"},
        {"query": "gatos", "mode": "images"},
        {"query": "tutorial Python", "mode": "videos"},
        {"query": "serendipity", "mode": "define"},
        {"mode": "trending"},
        {"mode": "summarize", "url": "https://www.python.org"},
        {"query": "hello world", "mode": "translate", "target_lang": "es"},
        {"query": "2 + 2 * 5", "mode": "calculate"},
        {"query": "cambio climático", "mode": "citations"},
    ]
    for test in tests:
        print("\n" + "="*60)
        print(f"Modo: {test.get('mode', 'search')}")
        result = web_search(test)
        print(result[:500] + ("..." if len(result) > 500 else ""))