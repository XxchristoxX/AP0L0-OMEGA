# secure_browser.py - VERSIÓN COMPLETA PARA AP0L0

import os
import sys
import time
import threading
import re
import urllib.parse
import ctypes
from ctypes import wintypes

try:
    import webview
except ImportError:
    webview = None
    print("[SecureBrowser] webview no instalado. pip install pywebview")

# ===== CONSTANTES WINDOWS =====
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_OVERLAPPEDWINDOW = 0x00CF0000
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

# ===== GLOBALES =====
_browser_window = None
_main_hwnd = None
_browser_hwnd = None
_is_docked = False
_default_url = "https://www.google.com"
_main_webview_window = None

# ===== SCRIPTS DE INYECCIÓN =====

ADBLOCK_JS = """
(function() {
    function cleanPageAds() {
        const adSelectors = [
            '.adsbygoogle', 'iframe[id^="google_ads"]', '.ad-banner',
            '.ads-container', '#ad-slot', '.ad-box',
            'ytd-ad-slot-renderer', 'ytd-promoted-sparkles-web-renderer',
            'ytd-promoted-video-renderer', '.ytp-ad-overlay-container',
            '.video-ads', '.ytp-ad-module', 'div[id^="ad-text:"]',
            'ytd-companion-ad-renderer'
        ];
        
        adSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (el && el.id !== 'jarvis-browser-toolbar') {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.opacity = '0';
                }
            });
        });

        // Bloqueo de anuncios en YouTube
        const video = document.querySelector('video');
        const isAdShowing = document.querySelector('.ad-showing, .ytp-ad-player-overlay, .ytp-ad-image-overlay, .ytp-ad-text-overlay');
        
        if (video && isAdShowing) {
            video.playbackRate = 16.0;
            video.muted = true;
            if (video.duration && video.currentTime < video.duration) {
                video.currentTime = video.duration - 0.1;
            }
        }

        // Saltar anuncios
        const skipButtons = [
            '.ytp-ad-skip-button', 
            '.ytp-ad-skip-button-modern',
            '.ytp-ad-skip-button-slot .ytp-ad-skip-button',
            '[class*="skip-button"]',
            '.ytp-ad-skip-button-text'
        ];
        skipButtons.forEach(selector => {
            const btn = document.querySelector(selector);
            if (btn && btn.style.display !== 'none') {
                btn.click();
            }
        });
    }

    cleanPageAds();
    if (!window._jarvisAdBlockInterval) {
        window._jarvisAdBlockInterval = setInterval(cleanPageAds, 300);
    }
})();
"""

TOOLBAR_JS = """
(function() {
    const stopMedia = () => {
        try {
            const findMedia = (root) => {
                let list = Array.from(root.querySelectorAll('video, audio'));
                root.querySelectorAll('*').forEach(el => {
                    try {
                        if (el.shadowRoot) {
                            list = list.concat(findMedia(el.shadowRoot));
                        }
                    } catch(e){}
                });
                return list;
            };
            findMedia(document).forEach(el => {
                try {
                    el.pause();
                    el.src = '';
                    el.load();
                } catch(e){}
            });
        } catch(e){}
    };

    function ensureToolbar() {
        // Detectar cambios de URL
        if (!window._jarvisLastUrl) {
            window._jarvisLastUrl = window.location.href;
        }
        if (window.location.href !== window._jarvisLastUrl) {
            const wasWatch = window._jarvisLastUrl.includes('/watch');
            const isWatch = window.location.href.includes('/watch');
            if (wasWatch && !isWatch) {
                stopMedia();
            }
            window._jarvisLastUrl = window.location.href;
        }

        let tb = document.getElementById('jarvis-browser-toolbar');
        if (tb) {
            const input = document.getElementById('jarvis-browser-toolbar-input');
            if (input && input !== document.activeElement && input.value !== window.location.href) {
                input.value = window.location.href;
            }
            // Asegurar que el body está desplazado
            if (document.body && document.body.style.transform !== 'translateY(40px)') {
                document.body.style.transform = 'translateY(40px)';
                document.body.style.height = 'calc(100% - 40px)';
                document.body.style.boxSizing = 'border-box';
            }
            return;
        }

        if (!document.body || !document.documentElement) return;

        // Desplazar el body para la barra
        document.body.style.transform = 'translateY(40px)';
        document.body.style.height = 'calc(100% - 40px)';
        document.body.style.boxSizing = 'border-box';

        // Crear barra de herramientas
        tb = document.createElement('div');
        tb.id = 'jarvis-browser-toolbar';
        tb.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 40px;
            background: rgba(10, 10, 20, 0.95);
            border-bottom: 1px solid rgba(0, 229, 255, 0.3);
            box-shadow: 0 3px 15px rgba(0,0,0,0.6);
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 15px; z-index: 999999999;
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #fff; box-sizing: border-box; user-select: none;
        `;

        // Grupo de navegación
        const navGroup = document.createElement('div');
        navGroup.style.cssText = 'display:flex; gap:8px; align-items:center;';

        const createBtn = (icon, title, action) => {
            const btn = document.createElement('button');
            btn.textContent = icon;
            btn.title = title;
            btn.style.cssText = 'background:rgba(0,229,255,0.05); border:1px solid rgba(0,229,255,0.2); border-radius:4px; color:#00e5ff; cursor:pointer; font-size:14px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; transition: all 0.2s;';
            btn.onmouseover = () => { btn.style.background = 'rgba(0,229,255,0.2)'; btn.style.borderColor = '#00e5ff'; };
            btn.onmouseout = () => { btn.style.background = 'rgba(0,229,255,0.05)'; btn.style.borderColor = 'rgba(0,229,255,0.2)'; };
            btn.onclick = action;
            return btn;
        };

        const btnBack = createBtn('◀', 'Atrás', () => { stopMedia(); window.history.back(); });
        const btnForward = createBtn('▶', 'Adelante', () => { stopMedia(); window.history.forward(); });
        const btnReload = createBtn('🔄', 'Recargar', () => { stopMedia(); window.location.reload(); });
        const btnGoogle = createBtn('🔍', 'Google', () => { stopMedia(); window.location.href = 'https://www.google.com'; });
        const btnYouTube = createBtn('📺', 'YouTube', () => { stopMedia(); window.location.href = 'https://www.youtube.com'; });

        navGroup.appendChild(btnBack);
        navGroup.appendChild(btnForward);
        navGroup.appendChild(btnReload);
        navGroup.appendChild(btnGoogle);
        navGroup.appendChild(btnYouTube);

        // Barra de direcciones
        const addressGroup = document.createElement('div');
        addressGroup.style.cssText = 'flex:1; margin:0 15px; max-width:700px;';

        const input = document.createElement('input');
        input.id = 'jarvis-browser-toolbar-input';
        input.type = 'text';
        input.placeholder = 'URL o búsqueda en Google...';
        input.value = window.location.href;
        input.style.cssText = 'width:100%; height:28px; border-radius:14px; border:1px solid rgba(0,229,255,0.3); background:rgba(15,15,25,0.9); color:#fff; padding:0 15px; font-size:12px; outline:none; box-sizing:border-box; transition: border-color 0.2s;';
        input.onfocus = () => { input.style.borderColor = '#00e5ff'; input.select(); };
        input.onblur = () => { input.style.borderColor = 'rgba(0,229,255,0.3)'; };
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                if (window.pywebview && window.pywebview.api) {
                    stopMedia();
                    window.pywebview.api.navigate_to(input.value);
                }
            }
        };
        addressGroup.appendChild(input);

        // Grupo de sistema
        const sysGroup = document.createElement('div');
        sysGroup.style.cssText = 'display:flex; gap:10px; align-items:center;';

        const btnDock = document.createElement('button');
        btnDock.id = 'jarvis-btn-dock';
        btnDock.textContent = window._isBrowserDocked ? '⚡ DESANCRA' : '🔗 ANCORAR';
        btnDock.title = 'Anclar o Desanclar la ventana';
        btnDock.style.cssText = 'background:rgba(0,229,255,0.1); border:1px solid #00e5ff; border-radius:4px; color:#00e5ff; cursor:pointer; font-size:11px; font-weight:bold; height:28px; padding:0 12px; transition: all 0.2s;';
        btnDock.onmouseover = () => { btnDock.style.background = '#00e5ff'; btnDock.style.color = '#000'; };
        btnDock.onmouseout = () => { btnDock.style.background = 'rgba(0,229,255,0.1)'; btnDock.style.color = '#00e5ff'; };
        btnDock.onclick = () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.toggle_dock();
            }
        };

        const btnClose = document.createElement('button');
        btnClose.textContent = '❌';
        btnClose.title = 'Cerrar navegador';
        btnClose.style.cssText = 'background:rgba(255,59,48,0.1); border:1px solid #ff3b30; border-radius:4px; color:#ff3b30; cursor:pointer; font-size:12px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; transition: all 0.2s;';
        btnClose.onmouseover = () => { btnClose.style.background = '#ff3b30'; btnClose.style.color = '#fff'; };
        btnClose.onmouseout = () => { btnClose.style.background = 'rgba(255,59,48,0.1)'; btnClose.style.color = '#ff3b30'; };
        btnClose.onclick = () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.close_browser();
            }
        };

        sysGroup.appendChild(btnDock);
        sysGroup.appendChild(btnClose);

        tb.appendChild(navGroup);
        tb.appendChild(addressGroup);
        tb.appendChild(sysGroup);
        document.documentElement.appendChild(tb);
    }

    try { ensureToolbar(); } catch(e) { console.error("Toolbar error:", e); }
    if (!window._jarvisToolbarInterval) {
        window._jarvisToolbarInterval = setInterval(() => {
            try { ensureToolbar(); } catch(e) { console.error("Toolbar interval error:", e); }
        }, 500);
    }
})();
"""


# ===== API PARA PYWEBVIEW =====

class BrowserAPI:
    """API expuesta a JavaScript."""
    
    def navigate_to(self, query):
        """Navega a una URL o realiza una búsqueda."""
        url = _format_url(query)
        global _browser_window
        if _browser_window:
            # Detener medios antes de navegar
            try:
                _browser_window.evaluate_js("""
                    document.querySelectorAll('video, audio').forEach(el => {
                        el.pause(); el.src = ''; el.load();
                    });
                """)
            except Exception:
                pass
            _browser_window.load_url(url)
    
    def toggle_dock(self):
        """Alterna entre anclado y desanclado."""
        global _is_docked
        if _is_docked:
            undock_browser()
        else:
            dock_browser()
    
    def close_browser(self):
        """Cierra el navegador."""
        close_browser_window()


# ===== FUNCIONES DE UTILIDAD =====

def _format_url(query):
    """Formatea una URL o búsqueda."""
    query = query.strip()
    if not query:
        return _default_url
    
    # Si ya es una URL con protocolo
    if re.match(r'^https?://', query):
        return query
    
    # Si es un dominio (ej: google.com)
    if re.match(r'^[\w\-]+(\.[\w\-]+)+', query):
        return "https://" + query
    
    # Si es una IP o localhost
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}(:\d+)?$', query) or query.startswith("localhost"):
        if not query.startswith("http"):
            return "http://" + query
        return query
    
    # Búsqueda en Google
    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"


def _find_hwnd():
    """Encuentra la ventana del navegador."""
    if not IS_WINDOWS:
        return None
    
    for _ in range(50):
        hwnd = ctypes.windll.user32.FindWindowW(None, "Navigator Seguro J.A.R.V.I.S")
        if hwnd:
            return hwnd
        time.sleep(0.1)
    return None


def center_and_own():
    """Centra el navegador y lo asocia a la ventana principal."""
    global _browser_hwnd, _main_hwnd
    
    if not _browser_hwnd or not _main_hwnd:
        return
    
    # Obtener dimensiones de la ventana principal
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(_main_hwnd, ctypes.byref(rect))
    main_w = rect.right - rect.left
    main_h = rect.bottom - rect.top
    
    browser_w = min(1024, int(main_w * 0.8))
    browser_h = min(768, int(main_h * 0.8))
    x = rect.left + (main_w - browser_w) // 2
    y = rect.top + (main_h - browser_h) // 2
    
    # Establecer owner
    ctypes.windll.user32.SetWindowLongW(_browser_hwnd, -8, _main_hwnd)
    
    # Posicionar
    ctypes.windll.user32.SetWindowPos(
        _browser_hwnd, 0, x, y, browser_w, browser_h,
        SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )


def dock_browser():
    """Ancla el navegador a la derecha."""
    global _is_docked, _browser_hwnd, _main_hwnd
    
    if not _browser_hwnd or not _main_hwnd:
        return
    
    _is_docked = True
    
    # Adjuntar a la ventana padre
    ctypes.windll.user32.SetParent(_browser_hwnd, _main_hwnd)
    
    # Quitar bordes para hacerlo hijo
    style = ctypes.windll.user32.GetWindowLongW(_browser_hwnd, GWL_STYLE)
    style = (style & ~WS_POPUP) | WS_CHILD | WS_VISIBLE
    ctypes.windll.user32.SetWindowLongW(_browser_hwnd, GWL_STYLE, style)
    
    # Redimensionar
    resize_docked()
    
    # Actualizar toolbar
    if _browser_window:
        _browser_window.evaluate_js("window._isBrowserDocked = true;")
    if _main_webview_window:
        _main_webview_window.evaluate_js("document.body.classList.add('browser-open');")


def undock_browser():
    """Desancla el navegador."""
    global _is_docked, _browser_hwnd
    
    if not _browser_hwnd:
        return
    
    _is_docked = False
    
    # Desadjuntar
    ctypes.windll.user32.SetParent(_browser_hwnd, 0)
    
    # Restaurar bordes
    style = ctypes.windll.user32.GetWindowLongW(_browser_hwnd, GWL_STYLE)
    style = (style & ~WS_CHILD) | WS_POPUP | WS_OVERLAPPEDWINDOW | WS_VISIBLE
    ctypes.windll.user32.SetWindowLongW(_browser_hwnd, GWL_STYLE, style)
    
    # Centrar
    center_and_own()
    
    if _browser_window:
        _browser_window.evaluate_js("window._isBrowserDocked = false;")
    if _main_webview_window:
        _main_webview_window.evaluate_js("document.body.classList.remove('browser-open');")


def resize_docked():
    """Redimensiona el navegador anclado."""
    if not _is_docked or not _browser_hwnd or not _main_hwnd:
        return
    
    rect = wintypes.RECT()
    ctypes.windll.user32.GetClientRect(_main_hwnd, ctypes.byref(rect))
    main_w = rect.right - rect.left
    main_h = rect.bottom - rect.top
    
    width = int(main_w * 0.45)
    x = main_w - width
    y = 0
    
    ctypes.windll.user32.SetWindowPos(
        _browser_hwnd, 0, x, y, width, main_h,
        SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )


def close_browser_window():
    """Cierra el navegador."""
    global _browser_window, _browser_hwnd, _is_docked
    
    if _browser_window:
        try:
            _browser_window.evaluate_js("""
                document.querySelectorAll('video, audio').forEach(el => {
                    el.pause(); el.src = ''; el.load();
                });
            """)
        except Exception:
            pass
        try:
            _browser_window.destroy()
        except Exception as e:
            print(f"[SecureBrowser] Error cerrando: {e}")
    
    _browser_window = None
    _browser_hwnd = None
    _is_docked = False


def trigger_browser(url_or_search=None, main_window_ref=None):
    """Abre el navegador seguro."""
    global _browser_window, _browser_hwnd, _main_webview_window, _is_docked, _main_hwnd
    
    if webview is None:
        print("[SecureBrowser] webview no instalado. pip install pywebview")
        return
    
    if main_window_ref:
        _main_webview_window = main_window_ref
        # Obtener HWND de la ventana principal
        _main_hwnd = ctypes.windll.user32.FindWindowW(None, "J.A.R.V.I.S")
    
    target_url = _format_url(url_or_search) if url_or_search else _default_url
    
    if _browser_window:
        _browser_window.load_url(target_url)
        if _browser_hwnd:
            ctypes.windll.user32.SetForegroundWindow(_browser_hwnd)
        return
    
    _is_docked = False
    
    _browser_window = webview.create_window(
        title="Navigator Seguro J.A.R.V.I.S",
        url=target_url,
        width=1024,
        height=768,
        frameless=False,
        background_color="#0a0a0f",
        js_api=BrowserAPI()
    )
    
    _browser_window.events.loaded += _on_loaded
    _browser_window.events.closed += _on_closed
    
    # Buscar HWND en un hilo separado
    threading.Thread(target=lambda: _find_hwnd_and_center(), daemon=True).start()


def _find_hwnd_and_center():
    global _browser_hwnd
    _browser_hwnd = _find_hwnd()
    if _browser_hwnd:
        center_and_own()


def _on_loaded():
    """Inyecta scripts al cargar la página."""
    if _browser_window:
        try:
            _browser_window.evaluate_js(ADBLOCK_JS)
        except Exception as e:
            print(f"[SecureBrowser] Error inyectando adblock: {e}")
        try:
            _browser_window.evaluate_js(TOOLBAR_JS)
        except Exception as e:
            print(f"[SecureBrowser] Error inyectando toolbar: {e}")


def _on_closed():
    global _browser_window, _browser_hwnd, _is_docked
    _browser_window = None
    _browser_hwnd = None
    _is_docked = False
    if _main_webview_window:
        try:
            _main_webview_window.evaluate_js("document.body.classList.remove('browser-open');")
        except Exception:
            pass


# ===== FUNCIÓN PARA AP0L0 =====

def secure_browser(params, player=None, speak=None):
    """
    Función de punto de entrada para AP0L0.
    
    Parámetros:
        action (str): "open", "close", "toggle_dock"
        url (str): URL o búsqueda (para open)
    """
    action = params.get("action", "open").lower()
    url = params.get("url", "").strip()
    
    if action == "open":
        if speak:
            speak("Abriendo navegador seguro...")
        trigger_browser(url if url else None)
        return "Navegador seguro abierto."
    
    elif action == "close":
        close_browser_window()
        if speak:
            speak("Navegador cerrado.")
        return "Navegador cerrado."
    
    elif action == "toggle_dock":
        if _is_docked:
            undock_browser()
            return "Navegador desanclado."
        else:
            dock_browser()
            return "Navegador anclado."
    
    else:
        return f"Acción '{action}' no soportada. Usa: open, close, toggle_dock"


# ===== CONSTANTES DE SISTEMA =====
IS_WINDOWS = sys.platform == "win32"