import os
import json
import time
import threading
from google.genai import types

# MEMORIA PERSISTENTE
# ==========================================
_DIR_BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_MEMORIA = os.path.join(_DIR_BASE, "jarvis_memoire.json")

def cargar_memoria():
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def guardar_memoria(memoria):
    try:
        with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(memoria, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error al guardar memoria: {e}")

def agregar_memoria(clave, valor):
    memoria      = cargar_memoria()
    memoria[clave] = {"valor": valor, "timestamp": time.strftime("%d/%m/%Y %H:%M")}
    guardar_memoria(memoria)

def eliminar_memoria(clave):
    memoria = cargar_memoria()
    if clave in memoria:
        del memoria[clave]
        guardar_memoria(memoria)
        return True
    return False

def construir_contexto_memoria():
    memoria = cargar_memoria()
    if not memoria:
        return ""
    lineas = ["MEMORIA PERSISTENTE:"]
    for clave, data in memoria.items():
        lineas.append(f"  - {clave} : {data['valor']} (anotado el {data['timestamp']})")
    return "\n".join(lineas)

# ==========================================
# HISTORIAL DE CONVERSACIONES PERSISTENTE
# ==========================================
ARCHIVO_HISTORIAL_CONV = os.path.join(_DIR_BASE, "jarvis_conversations.json")
MAX_INTERCAMBIOS_ARCHIVO = 200   # máximo de intercambios almacenados en disco
MAX_INTERCAMBIOS_CARGA  = 30    # intercambios recargados al inicio (contexto IA)

def _guardar_intercambio_conv_sync(texto_usuario: str, texto_modelo: str):
    """Realiza el guardado real en el disco."""
    # Esperar unos segundos para asegurar que Jarvis ha empezado a hablar
    # Esto permite que la notificación [OBSIDIAN] aparezca al final, como desea el usuario
    time.sleep(3)
    
    # 1. Guardado local en el archivo JSON
    try:
        intercambios = []
        if os.path.exists(ARCHIVO_HISTORIAL_CONV):
            with open(ARCHIVO_HISTORIAL_CONV, "r", encoding="utf-8") as f:
                intercambios = json.load(f)
        intercambios.append({
            "date":  time.strftime("%d/%m/%Y"),
            "heure": time.strftime("%H:%M"),
            "user":  texto_usuario[:2000],
            "model": texto_modelo[:3000],
        })
        if len(intercambios) > MAX_INTERCAMBIOS_ARCHIVO:
            intercambios = intercambios[-MAX_INTERCAMBIOS_ARCHIVO:]
        with open(ARCHIVO_HISTORIAL_CONV, "w", encoding="utf-8") as f:
            json.dump(intercambios, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CONV] Error al guardar historial: {e}")

    # 2. Guardado en la nota 'Journal_Discussions.md' del cofre de Obsidian configurado
    try:
        import obsidian_helper
        exito, contenido = obsidian_helper.leer_nota("Journal_Discussions")
        if not exito:
            contenido = "# Diario de Conversaciones JARVIS\n\nEste diario registra el historial completo de sus intercambios con JARVIS.\n\n"
            
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        nuevo_intercambio = f"### Intercambio del {timestamp}\n- **Usuario** : {texto_usuario}\n- **JARVIS** : {texto_modelo}\n\n"
        
        # Concatenar el nuevo intercambio al principio (debajo del título)
        lineas = contenido.split("\n")
        cabecera = []
        resto_lineas = []
        
        for linea in lineas:
            if linea.startswith("# ") or (linea.strip() and not linea.startswith("##") and not linea.startswith("###") and not linea.startswith("- ") and len(cabecera) < 3):
                cabecera.append(linea)
            else:
                resto_lineas.append(linea)
                
        contenido_cabecera = "\n".join(cabecera).strip()
        contenido_anterior = "\n".join(resto_lineas).strip()
        
        nuevo_contenido = f"{contenido_cabecera}\n\n{nuevo_intercambio}{contenido_anterior}"
        obsidian_helper.crear_o_modificar_nota("Journal_Discussions", nuevo_contenido)
    except Exception as e:
        print(f"[OBSIDIAN] Error al guardar el historial en Obsidian: {e}")

def _guardar_intercambio_conv(texto_usuario: str, texto_modelo: str):
    """Lanza el guardado del intercambio en segundo plano para no ralentizar Jarvis."""
    threading.Thread(target=_guardar_intercambio_conv_sync, args=(texto_usuario, texto_modelo), daemon=True).start()

def _cargar_historial_reciente():
    """Carga los últimos intercambios y devuelve una lista de tipos.Content."""
    if not os.path.exists(ARCHIVO_HISTORIAL_CONV):
        return []
    try:
        with open(ARCHIVO_HISTORIAL_CONV, "r", encoding="utf-8") as f:
            intercambios = json.load(f)
        recientes = intercambios[-MAX_INTERCAMBIOS_CARGA:]
        hist = []
        for e in recientes:
            fecha_str = f"[{e.get('date','?')} {e.get('heure','?')}] "
            hist.append(types.Content(role="user",  parts=[types.Part(text=fecha_str + e["user"])]))
            hist.append(types.Content(role="model", parts=[types.Part(text=e["model"])]))
        print(f"[CONV] {len(recientes)} intercambios pasados recargados en memoria.")
        return hist
    except Exception as e:
        print(f"[CONV] Error al cargar historial: {e}")
        return []