import os
import sys
import csv
import json
import time
import subprocess
import urllib.request

CSV_URL = "https://www.vpngate.net/api/iphone/"
NOMBRE_CONEXION = "JarvisVPN"

# Caché global para evitar descargar la lista de servidores demasiado a menudo
_servidores_cache = []
_momento_ultima_descarga = 0

def entero_seguro(val, default=0):
    try:
        if val is None:
            return default
        val_str = str(val).strip()
        if not val_str or val_str == '-':
            return default
        return int(val_str)
    except Exception:
        return default

def obtener_servidores(forzar=False):
    """Descarga la lista de servidores desde VPNGate y la parsea."""
    global _servidores_cache, _momento_ultima_descarga
    tiempo_actual = time.time()
    
    # Usar la caché si tiene menos de 5 minutos
    if _servidores_cache and (tiempo_actual - _momento_ultima_descarga < 300) and not forzar:
        return _servidores_cache
        
    try:
        print("[VPN] Recuperando servidores de VPN Gate...")
        req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            
        # Parsear el CSV (ignorar la primera línea de comentario y la última línea vacía)
        lineas = data.strip().split('\n')
        if len(lineas) < 3:
            return []
            
        # La 2ª línea contiene los encabezados
        lector = csv.DictReader(lineas[1:])
        
        servidores = []
        for fila in lector:
            if not fila.get('IP'):
                continue
            servidores.append({
                'hostname': fila.get('#HostName'),
                'ip': fila.get('IP'),
                'score': entero_seguro(fila.get('Score'), 0),
                'ping': entero_seguro(fila.get('Ping'), 999),
                'speed': entero_seguro(fila.get('Speed'), 0),
                'country_long': fila.get('CountryLong'),
                'country_short': fila.get('CountryShort'),
                'uptime': entero_seguro(fila.get('Uptime'), 0)
            })
            
        _servidores_cache = servidores
        _momento_ultima_descarga = tiempo_actual
        print(f"[VPN] {len(servidores)} servidores recuperados con éxito.")
        return servidores
    except Exception as e:
        print(f"[VPN] Error al recuperar los servidores: {e}")
        return _servidores_cache or []

def obtener_paises():
    """Devuelve la lista de países disponibles con su código ISO y número de servidores."""
    servidores = obtener_servidores()
    paises = {}
    for s in servidores:
        codigo = s['country_short']
        nombre = s['country_long']
        if codigo not in paises:
            paises[codigo] = {
                'code': codigo,
                'name': nombre,
                'count': 0
            }
        paises[codigo]['count'] += 1
        
    # Ordenar por nombre de país
    return sorted(list(paises.values()), key=lambda x: x['name'])

def obtener_ip_publica_actual():
    """Obtiene la IP pública actual y la localización del usuario."""
    try:
        req = urllib.request.Request("https://ipinfo.io/json", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            return {
                "ip": data.get("ip"),
                "country": data.get("country"),
                "city": data.get("city"),
                "org": data.get("org")
            }
    except Exception:
        return None

def desconectar():
    """Desconecta el VPN JarvisVPN y elimina el perfil de conexión."""
    try:
        print("[VPN] Desconectando...")
        # Ejecutar rasdial /disconnect
        subprocess.run(["rasdial", NOMBRE_CONEXION, "/disconnect"], capture_output=True)
        
        # Eliminar el perfil VPN de Windows mediante PowerShell
        cmd_ps = f"Remove-VpnConnection -Name '{NOMBRE_CONEXION}' -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-Command", cmd_ps], capture_output=True)
        
        print("[VPN] Desconectado con éxito.")
        return {"success": True}
    except Exception as e:
        print(f"[VPN] Error al desconectar: {e}")
        return {"success": False, "error": str(e)}

def obtener_estado():
    """Devuelve el estado actual de la conexión VPN."""
    try:
        cmd_ps = f"Get-VpnConnection -Name '{NOMBRE_CONEXION}' | Select-Object -ExpandProperty ConnectionStatus"
        res = subprocess.run(["powershell", "-Command", cmd_ps], capture_output=True, text=True)
        estado = res.stdout.strip()
        if estado:
            return {"connected": estado == "Connected", "status": estado}
        return {"connected": False, "status": "Disconnected"}
    except Exception:
        return {"connected": False, "status": "Disconnected"}

cancelacion_solicitada = False

def cancelar_conexion():
    """Señala la cancelación de la conexión en curso y fuerza la detención de rasdial."""
    global cancelacion_solicitada
    cancelacion_solicitada = True
    print("[VPN] Cancelación solicitada por el usuario. Forzando taskkill rasdial...")
    # Matar el proceso de marcación de Windows si está en curso
    subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)

def conectar(codigo_pais):
    """Intenta conectarse al mejor servidor VPN del país solicitado, probando primero los servidores de forma concurrente."""
    global cancelacion_solicitada
    cancelacion_solicitada = False
    
    # Asegurarse de estar desconectado primero
    desconectar()
    
    servidores = obtener_servidores()
    # Filtrar por país y ordenar por Velocidad (Speed) descendente
    servidores_pais = [s for s in servidores if s['country_short'].lower() == codigo_pais.lower()]
    servidores_pais.sort(key=lambda x: (x['speed'], -x['ping']), reverse=True)
    
    if not servidores_pais:
        return {"success": False, "error": f"No hay servidores disponibles para el país: {codigo_pais}"}
        
    print(f"[VPN] Intentando conectar a {codigo_pais} ({len(servidores_pais)} servidores candidatos)...")
    
    # 1. Seleccionar TODOS los servidores candidatos para la prueba de ping
    candidatos = servidores_pais
    servidores_activos = []
    
    # Ping concurrente con ThreadPoolExecutor
    import concurrent.futures
    
    # Ajustar los workers de forma dinámica hasta un máximo de 60 para ser ultra-rápido
    num_workers = min(60, len(candidatos))
    if num_workers < 1:
        num_workers = 1
        
    def trabajador_ping(s):
        if cancelacion_solicitada:
            return None
        ip = s['ip']
        try:
            # -n 1 (1 ping), -w 400 (400ms timeout)
            res = subprocess.run(
                ["ping", "-n", "1", "-w", "400", ip],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                return s
        except Exception:
            pass
        return None
        
    print(f"[VPN] Prefiltrado concurrente de TODOS los servidores activos mediante ping ({len(candidatos)} servidores)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        resultados = executor.map(trabajador_ping, candidatos)
        for s_activo in resultados:
            if cancelacion_solicitada:
                break
            if s_activo is not None:
                servidores_activos.append(s_activo)
                
    print(f"[VPN] {len(servidores_activos)} servidores activos responden al ping de {len(candidatos)} probados.")
    
    # Si ninguno responde al ping, se intentan igualmente los servidores por defecto (fallback)
    if not servidores_activos:
        if cancelacion_solicitada:
            return {"success": False, "error": "Cancelado por el usuario."}
        print("[VPN] Ningún servidor respondió al ping. Usando los servidores de la lista por defecto.")
        servidores_activos = servidores_pais
        
    # Intentar conectar a los servidores activos (todas las tentativas posibles)
    max_intentos = len(servidores_activos)
    
    for idx, s in enumerate(servidores_activos):
        if cancelacion_solicitada:
            print("[VPN] Conexión cancelada antes del intento.")
            return {"success": False, "error": "Cancelado por el usuario."}
            
        ip_servidor = s['ip']
        print(f"[VPN] [{idx+1}/{max_intentos}] Intentando conectar al servidor {ip_servidor} (Ping: {s['ping']}ms)...")
        
        try:
            # 1. Crear la conexión L2TP/IPsec mediante PowerShell
            cmd_ps = (
                f"Add-VpnConnection -Name '{NOMBRE_CONEXION}' "
                f"-ServerAddress '{ip_servidor}' "
                f"-TunnelType L2tp "
                f"-L2tpPsk 'vpn' "
                f"-Force"
            )
            subprocess.run(["powershell", "-Command", cmd_ps], capture_output=True)
            
            if cancelacion_solicitada:
                print("[VPN] Conexión cancelada justo después de crear el perfil.")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{NOMBRE_CONEXION}' -Force"], capture_output=True)
                return {"success": False, "error": "Cancelado por el usuario."}

            # 2. Ejecutar la marcación mediante rasdial con un timeout reducido de 7 segundos
            res_marcacion = subprocess.run(
                ["rasdial", NOMBRE_CONEXION, "vpn", "vpn"], 
                capture_output=True, 
                text=True,
                timeout=7
            )
            
            if cancelacion_solicitada:
                print("[VPN] Conexión cancelada durante/justo después de la marcación.")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{NOMBRE_CONEXION}' -Force"], capture_output=True)
                return {"success": False, "error": "Cancelado por el usuario."}
                
            if res_marcacion.returncode == 0:
                print(f"[VPN] Conectado al servidor {ip_servidor} con éxito.")
                
                # Verificar la nueva IP pública
                time.sleep(2)  # Esperar a que se establezca la ruta
                info_ip = obtener_ip_publica_actual()
                
                return {
                    "success": True,
                    "server_ip": ip_servidor,
                    "new_ip_info": info_ip or {"ip": ip_servidor, "country": codigo_pais}
                }
            else:
                print(f"[VPN] Fallo en la marcación rasdial: {res_marcacion.stderr.strip() or res_marcacion.stdout.strip()}")
                # Limpiar en caso de fallo
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{NOMBRE_CONEXION}' -Force"], capture_output=True)
        except subprocess.TimeoutExpired:
            print(f"[VPN] Timeout (7s) agotado en la marcación rasdial para {ip_servidor}.")
            # Matar rasdial
            subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)
            # Limpiar el perfil
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{NOMBRE_CONEXION}' -Force"], capture_output=True)
        except Exception as e:
            print(f"[VPN] Error en el intento: {e}")
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{NOMBRE_CONEXION}' -Force"], capture_output=True)
            
        if cancelacion_solicitada:
            print("[VPN] Cancelación detectada después del intento.")
            return {"success": False, "error": "Cancelado por el usuario."}
            
    if cancelacion_solicitada:
        return {"success": False, "error": "Cancelado por el usuario."}
    return {"success": False, "error": f"Todos los intentos con los {max_intentos} servidores activos fallaron o expiraron. Por favor, vuelva a intentarlo."}