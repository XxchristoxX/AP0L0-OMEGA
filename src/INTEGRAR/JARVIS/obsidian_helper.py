import os
import glob
import json

def obtener_ruta_cofre():
    try:
        ruta_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(ruta_cfg):
            with open(ruta_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                ruta_cofre = data.get("obsidian_vault_path")
                if ruta_cofre and os.path.isdir(ruta_cofre):
                    return ruta_cofre
    except Exception:
        pass
    
    # Por defecto
    ruta_por_defecto = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ObsidianVault")
    if not os.path.exists(ruta_por_defecto):
        os.makedirs(ruta_por_defecto, exist_ok=True)
    return ruta_por_defecto

def crear_o_modificar_nota(titulo, contenido):
    """Crea o modifica una nota markdown en el cofre."""
    cofre = obtener_ruta_cofre()
    # Limpiar el título para evitar inyecciones de ruta
    nombre_archivo = os.path.basename(titulo)
    if not nombre_archivo.endswith(".md"):
        nombre_archivo += ".md"
    
    ruta_archivo = os.path.join(cofre, nombre_archivo)
    try:
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(contenido)
        print(f"[OBSIDIAN] Nota creada/modificada: {ruta_archivo}")
        return True, f"Nota '{titulo}' creada en su cofre de Obsidian, Christopher."
    except Exception as e:
        print(f"[OBSIDIAN] Error al crear la nota: {e}")
        return False, f"No se pudo crear la nota: {e}"

def leer_nota(titulo):
    """Lee el contenido de una nota markdown."""
    cofre = obtener_ruta_cofre()
    nombre_archivo = os.path.basename(titulo)
    if not nombre_archivo.endswith(".md"):
        nombre_archivo += ".md"
    
    ruta_archivo = os.path.join(cofre, nombre_archivo)
    if not os.path.exists(ruta_archivo):
        return False, f"La nota '{titulo}' no existe en el cofre, Christopher."
    
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            contenido = f.read()
        return True, contenido
    except Exception as e:
        return False, f"Error al leer la nota: {e}"

def eliminar_nota(titulo):
    """Elimina una nota markdown del cofre."""
    cofre = obtener_ruta_cofre()
    nombre_archivo = os.path.basename(titulo)
    if not nombre_archivo.endswith(".md"):
        nombre_archivo += ".md"
    
    ruta_archivo = os.path.join(cofre, nombre_archivo)
    if not os.path.exists(ruta_archivo):
        return False, f"La nota '{titulo}' no existe en el cofre, Christopher."
    
    try:
        os.remove(ruta_archivo)
        print(f"[OBSIDIAN] Nota eliminada: {ruta_archivo}")
        return True, f"La nota '{titulo}' se ha eliminado de su cofre de Obsidian, Christopher."
    except Exception as e:
        return False, f"Error al eliminar la nota: {e}"

def listar_notas():
    """Lista todas las notas markdown del cofre con metadatos básicos."""
    cofre = obtener_ruta_cofre()
    archivos = glob.glob(os.path.join(cofre, "*.md"))
    notas = []
    for f in archivos:
        try:
            stat = os.stat(f)
            notas.append({
                "titulo": os.path.basename(f)[:-3], # quitar el .md
                "tamaño": stat.st_size,
                "mtime": stat.st_mtime # fecha de modificación
            })
        except Exception:
            pass
    # Ordenar por fecha de modificación descendente
    notas.sort(key=lambda x: x["mtime"], reverse=True)
    return notas

def buscar_notas(consulta):
    """Busca archivos markdown que contengan la palabra clave en el cofre."""
    cofre = obtener_ruta_cofre()
    archivos = glob.glob(os.path.join(cofre, "*.md"))
    resultados = []
    consulta = consulta.lower()
    for f in archivos:
        titulo = os.path.basename(f)[:-3]
        coincide = False
        fragmento = ""
        
        # Coincidencia en el título
        if consulta in titulo.lower():
            coincide = True
        
        # Coincidencia en el contenido
        try:
            with open(f, "r", encoding="utf-8") as archivo_obj:
                contenido = archivo_obj.read()
                if consulta in contenido.lower():
                    coincide = True
                    # Extraer un breve extracto
                    idx = contenido.lower().find(consulta)
                    inicio = max(0, idx - 40)
                    fin = min(len(contenido), idx + 80)
                    fragmento = "..." + contenido[inicio:fin].replace("\n", " ") + "..."
        except Exception:
            pass
            
        if coincide:
            resultados.append({
                "titulo": titulo,
                "fragmento": fragmento
            })
    return resultados