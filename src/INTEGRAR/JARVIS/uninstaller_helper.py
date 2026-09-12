import os
import winreg
import re
import shutil
import subprocess

def limpiar_nombre_para_busqueda(nombre):
    """Limpia el nombre de la aplicación para la búsqueda heurística de rastros."""
    # Eliminar paréntesis y menciones de versión
    nombre = re.sub(r'\(.*?\)|v\d+(\.\d+)*|\d+\.\d+(\.\d+)*', '', nombre)
    # Eliminar caracteres especiales
    nombre = re.sub(r'[^a-zA-Z0-9\s-]', '', nombre)
    return nombre.strip()

def listar_programas_instalados():
    """Enumera todas las aplicaciones instaladas en la máquina desde el Registro."""
    rutas = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    programas = []
    vistos = set()
    
    for hive, path in rutas:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            info = winreg.QueryInfoKey(key)
            num_subclaves = info[0]
            
            for i in range(num_subclaves):
                try:
                    subclave_nombre = winreg.EnumKey(key, i)
                    subclave = winreg.OpenKey(key, subclave_nombre, 0, winreg.KEY_READ)
                    
                    try:
                        nombre, _ = winreg.QueryValueEx(subclave, "DisplayName")
                        cadena_desinstalacion, _ = winreg.QueryValueEx(subclave, "UninstallString")
                        
                        nombre = nombre.strip()
                        if not nombre or nombre in vistos:
                            winreg.CloseKey(subclave)
                            continue
                            
                        vistos.add(nombre)
                        
                        # Fallbacks opcionales
                        publicador = ""
                        try: publicador, _ = winreg.QueryValueEx(subclave, "Publisher")
                        except OSError: pass
                        
                        version = ""
                        try: version, _ = winreg.QueryValueEx(subclave, "DisplayVersion")
                        except OSError: pass
                        
                        ubicacion_instalacion = ""
                        try: ubicacion_instalacion, _ = winreg.QueryValueEx(subclave, "InstallLocation")
                        except OSError: pass
                        
                        ruta_icono = ""
                        try: ruta_icono, _ = winreg.QueryValueEx(subclave, "DisplayIcon")
                        except OSError: pass
                        
                        programas.append({
                            "name": nombre,
                            "subkey": subclave_nombre,
                            "publisher": publicador.strip(),
                            "version": version.strip(),
                            "uninstall_string": cadena_desinstalacion.strip(),
                            "install_location": ubicacion_instalacion.strip(),
                            "icon_path": ruta_icono.strip(),
                            "hive": "HKLM" if hive == winreg.HKEY_LOCAL_MACHINE else "HKCU"
                        })
                    except OSError:
                        pass
                    finally:
                        winreg.CloseKey(subclave)
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            continue
            
    programas.sort(key=lambda x: x["name"].lower())
    return programas

def escanear_restos_archivos(app_name, publicador="", ubicacion_instalacion=""):
    """Busca heurísticamente rastros de carpetas en el disco duro."""
    app_name_limpio = limpiar_nombre_para_busqueda(app_name).lower()
    app_name_sin_espacios = app_name_limpio.replace(" ", "")
    
    publicador_limpio = limpiar_nombre_para_busqueda(publicador).lower() if publicador else ""
    
    restos = []
    rutas_vistas = set()
    
    # 1. Procesar la carpeta de instalación oficial del registro si existe
    if ubicacion_instalacion and os.path.exists(ubicacion_instalacion):
        ruta_abs = os.path.abspath(ubicacion_instalacion)
        # Evitar apuntar a la raíz de un disco duro por error
        if len(ruta_abs) > 4:
            rutas_vistas.add(ruta_abs)
            restos.append({
                "type": "folder",
                "path": ruta_abs,
                "desc": "Carpeta de instalación oficial configurada en el Registro de Windows."
            })
            
    # Carpetas sensibles por defecto
    directorios_busqueda = [
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        os.environ.get("ProgramData", "C:\\ProgramData"),
        os.path.expanduser("~/AppData/Local"),
        os.path.expanduser("~/AppData/Roaming"),
        os.path.expanduser("~/AppData/LocalLow")
    ]
    
    for base_dir in directorios_busqueda:
        if not base_dir or not os.path.exists(base_dir):
            continue
        try:
            # Nivel 1
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                    
                item_lower = item.lower()
                item_sin_espacios = item_lower.replace(" ", "")
                
                coincidencia = False
                if app_name_limpio and len(app_name_limpio) > 3 and app_name_limpio in item_lower:
                    coincidencia = True
                elif app_name_sin_espacios and len(app_name_sin_espacios) > 3 and app_name_sin_espacios in item_sin_espacios:
                    coincidencia = True
                    
                if coincidencia:
                    ruta_abs = os.path.abspath(item_path)
                    if ruta_abs not in rutas_vistas and len(ruta_abs) > 4:
                        rutas_vistas.add(ruta_abs)
                        restos.append({
                            "type": "folder",
                            "path": ruta_abs,
                            "desc": f"Carpeta asociada a la aplicación en {os.path.basename(base_dir)}."
                        })
                    continue  # No bajar al nivel 2 si la carpeta padre ya coincide
                    
                # Nivel 2 (ej: base_dir\Google\Android Studio)
                try:
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        if not os.path.isdir(subitem_path):
                            continue
                            
                        subitem_lower = subitem.lower()
                        subitem_sin_espacios = subitem_lower.replace(" ", "")
                        
                        sub_coincidencia = False
                        if app_name_limpio and len(app_name_limpio) > 3 and app_name_limpio in subitem_lower:
                            sub_coincidencia = True
                        elif app_name_sin_espacios and len(app_name_sin_espacios) > 3 and app_name_sin_espacios in subitem_sin_espacios:
                            sub_coincidencia = True
                            
                        if sub_coincidencia:
                            ruta_abs = os.path.abspath(subitem_path)
                            if ruta_abs not in rutas_vistas and len(ruta_abs) > 4:
                                rutas_vistas.add(ruta_abs)
                                restos.append({
                                    "type": "folder",
                                    "path": ruta_abs,
                                    "desc": f"Carpeta asociada a la aplicación bajo el editor/categoría '{item}'."
                                })
                except OSError:
                    pass
        except OSError:
            continue
            
    return restos

def escanear_restos_registro(app_name, publicador=""):
    """Busca heurísticamente rastros de claves de registro obsoletas."""
    app_name_limpio = limpiar_nombre_para_busqueda(app_name).lower()
    app_name_sin_espacios = app_name_limpio.replace(" ", "")
    
    publicador_limpio = limpiar_nombre_para_busqueda(publicador).lower() if publicador else ""
    
    restos = []
    
    hives = [
        (winreg.HKEY_CURRENT_USER, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software\\Wow6432Node")
    ]
    
    for hive, base_path in hives:
        nombre_hive = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
        try:
            key = winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ)
            info = winreg.QueryInfoKey(key)
            num_subclaves = info[0]
            
            for i in range(num_subclaves):
                try:
                    subclave_nombre = winreg.EnumKey(key, i)
                    subclave_nombre_lower = subclave_nombre.lower()
                    subclave_sin_espacios = subclave_nombre_lower.replace(" ", "")
                    ruta_completa = f"{nombre_hive}\\{base_path}\\{subclave_nombre}"
                    
                    coincidencia = False
                    if app_name_limpio and len(app_name_limpio) > 3 and app_name_limpio in subclave_nombre_lower:
                        coincidencia = True
                    elif app_name_sin_espacios and len(app_name_sin_espacios) > 3 and app_name_sin_espacios in subclave_sin_espacios:
                        coincidencia = True
                        
                    if coincidencia:
                        restos.append({
                            "type": "registry",
                            "hive": nombre_hive,
                            "path": ruta_completa,
                            "desc": "Clave de registro asociada al nombre de la aplicación."
                        })
                        continue  # No entrar si la raíz coincide
                        
                    # Nivel 2 (ej: HKLM\Software\Publicador\AppName)
                    if publicador_limpio and len(publicador_limpio) > 3 and publicador_limpio in subclave_nombre_lower:
                        try:
                            pub_key = winreg.OpenKey(hive, f"{base_path}\\{subclave_nombre}", 0, winreg.KEY_READ)
                            pub_info = winreg.QueryInfoKey(pub_key)
                            for j in range(pub_info[0]):
                                subclave_subnombre = winreg.EnumKey(pub_key, j)
                                subclave_subnombre_lower = subclave_subnombre.lower()
                                subclave_subnombre_sin_espacios = subclave_subnombre_lower.replace(" ", "")
                                
                                sub_coincidencia = False
                                if app_name_limpio and len(app_name_limpio) > 3 and app_name_limpio in subclave_subnombre_lower:
                                    sub_coincidencia = True
                                elif app_name_sin_espacios and len(app_name_sin_espacios) > 3 and app_name_sin_espacios in subclave_subnombre_sin_espacios:
                                    sub_coincidencia = True
                                    
                                if sub_coincidencia:
                                    restos.append({
                                        "type": "registry",
                                        "hive": nombre_hive,
                                        "path": f"{ruta_completa}\\{subclave_subnombre}",
                                        "desc": f"Clave de registro asociada bajo el editor '{subclave_nombre}'."
                                    })
                            winreg.CloseKey(pub_key)
                        except OSError:
                            pass
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            continue
            
    return restos

def ejecutar_proceso_desinstalacion(cadena_desinstalacion):
    """Ejecuta el proceso de desinstalación oficial de la aplicación."""
    try:
        print(f"[DESINSTALADOR] Ejecutando desinstalador oficial: {cadena_desinstalacion}")
        # Ejecutar el desinstalador y esperar a que termine
        p = subprocess.Popen(cadena_desinstalacion, shell=True)
        p.wait()
        return True, "Desinstalación oficial completada."
    except Exception as e:
        print(f"[DESINSTALADOR] Error al ejecutar la desinstalación: {e}")
        return False, str(e)

def eliminar_clave_registro_recursiva(hive, path):
    """Elimina una clave de registro y todas sus subclaves de forma recursiva."""
    # Convertir el nombre de la colmena en objeto winreg HKEY
    clave_hive = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    
    try:
        # 1. Abrir la clave para listar las subclaves
        key = winreg.OpenKey(clave_hive, path, 0, winreg.KEY_ALL_ACCESS)
        info = winreg.QueryInfoKey(key)
        num_subclaves = info[0]
        
        subclaves = []
        for i in range(num_subclaves):
            subclaves.append(winreg.EnumKey(key, i))
        winreg.CloseKey(key)
        
        # 2. Eliminar las subclaves primero recursivamente
        for subclave in subclaves:
            eliminar_clave_registro_recursiva(hive, f"{path}\\{subclave}")
            
        # 3. Eliminar la clave misma
        ruta_padre, nombre_clave = path.rsplit("\\", 1)
        clave_padre = winreg.OpenKey(clave_hive, ruta_padre, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKey(clave_padre, nombre_clave)
        winreg.CloseKey(clave_padre)
        return True
    except Exception as e:
        print(f"[DESINSTALADOR] Error al eliminar la clave de registro {hive}\\{path}: {e}")
        return False

def limpiar_elemento_resto(item):
    """Elimina un elemento residual (carpeta o clave de registro)."""
    tipo = item.get("type")
    path = item.get("path")
    
    if tipo == "folder":
        if not path or len(path) <= 4:
            return False, "Ruta inválida o demasiado corta para una eliminación segura."
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                return True, "Carpeta eliminada con éxito."
            return True, "Carpeta ya inexistente."
        except Exception as e:
            return False, f"No se pudo eliminar la carpeta: {e}"
            
    elif tipo == "registry":
        hive = item.get("hive")
        # La ruta contiene la colmena al principio (HKCU\ o HKLM\), hay que dividirla
        partes = path.split("\\", 1)
        if len(partes) < 2:
            return False, "Ruta de registro inválida."
        reg_path = partes[1]
        
        exito = eliminar_clave_registro_recursiva(hive, reg_path)
        if exito:
            return True, "Clave de registro eliminada con éxito."
        return False, "Error al eliminar la clave de registro."
        
    return False, "Tipo de residuo desconocido."