# src/actions/secure_browser.py
"""
Navegador seguro para AP0L0 (PyWebView)
"""

try:
    import webview
    _WEBVIEW_AVAILABLE = True
except ImportError:
    webview = None
    _WEBVIEW_AVAILABLE = False
import webbrowser
import threading
import time
import re
import urllib.parse
import ctypes
import os

_browser_window = None
_is_docked = False
_main_hwnd = None
_browser_hwnd = None
_default_url = "https://www.google.com"


def format_url_or_search(query):
    query = query.strip()
    if not query:
        return _default_url
    # Si parece URL
    if re.match(r'^(https?://)?[\w\-\.]+\.\w+', query):
        if not query.startswith(("http://", "https://")):
            return "https://" + query
        return query
    return "https://www.google.com/search?q=" + urllib.parse.quote(query)


def trigger_browser(url_or_search=None, main_window_ref=None):
    global _browser_window
    target_url = _default_url
    if url_or_search:
        target_url = format_url_or_search(url_or_search)
    if not _WEBVIEW_AVAILABLE:
        webbrowser.open(target_url)
        return False
    if _browser_window is not None:
        _browser_window.load_url(target_url)
        return
    _browser_window = webview.create_window(
        title="Navegador Seguro AP0L0",
        url=target_url,
        width=1024,
        height=768,
        resizable=True,
        fullscreen=False
    )
    threading.Thread(target=webview.start, daemon=True).start()


def dock_browser():
    global _is_docked
    _is_docked = True
    # En pywebview no hay anclaje real; simulamos con mensaje
    if _browser_window:
        _browser_window.evaluate_js("document.body.style.border='2px solid cyan'")
        _browser_window.evaluate_js("alert('Modo anclado (simulado)')")


def undock_browser():
    global _is_docked
    _is_docked = False
    if _browser_window:
        _browser_window.evaluate_js("document.body.style.border='none'")
        _browser_window.evaluate_js("alert('Modo desanclado')")


def close_browser_window():
    global _browser_window
    if _browser_window:
        try:
            _browser_window.destroy()
        except:
            pass
        _browser_window = None


# ===== FUNCIÓN EXPORTABLE =====

async def secure_browser(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "open")
    url = params.get("url", "")
    if action == "open":
        embedded = trigger_browser(url)
        return "Navegador seguro abierto." if embedded else "Navegador del sistema abierto (pywebview no instalado)."
    elif action == "close":
        close_browser_window()
        return "Navegador cerrado."
    elif action == "dock":
        dock_browser()
        return "Navegador anclado (simulado)."
    elif action == "undock":
        undock_browser()
        return "Navegador desanclado (simulado)."
    else:
        return "Acción no soportada."
