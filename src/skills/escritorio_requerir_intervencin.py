import os
import sys
import subprocess
from pathlib import Path
import shutil
from datetime import datetime
def instalar_si_no_existe(paquete, pip_nombre=None):
    if pip_nombre is None:
        pip_nombre = paquete
    try:
        __import__(paquete)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_nombre])
def run(params):
    try:
        instalar_si_no_existe('plyer', 'plyer')
        from plyer import notification
        directorio_usuario = Path.home()
        descargas = directorio_usuario / "Downloads"
        if not descargas.exists():
            return {"status": "error", "message": "No se encontró la carpeta de descargas."}
        # Crear carpetas de organización si no existen
        carpetas = {
            "Imágenes": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
            "Documentos": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"],
            "Instaladores": [".exe", ".msi", ".dmg", ".pkg"],
            "Comprimidos": [".zip", ".rar", ".7z", ".tar", ".gz"]
        }
        for carpeta in carpetas.keys():
            (descargas / carpeta).mkdir(exist_ok=True)
        archivos_movidos = 0
        for archivo in descargas.iterdir():
            if archivo.is_file():
                extension = archivo.suffix.lower()
                movido = False
                for carpeta, exts in carpetas.items():
                    if extension in exts:
                        destino = descargas / carpeta / archivo.name
                        # Evitar sobreescritura
                        if destino.exists():
                            destino = descargas / carpeta / f"{archivo.stem}_{int(datetime.now().timestamp())}{extension}"
                        shutil.move(str(archivo), str(destino))
                        archivos_movidos += 1
                        movido = True
                        break
        mensaje_resultado = f"Flujo contextual completado. Se organizaron {archivos_movidos} archivos en Descargas."
        # Notificación del sistema
        notification.notify(
            title="Automatización de Flujos",
            message=mensaje_resultado,
            timeout=5
        )
        return {
            "status": "success",
            "archivos_organizados": archivos_movidos,
            "message": mensaje_resultado
        }
    except Exception as e:
        error_msg = f"Error en la ejecución del flujo contextual: {str(e)}"
        try:
            from plyer import notification
            notification.notify(
                title="Error en Automatización",
                message=error_msg,
                timeout=5
            )
        except:
            pass
        return {"status": "error", "message": error_msg}