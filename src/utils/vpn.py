# vpn.py - VERSIÓN COMPLETA PARA AP0L0

import os
import sys
import csv
import json
import time
import subprocess
import urllib.request
import threading
import concurrent.futures

# ===== CONFIGURACIÓN =====
CSV_URL = "https://www.vpngate.net/api/iphone/"
CONNECTION_NAME = "AP0L0VPN"

# ===== CACHE =====
_cached_servers = []
_last_fetch_time = 0
_cancel_requested = False

# ===== CONSTANTES =====
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def _safe_int(val, default=0):
    """Convierte a entero de forma segura."""
    try:
        if val is None:
            return default
        val_str = str(val).strip()
        if not val_str or val_str == '-':
            return default
        return int(val_str)
    except Exception:
        return default


def fetch_servers(force=False):
    """Descarga la lista de servidores desde VPNGate."""
    global _cached_servers, _last_fetch_time
    
    current_time = time.time()
    if _cached_servers and (current_time - _last_fetch_time < 300) and not force:
        return _cached_servers
    
    print("[VPN] Obteniendo servidores VPN Gate...")
    try:
        req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
        
        lines = data.strip().split('\n')
        if len(lines) < 3:
            print("[VPN] Datos CSV insuficientes")
            return []
        
        # La primera línea es un comentario, la segunda tiene los encabezados
        reader = csv.DictReader(lines[1:])
        servers = []
        
        for row in reader:
            if not row.get('IP'):
                continue
            servers.append({
                'hostname': row.get('#HostName', ''),
                'ip': row.get('IP', ''),
                'score': _safe_int(row.get('Score'), 0),
                'ping': _safe_int(row.get('Ping'), 999),
                'speed': _safe_int(row.get('Speed'), 0),
                'country_long': row.get('CountryLong', ''),
                'country_short': row.get('CountryShort', ''),
                'uptime': _safe_int(row.get('Uptime'), 0)
            })
        
        _cached_servers = servers
        _last_fetch_time = current_time
        print(f"[VPN] {len(servers)} servidores obtenidos.")
        return servers
    except Exception as e:
        print(f"[VPN] Error obteniendo servidores: {e}")
        return _cached_servers or []


def get_countries():
    """Retorna lista de países disponibles con sus códigos."""
    servers = fetch_servers()
    countries = {}
    for s in servers:
        code = s['country_short']
        name = s['country_long']
        if code not in countries:
            countries[code] = {'code': code, 'name': name, 'count': 0}
        countries[code]['count'] += 1
    return sorted(list(countries.values()), key=lambda x: x['name'])


def get_current_ip():
    """Obtiene la IP pública actual."""
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
    except Exception as e:
        print(f"[VPN] Error obteniendo IP: {e}")
        return None


def disconnect():
    """Desconecta el VPN."""
    if not IS_WINDOWS:
        print("[VPN] VPN solo soportado en Windows")
        return {"success": False, "error": "Solo Windows"}
    
    try:
        print("[VPN] Desconectando...")
        subprocess.run(["rasdial", CONNECTION_NAME, "/disconnect"], capture_output=True)
        
        ps_cmd = f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        
        print("[VPN] Desconectado.")
        return {"success": True}
    except Exception as e:
        print(f"[VPN] Error desconectando: {e}")
        return {"success": False, "error": str(e)}


def get_status():
    """Obtiene el estado del VPN."""
    if not IS_WINDOWS:
        return {"connected": False, "status": "Solo Windows"}
    
    try:
        ps_cmd = f"Get-VpnConnection -Name '{CONNECTION_NAME}' | Select-Object -ExpandProperty ConnectionStatus"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
        status = res.stdout.strip()
        if status:
            return {"connected": status == "Connected", "status": status}
        return {"connected": False, "status": "Desconectado"}
    except Exception as e:
        print(f"[VPN] Error obteniendo estado: {e}")
        return {"connected": False, "status": "Error"}


def cancel_connection():
    """Cancela la conexión en curso."""
    global _cancel_requested
    _cancel_requested = True
    print("[VPN] Cancelando conexión...")
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)


def connect(country_code):
    """Conecta al mejor servidor VPN del país."""
    global _cancel_requested
    
    if not IS_WINDOWS:
        return {"success": False, "error": "VPN solo soportado en Windows"}
    
    _cancel_requested = False
    
    # Desconectar primero
    disconnect()
    
    servers = fetch_servers()
    country_servers = [s for s in servers if s['country_short'].lower() == country_code.lower()]
    country_servers.sort(key=lambda x: (x['speed'], -x['ping']), reverse=True)
    
    if not country_servers:
        return {"success": False, "error": f"No hay servidores para {country_code}"}
    
    print(f"[VPN] Conectando a {country_code} ({len(country_servers)} servidores)...")
    
    # Probar ping concurrente
    active_servers = []
    num_workers = min(60, len(country_servers))
    
    def ping_worker(s):
        if _cancel_requested:
            return None
        ip = s['ip']
        try:
            res = subprocess.run(
                ["ping", "-n", "1", "-w", "400", ip],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if res.returncode == 0:
                return s
        except Exception:
            pass
        return None
    
    print(f"[VPN] Probando servidores activos ({len(country_servers)})...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = executor.map(ping_worker, country_servers)
        for srv in results:
            if _cancel_requested:
                break
            if srv is not None:
                active_servers.append(srv)
    
    print(f"[VPN] {len(active_servers)} servidores activos.")
    
    if not active_servers:
        active_servers = country_servers[:5]
    
    # Intentar conectar
    for idx, s in enumerate(active_servers[:10]):
        if _cancel_requested:
            return {"success": False, "error": "Cancelado por el usuario"}
        
        server_ip = s['ip']
        print(f"[VPN] [{idx+1}/{len(active_servers[:10])}] Conectando a {server_ip}...")
        
        try:
            # Crear conexión VPN en Windows
            ps_cmd = (
                f"Add-VpnConnection -Name '{CONNECTION_NAME}' "
                f"-ServerAddress '{server_ip}' "
                f"-TunnelType L2tp "
                f"-L2tpPsk 'vpn' "
                f"-Force"
            )
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            
            if _cancel_requested:
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
                return {"success": False, "error": "Cancelado por el usuario"}
            
            # Conectar
            dial_res = subprocess.run(
                ["rasdial", CONNECTION_NAME, "vpn", "vpn"],
                capture_output=True,
                text=True,
                timeout=7,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if dial_res.returncode == 0:
                print(f"[VPN] ✅ Conectado a {server_ip}")
                time.sleep(2)
                ip_info = get_current_ip()
                return {
                    "success": True,
                    "server_ip": server_ip,
                    "new_ip_info": ip_info or {"ip": server_ip, "country": country_code}
                }
            else:
                error_msg = dial_res.stderr.strip() or dial_res.stdout.strip()
                print(f"[VPN] Falló: {error_msg}")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
                
        except subprocess.TimeoutExpired:
            print(f"[VPN] Timeout en {server_ip}")
            subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
        except Exception as e:
            print(f"[VPN] Error: {e}")
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
        
        if _cancel_requested:
            return {"success": False, "error": "Cancelado por el usuario"}
    
    return {"success": False, "error": "No se pudo conectar a ningún servidor"}


# ===== FUNCIÓN PARA AP0L0 =====

def vpn_control(params, player=None, speak=None):
    """
    Función de punto de entrada para AP0L0.
    
    Parámetros:
        action (str): "connect", "disconnect", "status", "countries"
        country (str): Código del país (para connect)
    """
    action = params.get("action", "status").lower()
    
    if action == "countries":
        countries = get_countries()
        result = "Países disponibles:\n" + "\n".join(f"  • {c['name']} ({c['code']})" for c in countries[:20])
        return result
    
    elif action == "connect":
        country = params.get("country", "FR").upper()
        if player:
            player.write_log(f"[VPN] Conectando a {country}...")
        result = connect(country)
        
        if result.get("success"):
            ip_info = result.get("new_ip_info", {})
            msg = f"✅ VPN conectado a {country}. IP: {ip_info.get('ip', 'desconocida')}"
        else:
            msg = f"❌ Error: {result.get('error', 'desconocido')}"
        
        if speak:
            speak(msg)
        return msg
    
    elif action == "disconnect":
        result = disconnect()
        msg = "✅ VPN desconectado" if result.get("success") else f"❌ Error: {result.get('error')}"
        if speak:
            speak(msg)
        return msg
    
    elif action == "status":
        status = get_status()
        if status.get("connected"):
            ip_info = get_current_ip()
            ip = ip_info.get("ip", "desconocida") if ip_info else "desconocida"
            return f"VPN conectado. IP: {ip}"
        else:
            return "VPN desconectado"
    
    else:
        return f"Acción '{action}' no soportada. Usa: connect, disconnect, status, countries"