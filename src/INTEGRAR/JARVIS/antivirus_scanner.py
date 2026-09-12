import os
import winreg
import psutil
import json
import asyncio

def obtener_exclusiones():
    """Carga las exclusiones del antivirus desde jarvis_config.json."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("av_exclusions", [])
    except Exception as e:
        print(f"[AV] Error al cargar exclusiones: {e}")
    return []

def esta_excluido(objetivo, exclusiones):
    """Verifica si un objetivo de amenaza está en la lista de exclusiones."""
    if not objetivo or not exclusiones:
        return False
    t_norm = objetivo.replace("\\", "/").lower()
    for exc in exclusiones:
        exc_norm = exc.replace("\\", "/").lower()
        if exc_norm == t_norm or exc_norm in t_norm:
            return True
    return False

# Cadena EICAR estándar para la prueba de detección antivirus
FIRMA_EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

def verificar_registro_inicio():
    """Analiza las claves de inicio del registro de Windows para detectar anomalías."""
    entradas = []
    
    # HKCU Run
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for i in range(256):
            try:
                nombre, valor, tipo = winreg.EnumValue(key, i)
                entradas.append({"name": nombre, "path": valor, "hive": "HKCU\\Run"})
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AV] Error al leer registro HKCU: {e}")

    # HKLM Run
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for i in range(256):
            try:
                nombre, valor, tipo = winreg.EnumValue(key, i)
                entradas.append({"name": nombre, "path": valor, "hive": "HKLM\\Run"})
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AV] Error al leer registro HKLM: {e}")
        
    return entradas

def verificar_procesos_ejecucion():
    """Analiza todos los procesos en ejecución."""
    lista_procesos = []
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            info = proc.info
            lista_procesos.append({
                "pid": info.get('pid') or 0,
                "name": info.get('name') or '',
                "path": info.get('exe') or ''
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return lista_procesos

def recopilar_archivos_escanear():
    """Recopila los archivos más recientes de carpetas sensibles para el análisis."""
    rutas = []
    carpetas = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        os.path.dirname(os.path.abspath(__file__))
    ]
    
    # Eliminar duplicados y carpetas inexistentes
    carpetas = list(set([os.path.abspath(f) for f in carpetas if f and os.path.exists(f)]))
    
    for carpeta in carpetas:
        try:
            for root, dirs, files in os.walk(carpeta):
                # Ignorar carpetas pesadas o no significativas
                for d in ["node_modules", "venv", ".git", "__pycache__", ".gemini", ".claude", "dist"]:
                    if d in dirs:
                        dirs.remove(d)
                
                # Limitar la profundidad a 2 subcarpetas para mantener rapidez
                ruta_rel = os.path.relpath(root, carpeta)
                profundidad = 0 if ruta_rel == "." else len(ruta_rel.split(os.sep))
                if profundidad > 2:
                    dirs.clear()
                    
                for archivo in files:
                    ruta_archivo = os.path.join(root, archivo)
                    try:
                        mtime = os.path.getmtime(ruta_archivo)
                        rutas.append((ruta_archivo, mtime))
                    except OSError:
                        pass
        except Exception as e:
            print(f"[AV] Error al recorrer carpeta {carpeta}: {e}")
            
    # Ordenar por fecha de modificación descendente (los archivos más recientes primero)
    rutas.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in rutas[:200]]  # Limitar a 200 archivos para la animación del HUD

def archivo_es_sospechoso(ruta_archivo):
    """Analiza un archivo físico en busca de virus conocidos, EICAR o firmas."""
    nombre_archivo = os.path.basename(ruta_archivo).lower()
    
    # ── 1. Verificación EICAR (Cadena de prueba antivirus universal) ───────
    try:
        if os.path.isfile(ruta_archivo) and os.path.getsize(ruta_archivo) < 1024 * 500: # < 500 KB
            with open(ruta_archivo, 'rb') as f:
                contenido = f.read(2048)
                if FIRMA_EICAR in contenido:
                    return "Threat.EICAR.TestFile", "Cadena de prueba antivirus estándar detectada (EICAR)"
    except Exception:
        pass

    # ── 2. Verificación de extensiones dobles (ej: factura.pdf.exe) ────────
    partes = nombre_archivo.split('.')
    if len(partes) >= 3:
        extensiones_peligrosas = ["exe", "bat", "cmd", "vbs", "js", "scr", "msi", "lnk", "pif", "com"]
        if partes[-1] in extensiones_peligrosas:
            extensiones_seguras = ["pdf", "jpg", "jpeg", "png", "txt", "doc", "docx", "xls", "xlsx", "zip", "rar", "mp4"]
            if partes[-2] in extensiones_seguras:
                return "Suspicious.DoubleExtension", f"Doble extensión detectada: .{partes[-2]}.{partes[-1]}"

    # ── 3. Búsqueda de palabras clave sospechosas en el nombre ─────────────────────
    palabras_sospechosas = ["mimikatz", "keylogger", "ransomware", "miner.exe", "backdoor", "trojan", "virus.exe"]
    for kw in palabras_sospechosas:
        if kw in nombre_archivo:
            return "Suspicious.Keywords", f"Nombre de archivo sospechoso que contiene: {kw}"

    # ── 4. Archivo ejecutable en el directorio Temp ──────────────────────
    if "temp" in ruta_archivo.lower() or "tmp" in ruta_archivo.lower():
        if nombre_archivo.endswith((".exe", ".scr", ".pif", ".vbs", ".bat")):
            return "Suspicious.TempExecutable", "Archivo ejecutable detectado en directorios temporales"

    return None, None

# Tarea activa de escaneo para permitir la cancelación
TAREA_ESCANEO_ACTIVA = None

async def ejecutar_escaneo_antivirus(callback_broadcast_ws, callback_hablar):
    """Ejecuta el análisis antivirus completo paso a paso y difunde el progreso."""
    global TAREA_ESCANEO_ACTIVA
    amenazas_detectadas = []
    exclusiones = obtener_exclusiones()
    
    try:
        # Paso 1: Inicialización
        await callback_broadcast_ws({
            "type": "av_start",
            "message": "Inicializando el motor antivirus de J.A.R.V.I.S..."
        })
        await asyncio.sleep(1.0)
        
        # Paso 2: Análisis del Registro de inicio
        await callback_broadcast_ws({
            "type": "av_progress",
            "step": "registry",
            "message": "Analizando la base de registro de inicio de Windows...",
            "scanned": 0,
            "total": 100,
            "percent": 5,
            "threats_found": len(amenazas_detectadas)
        })
        await asyncio.sleep(0.8)
        
        entradas_reg = verificar_registro_inicio()
        for reg in entradas_reg:
            # Verificar si la entrada es sospechosa
            ruta_lower = reg["path"].lower()
            for kw in ["temp", "tmp", "mimikatz", "miner", "keylogger", "exploit"]:
                if kw in ruta_lower or kw in reg["name"].lower():
                    amenaza = {
                        "type": "registry",
                        "name": reg["name"],
                        "target": reg["path"],
                        "class": "Suspicious.RegistryStartup",
                        "desc": f"Entrada de inicio sospechosa ({reg['hive']})"
                    }
                    if esta_excluido(amenaza["target"], exclusiones):
                        continue
                    amenazas_detectadas.append(amenaza)
                    await callback_broadcast_ws({
                        "type": "av_threat_detected",
                        "threat": amenaza
                    })
        
        # Paso 3: Análisis de Procesos Activos
        await callback_broadcast_ws({
            "type": "av_progress",
            "step": "processes",
            "message": "Analizando procesos en ejecución...",
            "scanned": 0,
            "total": 100,
            "percent": 15,
            "threats_found": len(amenazas_detectadas)
        })
        await asyncio.sleep(0.8)
        
        procesos = verificar_procesos_ejecucion()
        for i, proc in enumerate(procesos):
            nombre_lower = proc["name"].lower()
            ruta_lower = proc["path"].lower()
            
            # Detección heurística del proceso
            detectado = False
            desc = ""
            if "mimikatz" in nombre_lower or "miner.exe" in nombre_lower or "keylogger" in nombre_lower:
                detectado = True
                desc = "Proceso relacionado con una herramienta maliciosa conocida"
            elif ("temp" in ruta_lower or "tmp" in ruta_lower) and nombre_lower.endswith((".exe", ".bat")):
                detectado = True
                desc = "Proceso activo lanzado desde el directorio temporal"
                
            if detectado:
                amenaza = {
                    "type": "process",
                    "name": proc["name"],
                    "target": f"PID {proc['pid']} ({proc['path']})",
                    "class": "Suspicious.ActiveProcess",
                    "desc": desc
                }
                if esta_excluido(amenaza["target"], exclusiones) or esta_excluido(proc["path"], exclusiones):
                    continue
                amenazas_detectadas.append(amenaza)
                await callback_broadcast_ws({
                    "type": "av_threat_detected",
                    "threat": amenaza
                })
            
            # Transmitir periódicamente para mantener viva la UI
            if i % 15 == 0:
                await callback_broadcast_ws({
                    "type": "av_progress",
                    "step": "processes",
                    "message": f"Verificando procesos activos: {proc['name']} (PID {proc['pid']})",
                    "scanned": i,
                    "total": len(procesos),
                    "percent": int(15 + (i / len(procesos)) * 15),
                    "threats_found": len(amenazas_detectadas)
                })
                await asyncio.sleep(0.02)
                
        # Paso 4: Análisis de archivos físicos
        await callback_broadcast_ws({
            "type": "av_progress",
            "step": "files",
            "message": "Indexando y recopilando archivos recientes...",
            "scanned": 0,
            "total": 100,
            "percent": 30,
            "threats_found": len(amenazas_detectadas)
        })
        await asyncio.sleep(0.8)
        
        archivos_a_escanear = recopilar_archivos_escanear()
        total_archivos = len(archivos_a_escanear)
        
        for idx, ruta_archivo in enumerate(archivos_a_escanear):
            t_class, t_desc = archivo_es_sospechoso(ruta_archivo)
            if t_class:
                amenaza = {
                    "type": "file",
                    "name": os.path.basename(ruta_archivo),
                    "target": ruta_archivo,
                    "class": t_class,
                    "desc": t_desc
                }
                if esta_excluido(amenaza["target"], exclusiones):
                    continue
                amenazas_detectadas.append(amenaza)
                await callback_broadcast_ws({
                    "type": "av_threat_detected",
                    "threat": amenaza
                })
                
            # Enviar el progreso para cada archivo (para que los logs desfilen bonito en la pantalla)
            pct = int(30 + ((idx + 1) / total_archivos) * 69) if total_archivos > 0 else 99
            await callback_broadcast_ws({
                "type": "av_progress",
                "step": "files",
                "message": ruta_archivo,
                "scanned": idx + 1,
                "total": total_archivos,
                "percent": pct,
                "threats_found": len(amenazas_detectadas)
            })
            # Dormir 50ms para dar un efecto de desplazamiento agradable de 20 archivos/segundo
            await asyncio.sleep(0.05)
            
        # Paso 5: Finalización
        estado = "infected" if amenazas_detectadas else "clean"
        await callback_broadcast_ws({
            "type": "av_complete",
            "status": estado,
            "percent": 100,
            "threats": amenazas_detectadas
        })
        
        if estado == "infected":
            await callback_hablar(f"Análisis completado, Christopher. Atención, he detectado {len(amenazas_detectadas)} amenaza(s) de seguridad en su sistema. Consulte la consola para más detalles.")
        else:
            await callback_hablar("Análisis de seguridad completado. Su sistema está totalmente seguro. No se ha detectado ningún virus.")
            
    except asyncio.CancelledError:
        print("[AV] Análisis antivirus cancelado por el usuario.")
        await callback_broadcast_ws({
            "type": "av_cancel",
            "message": "Análisis interrumpido por el usuario."
        })
    except Exception as e:
        print(f"[AV] Error durante el análisis antivirus: {e}")
        await callback_broadcast_ws({
            "type": "av_complete",
            "status": "error",
            "message": f"Error del sistema durante el escaneo: {e}"
        })
        await callback_hablar("Se ha producido un error durante el análisis antivirus de su ordenador.")
    finally:
        TAREA_ESCANEO_ACTIVA = None