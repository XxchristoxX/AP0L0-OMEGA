# -*- coding: utf-8 -*-
import webview
import ctypes
import threading
import time
import urllib.parse
import re
import os

# --- CONTEXTO Y CONSTANTES WINDOWS ---
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_OVERLAPPEDWINDOW = 0x00CF0000

SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

# Variables globales
_ventana_navegador = None
_hwnd_principal = None
_hwnd_navegador = None
_está_anclado = False
_url_por_defecto = "https://www.techenclair.fr"
_ventana_webview_principal = None  # Referencia a la ventana principal de JARVIS pywebview

# --- CÓDIGO DE INYECCIÓN JS (BLOQUEO DE ANUNCIOS + BARRA DE HERRAMIENTAS) ---

ADBLOCK_JS = """
(function() {
    function limpiarAnunciosPagina() {
        // Selectores de banners publicitarios comunes
        const selectoresAnuncios = [
            '.adsbygoogle', 'iframe[id^="google_ads"]', '.ad-banner', 
            '.ads-container', '#ad-slot', '.ad-box', '.ytp-ad-overlay-container',
            'ytd-ad-slot-renderer', 'ytd-companion-ad-renderer',
            'ytd-promoted-sparkles-web-renderer', 'ytd-promoted-video-renderer',
            '.ytd-ad-slot-renderer', '.video-ads', '.ytp-ad-module', 'div[id^="ad-text:"]'
        ];
        selectoresAnuncios.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (el && el.id !== 'jarvis-browser-toolbar') {
                    el.style.display = 'none';
                }
            });
        });

        // Bloqueador / Acelerador de anuncios de YouTube
        const video = document.querySelector('video');
        const anuncioVisible = document.querySelector('.ad-showing, .ytp-ad-player-overlay, .ytp-ad-image-overlay');
        
        if (video && anuncioVisible) {
            video.playbackRate = 16.0;
            video.muted = true;
            if (video.duration && video.currentTime < video.duration) {
                // Avanzar directamente al final del anuncio
                video.currentTime = video.duration - 0.1;
            }
        }

        // Clic automático en "Saltar anuncio"
        const botonesSaltar = [
            '.ytp-ad-skip-button', 
            '.ytp-ad-skip-button-modern', 
            '.ytp-ad-skip-button-slot .ytp-ad-skip-button',
            '[class*="skip-button"]',
            '.ytp-ad-skip-button-text'
        ];
        botonesSaltar.forEach(selector => {
            const btn = document.querySelector(selector);
            if (btn && btn.style.display !== 'none') {
                btn.click();
            }
        });
    }

    // Ejecutar inmediatamente y luego cada 250ms
    limpiarAnunciosPagina();
    if (!window._jarvisAdBlockInterval) {
        window._jarvisAdBlockInterval = setInterval(limpiarAnunciosPagina, 250);
    }
})();
"""

BARRA_HERRAMIENTAS_JS = """
(function() {
    const detenerMultimedia = () => {
        try {
            const buscarMultimedia = (raiz) => {
                let lista = Array.from(raiz.querySelectorAll('video, audio'));
                raiz.querySelectorAll('*').forEach(el => {
                    try {
                        if (el.shadowRoot) {
                            lista = lista.concat(buscarMultimedia(el.shadowRoot));
                        }
                    } catch(e){}
                });
                return lista;
            };
            buscarMultimedia(document).forEach(el => {
                try {
                    el.pause();
                    el.src = '';
                    el.load();
                } catch(e){}
            });
        } catch(e){}
    };

    function asegurarBarraHerramientas() {
        // Detectar cambios de URL del lado del cliente (SPA)
        if (!window._jarvisLastUrl) {
            window._jarvisLastUrl = window.location.href;
        }
        if (window.location.href !== window._jarvisLastUrl) {
            const eraWatch = window._jarvisLastUrl.includes('/watch');
            const esWatch = window.location.href.includes('/watch');
            if (eraWatch && !esWatch) {
                detenerMultimedia();
            }
            window._jarvisLastUrl = window.location.href;
        }

        let tb = document.getElementById('jarvis-browser-toolbar');
        if (tb) {
            // Actualizar la dirección si ha cambiado
            const input = document.getElementById('jarvis-browser-toolbar-input');
            if (input && input !== document.activeElement && input.value !== window.location.href) {
                input.value = window.location.href;
            }
            // Asegurar que el desplazamiento del body se aplica
            if (document.body && document.body.style.transform !== 'translateY(40px)') {
                document.body.style.setProperty('transform', 'translateY(40px)', 'important');
                document.body.style.setProperty('height', 'calc(100% - 40px)', 'important');
                document.body.style.setProperty('box-sizing', 'border-box', 'important');
            }
            return;
        }

        if (!document.body || !document.documentElement) return;

        // Desplazar el body para no ocultar la parte superior con elementos fijos de la página
        document.body.style.setProperty('transform', 'translateY(40px)', 'important');
        document.body.style.setProperty('height', 'calc(100% - 40px)', 'important');
        document.body.style.setProperty('box-sizing', 'border-box', 'important');

        // Crear la barra
        tb = document.createElement('div');
        tb.id = 'jarvis-browser-toolbar';
        tb.style.position = 'fixed';
        tb.style.top = '0';
        tb.style.left = '0';
        tb.style.width = '100%';
        tb.style.height = '40px';
        tb.style.backgroundColor = 'rgba(10, 10, 20, 0.95)';
        tb.style.borderBottom = '1px solid rgba(0, 229, 255, 0.3)';
        tb.style.boxShadow = '0 3px 15px rgba(0,0,0,0.6)';
        tb.style.display = 'flex';
        tb.style.alignItems = 'center';
        tb.style.justifyContent = 'space-between';
        tb.style.padding = '0 15px';
        tb.style.zIndex = '999999999';
        tb.style.fontFamily = 'Segoe UI, Arial, sans-serif';
        tb.style.color = '#fff';
        tb.style.boxSizing = 'border-box';
        tb.style.userSelect = 'none';

        // Grupo de botones de navegación
        const grupoNav = document.createElement('div');
        grupoNav.style.display = 'flex';
        grupoNav.style.gap = '8px';
        grupoNav.style.alignItems = 'center';

        const crearBtn = (icono, titulo, accion) => {
            const btn = document.createElement('button');
            btn.textContent = icono;
            btn.title = titulo;
            btn.style.cssText = 'background:rgba(0,229,255,0.05); border:1px solid rgba(0,229,255,0.2); border-radius:4px; color:#00e5ff; cursor:pointer; font-size:14px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; transition: all 0.2s;';
            btn.onmouseover = () => { btn.style.background = 'rgba(0,229,255,0.2)'; btn.style.borderColor = '#00e5ff'; };
            btn.onmouseout = () => { btn.style.background = 'rgba(0,229,255,0.05)'; btn.style.borderColor = 'rgba(0,229,255,0.2)'; };
            btn.onclick = accion;
            return btn;
        };

        const btnAtras = crearBtn('◀', 'Atrás', () => { detenerMultimedia(); window.history.back(); });
        const btnAdelante = crearBtn('▶', 'Adelante', () => { detenerMultimedia(); window.history.forward(); });
        const btnRecargar = crearBtn('🔄', 'Recargar', () => { detenerMultimedia(); window.location.reload(); });
        const btnGoogle = crearBtn('🔍', 'Google', () => { detenerMultimedia(); window.location.href = 'https://www.google.com'; });
        const btnYouTube = crearBtn('📺', 'YouTube', () => { detenerMultimedia(); window.location.href = 'https://www.youtube.com'; });

        grupoNav.appendChild(btnAtras);
        grupoNav.appendChild(btnAdelante);
        grupoNav.appendChild(btnRecargar);
        grupoNav.appendChild(btnGoogle);
        grupoNav.appendChild(btnYouTube);

        // Grupo de barra de direcciones
        const grupoDirecciones = document.createElement('div');
        grupoDirecciones.style.flex = '1';
        grupoDirecciones.style.margin = '0 15px';
        grupoDirecciones.style.maxWidth = '700px';

        const input = document.createElement('input');
        input.id = 'jarvis-browser-toolbar-input';
        input.type = 'text';
        input.placeholder = 'Introduzca una URL o realice una búsqueda en Google...';
        input.value = window.location.href;
        input.style.cssText = 'width:100%; height:28px; border-radius:14px; border:1px solid rgba(0, 229, 255, 0.3); background:rgba(15,15,25,0.9); color:#fff; padding:0 15px; font-size:12px; outline:none; box-sizing:border-box; transition: border-color 0.2s;';
        input.onfocus = () => { input.style.borderColor = '#00e5ff'; input.select(); };
        input.onblur = () => { input.style.borderColor = 'rgba(0, 229, 255, 0.3)'; };
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                if (window.pywebview && window.pywebview.api) {
                    detenerMultimedia();
                    window.pywebview.api.navigate_to(input.value);
                }
            }
        };
        grupoDirecciones.appendChild(input);

        // Grupo de botones del sistema
        const grupoSistema = document.createElement('div');
        grupoSistema.style.display = 'flex';
        grupoSistema.style.gap = '10px';
        grupoSistema.style.alignItems = 'center';

        const btnAnclar = document.createElement('button');
        btnAnclar.id = 'jarvis-btn-anclar';
        btnAnclar.textContent = window._isBrowserDocked ? '⚡ DESANCLAR' : '🔗 ANCLAR';
        btnAnclar.title = 'Anclar o desanclar la ventana';
        btnAnclar.style.cssText = 'background:rgba(0, 229, 255, 0.1); border:1px solid #00e5ff; border-radius:4px; color:#00e5ff; cursor:pointer; font-size:11px; font-weight:bold; height:28px; padding:0 12px; transition: all 0.2s;';
        btnAnclar.onmouseover = () => { btnAnclar.style.background = '#00e5ff'; btnAnclar.style.color = '#000'; };
        btnAnclar.onmouseout = () => { btnAnclar.style.background = 'rgba(0, 229, 255, 0.1)'; btnAnclar.style.color = '#00e5ff'; };
        btnAnclar.onclick = () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.toggle_dock();
            }
        };

        const btnCerrar = document.createElement('button');
        btnCerrar.textContent = '❌';
        btnCerrar.title = 'Cerrar el navegador';
        btnCerrar.style.cssText = 'background:rgba(255,59,48,0.1); border:1px solid #ff3b30; border-radius:4px; color:#ff3b30; cursor:pointer; font-size:12px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; transition: all 0.2s;';
        btnCerrar.onmouseover = () => { btnCerrar.style.background = '#ff3b30'; btnCerrar.style.color = '#fff'; };
        btnCerrar.onmouseout = () => { btnCerrar.style.background = 'rgba(255,59,48,0.1)'; btnCerrar.style.color = '#ff3b30'; };
        btnCerrar.onclick = () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.close_browser();
            }
        };

        grupoSistema.appendChild(btnAnclar);
        grupoSistema.appendChild(btnCerrar);

        tb.appendChild(grupoNav);
        tb.appendChild(grupoDirecciones);
        tb.appendChild(grupoSistema);
        
        // Inyectar en documentElement para evitar ser sobrescrito por Polymer/SPA o afectado por las traducciones del body
        document.documentElement.appendChild(tb);
    }

    // Ejecutar y supervisar cada 500ms
    try {
        asegurarBarraHerramientas();
    } catch(e) {
        console.error("Error de inicialización de la barra de herramientas de Jarvis:", e);
    }
    if (!window._jarvisToolbarInterval) {
        window._jarvisToolbarInterval = setInterval(() => {
            try {
                asegurarBarraHerramientas();
            } catch(e) {
                console.error("Error en el intervalo de la barra de herramientas de Jarvis:", e);
            }
        }, 500);
    }
})();
"""

# --- INTERFAZ JAVASCRIPT DE PYWEBVIEW ---
class BrowserAPI:
    def navigate_to(self, query):
        url = formatear_url_o_busqueda(query)
        global _ventana_navegador
        if _ventana_navegador:
            try:
                _ventana_navegador.evaluate_js(
                    """
                    (function() {
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
                    })();
                    """
                )
            except Exception:
                pass
            _ventana_navegador.load_url(url)
            
    def toggle_dock(self):
        global _está_anclado
        if _está_anclado:
            desanclar_navegador()
        else:
            anclar_navegador()
            
    def close_browser(self):
        cerrar_ventana_navegador()

# --- UTILIDADES Y FORMATEADOR DE URL ---
def formatear_url_o_busqueda(consulta):
    consulta = consulta.strip()
    if not consulta:
        return _url_por_defecto
        
    # Verificar si es una dirección IP local o remota
    patron_ip = re.compile(r'^https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?')
    if patron_ip.match(consulta) or consulta.startswith("localhost") or consulta.startswith("http://localhost"):
        if not consulta.startswith("http"):
            return "http://" + consulta
        return consulta
        
    # URL clásica
    patron_url = re.compile(
        r'^(https?:\/\/)?' # http:// o https://
        r'([\w\d\-_]+\.)+[\w\d\-_]+' # dominio
        r'(:\d+)?(\/[^\s]*)?$', re.IGNORECASE
    )
    if patron_url.match(consulta):
        if not (consulta.startswith("http://") or consulta.startswith("https://")):
            return "https://" + consulta
        return consulta
    else:
        # Búsqueda en Google
        return "https://www.google.com/search?q=" + urllib.parse.quote(consulta)

# --- LÓGICA DE ANCLAJE Y DESANCLAJE ---

def lanzar_navegador(url_o_busqueda=None, ventana_principal_ref=None):
    """Función principal para lanzar el navegador por voz o manualmente."""
    global _ventana_navegador, _hwnd_navegador, _ventana_webview_principal, _está_anclado
    
    if ventana_principal_ref:
        _ventana_webview_principal = ventana_principal_ref
        
    url_destino = _url_por_defecto
    if url_o_busqueda:
        url_destino = formatear_url_o_busqueda(url_o_busqueda)
        
    if _ventana_navegador is not None:
        # Ya abierto, recargar o traer al frente
        print(f"[NAVEGADOR] Navegador ya abierto. Navegando a: {url_destino}")
        _ventana_navegador.load_url(url_destino)
        if _hwnd_navegador:
            ctypes.windll.user32.SetForegroundWindow(_hwnd_navegador)
        return
        
    print(f"[NAVEGADOR] Lanzando el navegador seguro en: {url_destino}")
    _está_anclado = False  # Flotante por defecto al inicio
    
    # Creación de la ventana pywebview (con marcos/ bordes estándar al inicio)
    _ventana_navegador = webview.create_window(
        title="Navegador Seguro J.A.R.V.I.S",
        url=url_destino,
        width=1024,
        height=768,
        frameless=False,
        background_color="#0a0a0f",
        js_api=BrowserAPI()
    )
    
    # Eventos de pywebview
    _ventana_navegador.events.loaded += _al_cargar_navegador
    _ventana_navegador.events.closed += _al_cerrar_navegador
    
    # Lanzar la búsqueda de HWND y el centrado/anclaje
    threading.Thread(target=_buscar_hwnd_y_anclar_bucle, daemon=True).start()

def _buscar_hwnd_y_anclar_bucle():
    global _hwnd_navegador, _hwnd_principal
    
    # Encontrar la ventana principal de J.A.R.V.I.S
    _hwnd_principal = ctypes.windll.user32.FindWindowW(None, "J.A.R.V.I.S")
    if not _hwnd_principal:
        print("[NAVEGADOR] ¡Ventana principal de J.A.R.V.I.S no encontrada!")
        
    # Buscar la nueva ventana durante 5 segundos máximo
    for _ in range(50):
        hwnd = ctypes.windll.user32.FindWindowW(None, "Navegador Seguro J.A.R.V.I.S")
        if hwnd:
            _hwnd_navegador = hwnd
            print(f"[NAVEGADOR] HWND del navegador encontrado: {_hwnd_navegador}")
            # Centrar la ventana y asociarla como ventana propietaria (owned)
            centrar_y_propietario_navegador()
            break
        time.sleep(0.1)

def anclar_navegador():
    """Ancla el navegador a la derecha de la interfaz principal."""
    global _está_anclado, _hwnd_navegador, _hwnd_principal, _ventana_navegador
    if not _hwnd_navegador or not _hwnd_principal:
        return
        
    _está_anclado = True
    print("[NAVEGADOR] Anclando el navegador en la aplicación principal.")
    
    # 1. Adjuntar a la ventana padre J.A.R.V.I.S
    ctypes.windll.user32.SetParent(_hwnd_navegador, _hwnd_principal)
    
    # 2. Eliminar bordes, menús del sistema, etc., para convertirla en una ventana hija (WS_CHILD)
    estilo = ctypes.windll.user32.GetWindowLongW(_hwnd_navegador, GWL_STYLE)
    estilo = (estilo & ~WS_POPUP & ~WS_OVERLAPPEDWINDOW) | WS_CHILD
    ctypes.windll.user32.SetWindowLongW(_hwnd_navegador, GWL_STYLE, estilo)
    
    # 3. Actualizar tamaño y posición del anclaje
    redimensionar_ventana_anclada()
    
    # 4. Sincronizar el estado con el HUD principal
    try:
        from main2 import enviar_difusion_web_sync
        enviar_difusion_web_sync({"action": "browser_state", "state": "docked"})
    except Exception as e:
        print(f"[NAVEGADOR] Error al difundir el estado: {e}")
        
    if _ventana_webview_principal:
        _ventana_webview_principal.evaluate_js("if(window.updateBrowserUIState) { window.updateBrowserUIState('docked'); } else { document.body.classList.add('browser-open'); }")
        
    # 5. Actualizar la etiqueta del botón de desanclaje en la barra flotante
    if _ventana_navegador:
        _ventana_navegador.evaluate_js("window._isBrowserDocked = true; if(document.getElementById('jarvis-btn-anclar')) document.getElementById('jarvis-btn-anclar').innerText = '⚡ DESANCLAR';")

def centrar_y_propietario_navegador():
    """Centra el navegador respecto a la ventana principal y define JARVIS como propietario (owner)."""
    global _hwnd_navegador, _hwnd_principal, _ventana_navegador, _está_anclado
    if not _hwnd_navegador:
        return
        
    _está_anclado = False
    print("[NAVEGADOR] Centrando el navegador y enlazando propiedad (owner).")
    
    # 1. Obtener las dimensiones de la ventana principal
    rect = RECT()
    if _hwnd_principal:
        ctypes.windll.user32.GetWindowRect(_hwnd_principal, ctypes.byref(rect))
        ancho_principal = rect.right - rect.left
        alto_principal = rect.bottom - rect.top
        
        ancho_navegador = 1024
        alto_navegador = 768
        
        if ancho_principal < ancho_navegador:
            ancho_navegador = int(ancho_principal * 0.9)
        if alto_principal < alto_navegador:
            alto_navegador = int(alto_principal * 0.9)
            
        x = rect.left + (ancho_principal - ancho_navegador) // 2
        y = rect.top + (alto_principal - alto_navegador) // 2
    else:
        x, y, ancho_navegador, alto_navegador = 150, 150, 1024, 768
        
    # 2. Definir JARVIS como propietario (owner) de la ventana del navegador (GWL_HWNDPARENT = -8)
    if _hwnd_principal:
        ctypes.windll.user32.SetWindowLongW(_hwnd_navegador, -8, _hwnd_principal)
        
    # 3. Posicionar en el centro de la ventana principal
    ctypes.windll.user32.SetWindowPos(
        _hwnd_navegador, 0, x, y, ancho_navegador, alto_navegador,
        SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )
    
    # 4. Sincronizar el estado con el HUD principal
    try:
        from main2 import enviar_difusion_web_sync
        enviar_difusion_web_sync({"action": "browser_state", "state": "undocked"})
    except Exception as e:
        print(f"[NAVEGADOR] Error al difundir el estado: {e}")
        
    if _ventana_webview_principal:
        _ventana_webview_principal.evaluate_js("if(window.updateBrowserUIState) { window.updateBrowserUIState('undocked'); } else { document.body.classList.remove('browser-open'); }")
        
    # 5. Actualizar la etiqueta del botón de desanclaje en la barra flotante
    if _ventana_navegador:
        _ventana_navegador.evaluate_js("window._isBrowserDocked = false; if(document.getElementById('jarvis-btn-anclar')) document.getElementById('jarvis-btn-anclar').innerText = '🔗 ANCLAR';")

def desanclar_navegador():
    """Desancla el navegador en una ventana independiente con sus bordes."""
    global _está_anclado, _hwnd_navegador
    if not _hwnd_navegador:
        return
        
    print("[NAVEGADOR] Desanclando el navegador.")
    
    # 1. Quitar la ventana padre (SetParent a 0 para devolverla al escritorio de Windows)
    ctypes.windll.user32.SetParent(_hwnd_navegador, 0)
    
    # 2. Restaurar los bordes estándar, barra de título, botones maximizar/minimizar (WS_OVERLAPPEDWINDOW)
    estilo = ctypes.windll.user32.GetWindowLongW(_hwnd_navegador, GWL_STYLE)
    estilo = (estilo & ~WS_CHILD) | WS_POPUP | WS_OVERLAPPEDWINDOW | WS_VISIBLE
    ctypes.windll.user32.SetWindowLongW(_hwnd_navegador, GWL_STYLE, estilo)
    
    # 3. Centrar y asociar el propietario (owner)
    centrar_y_propietario_navegador()

def redimensionar_ventana_anclada():
    """Recalcula la posición y el tamaño de la ventana anclada a la derecha."""
    global _está_anclado, _hwnd_navegador, _hwnd_principal
    if not _está_anclado or not _hwnd_navegador or not _hwnd_principal:
        return
        
    rect = RECT()
    ctypes.windll.user32.GetClientRect(_hwnd_principal, ctypes.byref(rect))
    ancho_principal = rect.right - rect.left
    alto_principal = rect.bottom - rect.top
    
    # El navegador ocupa el 45% del ancho total a la derecha
    ancho = int(ancho_principal * 0.45)
    alto = alto_principal
    x = ancho_principal - ancho
    y = 0
    
    ctypes.windll.user32.SetWindowPos(
        _hwnd_navegador, 0, x, y, ancho, alto,
        SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )

def cerrar_ventana_navegador():
    """Cierra correctamente el navegador y restaura la interfaz."""
    global _ventana_navegador
    if _ventana_navegador:
        try:
            _ventana_navegador.evaluate_js(
                """
                (function() {
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
                })();
                """
            )
        except Exception:
            pass
        try:
            _ventana_navegador.destroy()
        except Exception:
            pass

def _al_cargar_navegador():
    """Inyección automática de scripts en cada carga de página."""
    global _ventana_navegador
    if _ventana_navegador:
        print("[NAVEGADOR] Intentando inyectar scripts...")
        try:
            _ventana_navegador.evaluate_js(ADBLOCK_JS)
            print("[NAVEGADOR] Bloqueador de anuncios inyectado.")
        except Exception as e:
            print(f"[NAVEGADOR] Error al inyectar el bloqueador de anuncios: {e}")
            
        try:
            _ventana_navegador.evaluate_js(BARRA_HERRAMIENTAS_JS)
            print("[NAVEGADOR] Barra de navegación inyectada.")
        except Exception as e:
            print(f"[NAVEGADOR] Error al inyectar la barra de navegación: {e}")

def _al_cerrar_navegador():
    """Callback de cierre de la ventana del navegador."""
    global _ventana_navegador, _hwnd_navegador, _está_anclado
    print("[NAVEGADOR] Ventana cerrada.")
    _ventana_navegador = None
    _hwnd_navegador = None
    _está_anclado = False
    
    # Sincronizar el estado con el HUD principal
    try:
        from main2 import enviar_difusion_web_sync
        enviar_difusion_web_sync({"action": "browser_state", "state": "closed"})
    except Exception as e:
        print(f"[NAVEGADOR] Error al difundir el estado: {e}")
        
    if _ventana_webview_principal:
        _ventana_webview_principal.evaluate_js("if(window.updateBrowserUIState) { window.updateBrowserUIState('closed'); } else { document.body.classList.remove('browser-open'); }")