import os
import shutil
import glob
import subprocess
from datetime import datetime
from pathlib import Path
try:
    import pyautogui
except ImportError:
    pyautogui = None
import ctypes
import time

user32 = ctypes.windll.user32



def resolver_ruta(ruta):
    if not ruta:
        return None
    ruta = ruta.strip().strip('"').strip("'")
    atajos = {
        "escritorio": os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        "desktop": os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        "documento": os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "documentos": os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "descarga": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "descargas": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "telechargement": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "telechargements": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "downloads": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "imagen": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "imagenes": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "foto": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "fotos": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "video": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "videos": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "musica": os.path.join(os.environ.get("USERPROFILE", ""), "Music"),
        "music": os.path.join(os.environ.get("USERPROFILE", ""), "Music"),
        "papelera": "shell:RecycleBinFolder"
    }
    
    ruta_resuelta = atajos.get(ruta.lower(), ruta)
    
    # Probar variantes en español si la carpeta en inglés no existe
    if not os.path.exists(ruta_resuelta):
        variantes = {
            "Downloads": "Descargas",
            "Pictures": "Imágenes",
            "Music": "Música"
        }
        for eng, esp in variantes.items():
            if eng in ruta_resuelta:
                prueba_esp = ruta_resuelta.replace(eng, esp)
                if os.path.exists(prueba_esp):
                    ruta_resuelta = prueba_esp
                    break
    return ruta_resuelta

def encontrar_extension(ext):
    for categoria, extensiones in EXTENSIONES.items():
        if ext.lower() in extensiones:
            return categoria
    return "Otros"

def abrir_carpeta(ruta):
    global carpeta_actual
    ruta_resuelta = resolver_ruta(ruta)
    if not ruta_resuelta or (not os.path.exists(ruta_resuelta) and not ruta_resuelta.startswith("shell:")):
        return False, f"Carpeta no encontrada: {ruta_resuelta}"
    carpeta_actual = ruta_resuelta
    # Usar Popen para no bloquear
    if ruta_resuelta.startswith("shell:"):
        subprocess.Popen(f'explorer "{ruta_resuelta}"', shell=True)
    else:
        subprocess.Popen(['explorer', ruta_resuelta])
    return True, ruta_resuelta

def ordenar_ventanas_carpetas():
    """Abre y coloca las carpetas Documentos, Descargas, Imágenes y Vídeos en mosaico."""
    carpetas = [
        ("documento", 0, 0),             # Arriba Izquierda
        ("descarga", 1, 0),       # Arriba Derecha
        ("imagen", 0, 1),               # Abajo Izquierda
        ("video", 1, 1)                # Abajo Derecha
    ]
    
    sw, sh = pyautogui.size()
    ancho, alto = sw // 2, (sh - 40) // 2  # -40 para la barra de tareas aproximada
    
    for nombre, qx, qy in carpetas:
        abrir_carpeta(nombre)
        time.sleep(0.8) # Dar tiempo a que Explorer se abra
        
        # Intentar encontrar la ventana activa que acaba de abrirse
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            x = qx * ancho
            y = qy * alto
            # SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, 0, x, y, ancho, alto, 0x0040)
    
    return "He abierto y colocado sus carpetas principales en mosaico, Christopher."

def listar_carpeta(ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo or not os.path.exists(objetivo):
        return None, "No hay carpeta abierta o ruta inválida."
    archivos  = []
    carpetas  = []
    for item in os.scandir(objetivo):
        if item.is_file():
            archivos.append(item.name)
        elif item.is_dir():
            carpetas.append(item.name)
    return {"ruta": objetivo, "archivos": archivos, "carpetas": carpetas}, None

def ordenar_por_tipo(ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo or not os.path.exists(objetivo):
        return False, "No hay carpeta abierta o inválida."
    movimientos = 0
    errores      = 0
    categorias   = {}
    for item in os.scandir(objetivo):
        if not item.is_file():
            continue
        ext       = Path(item.name).suffix
        categoria = encontrar_extension(ext)
        destino  = os.path.join(objetivo, categoria)
        try:
            os.makedirs(destino, exist_ok=True)
            ruta_destino = os.path.join(destino, item.name)
            if os.path.exists(ruta_destino):
                base  = Path(item.name).stem
                ext2  = Path(item.name).suffix
                ruta_destino = os.path.join(destino, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, ruta_destino)
            movimientos += 1
            categorias[categoria] = categorias.get(categoria, 0) + 1
        except Exception as e:
            print(f"[ARCHIVO] Error al mover {item.name}: {e}")
            errores += 1
    resumen = ", ".join([f"{v} {k}" for k, v in categorias.items()])
    return True, f"{movimientos} archivos ordenados: {resumen}. {errores} errores."

def ordenar_por_fecha(ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo or not os.path.exists(objetivo):
        return False, "No hay carpeta abierta o inválida."
    movimientos = 0
    errores      = 0
    for item in os.scandir(objetivo):
        if not item.is_file():
            continue
        try:
            mtime     = item.stat().st_mtime
            fecha      = datetime.fromtimestamp(mtime)
            año     = str(fecha.year)
            mes      = fecha.strftime("%m - %B")
            destino  = os.path.join(objetivo, año, mes)
            os.makedirs(destino, exist_ok=True)
            ruta_destino = os.path.join(destino, item.name)
            if os.path.exists(ruta_destino):
                base      = Path(item.name).stem
                ext2      = Path(item.name).suffix
                ruta_destino = os.path.join(destino, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, ruta_destino)
            movimientos += 1
        except Exception as e:
            print(f"[ARCHIVO] Error al mover {item.name}: {e}")
            errores += 1
    return True, f"{movimientos} archivos ordenados por fecha. {errores} errores."

def ordenar_por_tipo_y_fecha(ruta=None):
    objetivo = ruta or carpeta_actual
    if not objetivo or not os.path.exists(objetivo):
        return False, "No hay carpeta abierta."
    ok1, msg1 = ordenar_por_tipo(objetivo)
    if not ok1:
        return False, msg1
    for item in os.scandir(objetivo):
        if item.is_dir() and item.name in EXTENSIONES.keys():
            ordenar_por_fecha(item.path)
    return True, "Carpeta ordenada por tipo y luego por fecha en cada categoría."

def crear_subcarpeta(nombre, ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo:
        return False, "No hay carpeta abierta."
    nueva = os.path.join(objetivo, nombre)
    try:
        os.makedirs(nueva, exist_ok=True)
        return True, f"Carpeta {nombre} creada."
    except Exception as e:
        return False, f"Error al crear la carpeta: {e}"

def renombrar_archivo(nombre_antiguo, nombre_nuevo, ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo:
        return False, "No hay carpeta abierta."
    antiguo = os.path.join(objetivo, nombre_antiguo)
    nuevo = os.path.join(objetivo, nombre_nuevo)
    try:
        os.rename(antiguo, nuevo)
        return True, f"Archivo renombrado a {nombre_nuevo}."
    except Exception as e:
        return False, f"Error al renombrar: {e}"

def mover_archivo(nombre_archivo, carpeta_destino, ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo:
        return False, "No hay carpeta abierta."
    origen = os.path.join(objetivo, nombre_archivo)
    destino   = os.path.join(objetivo, carpeta_destino, nombre_archivo)
    try:
        os.makedirs(os.path.join(objetivo, carpeta_destino), exist_ok=True)
        shutil.move(origen, destino)
        return True, f"{nombre_archivo} movido a {carpeta_destino}."
    except Exception as e:
        return False, f"Error al mover: {e}"

def buscar_archivo(nombre, ruta=None):
    objetivo = resolver_ruta(ruta) or carpeta_actual
    if not objetivo:
        return [], "No hay carpeta abierta."
    resultados = []
    for root, dirs, files in os.walk(objetivo):
        for f in files:
            if nombre.lower() in f.lower():
                resultados.append(os.path.join(root, f))
    return resultados, None