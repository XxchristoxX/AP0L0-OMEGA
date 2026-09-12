# src/actions/vpn.py
"""
Cliente VPN para AP0L0 - Basado en VPNGate
Versión completa desde JARVIS
Soporte: conexión a servidores VPN, desconexión, listado de países, cancelación de conexión
"""

import os
import sys
import csv
import json
import time
import subprocess
import urllib.request
import threading
from pathlib import Path
from typing import List, Dict, Optional

# ===== CONFIGURACIÓN DE AP0L0 =====
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "src" / "config" / "api_keys.json"

# ===== CONSTANTES =====
CSV_URL = "https://www.vpngate.net/api/iphone/"
CONNECTION_NAME = "AP0L0VPN"

# Cache global para evitar descargas repetidas
_cached_servers = []
_last_fetch_time = 0


def _load_config():
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def safe_int(val, default=0):
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
    """Descarga la lista de servidores desde VPNGate y la parsea."""
    global _cached_servers, _last_fetch_time
    current_time = time.time()
    
    if _cached_servers and (current_time - _last_fetch_time < 300) and not force:
        return _cached_servers
        
    try:
        print("[VPN] Obteniendo servidores VPN Gate...")
        req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            
        lines = data.strip().split('\n')
        if len(lines) < 3:
            return []
            
        reader = csv.DictReader(lines[1:])
        
        servers = []
        for row in reader:
            if not row.get('IP'):
                continue
            servers.append({
                'hostname': row.get('#HostName'),
                'ip': row.get('IP'),
                'score': safe_int(row.get('Score'), 0),
                'ping': safe_int(row.get('Ping'), 999),
                'speed': safe_int(row.get('Speed'), 0),
                'country_long': row.get('CountryLong'),
                'country_short': row.get('CountryShort'),
                'uptime': safe_int(row.get('Uptime'), 0)
            })
            
        _cached_servers = servers
        _last_fetch_time = current_time
        print(f"[VPN] {len(servers)} servidores obtenidos.")
        return servers
    except Exception as e:
        print(f"[VPN] Error al obtener servidores: {e}")
        return _cached_servers or []


def get_countries():
    """Retorna lista de países disponibles con código y conteo."""
    servers = fetch_servers()
    countries = {}
    for s in servers:
        code = s['country_short']
        name = s['country_long']
        if code not in countries:
            countries[code] = {
                'code': code,
                'name': name,
                'count': 0
            }
        countries[code]['count'] += 1
        
    return sorted(list(countries.values()), key=lambda x: x['name'])


def get_current_public_ip():
    """Obtiene la IP pública actual y ubicación."""
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


def disconnect():
    """Desconecta la VPN y elimina el perfil de conexión."""
    try:
        print("[VPN] Desconectando...")
        subprocess.run(["rasdial", CONNECTION_NAME, "/disconnect"], capture_output=True)
        
        # Eliminar perfil VPN de Windows
        ps_cmd = f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        
        print("[VPN] Desconectado.")
        return {"success": True}
    except Exception as e:
        print(f"[VPN] Error en desconexión: {e}")
        return {"success": False, "error": str(e)}


def get_status():
    """Retorna el estado actual de la conexión VPN."""
    try:
        ps_cmd = f"Get-VpnConnection -Name '{CONNECTION_NAME}' | Select-Object -ExpandProperty ConnectionStatus"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
        status = res.stdout.strip()
        if status:
            return {"connected": status == "Connected", "status": status}
        return {"connected": False, "status": "Disconnected"}
    except Exception:
        return {"connected": False, "status": "Disconnected"}


# Variable global para cancelación
_cancel_requested = False


def cancel_connection():
    """Cancela la conexión en curso."""
    global _cancel_requested
    _cancel_requested = True
    print("[VPN] Cancelación solicitada. Forzando finalización de rasdial...")
    subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)


def connect(country_code):
    """Conecta al mejor servidor del país indicado."""
    global _cancel_requested
    _cancel_requested = False
    
    disconnect()
    
    servers = fetch_servers()
    country_servers = [s for s in servers if s['country_short'].lower() == country_code.lower()]
    country_servers.sort(key=lambda x: (x['speed'], -x['ping']), reverse=True)
    
    if not country_servers:
        return {"success": False, "error": f"No hay servidores disponibles para {country_code}"}
        
    print(f"[VPN] Conectando a {country_code} ({len(country_servers)} servidores)...")
    
    # Probar servidores activos con ping concurrente
    import concurrent.futures
    active_servers = []
    
    def ping_worker(s):
        if _cancel_requested:
            return None
        ip = s['ip']
        try:
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
        
    print(f"[VPN] Probando {len(country_servers)} servidores...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(60, len(country_servers))) as executor:
        results = executor.map(ping_worker, country_servers)
        for r in results:
            if _cancel_requested:
                break
            if r is not None:
                active_servers.append(r)
                
    print(f"[VPN] {len(active_servers)} servidores activos.")
    
    if not active_servers:
        if _cancel_requested:
            return {"success": False, "error": "Cancelado por el usuario."}
        print("[VPN] Ningún ping respondió. Usando lista completa.")
        active_servers = country_servers
        
    max_attempts = len(active_servers)
    
    for idx, s in enumerate(active_servers):
        if _cancel_requested:
            print("[VPN] Conexión cancelada.")
            return {"success": False, "error": "Cancelado por el usuario."}
            
        server_ip = s['ip']
        print(f"[VPN] [{idx+1}/{max_attempts}] Intentando con {server_ip} (Ping: {s['ping']}ms)...")
        
        try:
            # Crear conexión L2TP/IPsec
            ps_cmd = (
                f"Add-VpnConnection -Name '{CONNECTION_NAME}' "
                f"-ServerAddress '{server_ip}' "
                f"-TunnelType L2tp "
                f"-L2tpPsk 'vpn' "
                f"-Force"
            )
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            
            if _cancel_requested:
                print("[VPN] Cancelado después de crear perfil.")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
                return {"success": False, "error": "Cancelado por el usuario."}

            # Llamar a rasdial con timeout de 7 segundos
            dial_res = subprocess.run(
                ["rasdial", CONNECTION_NAME, "vpn", "vpn"], 
                capture_output=True, 
                text=True,
                timeout=7
            )
            
            if _cancel_requested:
                print("[VPN] Cancelado durante/después de la llamada.")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
                return {"success": False, "error": "Cancelado por el usuario."}
                
            if dial_res.returncode == 0:
                print(f"[VPN] Conectado a {server_ip}!")
                time.sleep(2)
                ip_info = get_current_public_ip()
                return {
                    "success": True,
                    "server_ip": server_ip,
                    "new_ip_info": ip_info or {"ip": server_ip, "country": country_code}
                }
            else:
                print(f"[VPN] Falló rasdial: {dial_res.stderr.strip() or dial_res.stdout.strip()}")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
        except subprocess.TimeoutExpired:
            print(f"[VPN] Timeout (7s) en rasdial para {server_ip}.")
            subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
        except Exception as e:
            print(f"[VPN] Error: {e}")
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
            
        if _cancel_requested:
            print("[VPN] Cancelación detectada tras intento.")
            return {"success": False, "error": "Cancelado por el usuario."}
            
    if _cancel_requested:
        return {"success": False, "error": "Cancelado por el usuario."}
    return {"success": False, "error": f"Fallaron todos los intentos ({max_attempts} servidores)."}


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 (Herramienta) =====

async def vpn_control(params: dict, player=None, speak=None) -> str:
    """
    Punto de entrada para el sistema de herramientas.
    Parámetros:
        action: "connect", "disconnect", "status", "countries"
        country: código de país (para connect)
    """
    action = params.get("action", "status").lower()
    country = params.get("country", "").upper()
    
    if action == "countries":
        countries = get_countries()
        if player:
            player.write_log("[VPN] Países disponibles:")
            for c in countries:
                player.write_log(f"  {c['code']}: {c['name']} ({c['count']} servidores)")
        return "Lista de países actualizada en la consola."
    
    if action == "status":
        status = get_status()
        ip_info = get_current_public_ip()
        result = f"Estado VPN: {status.get('status', 'Desconocido')}"
        if ip_info:
            result += f" | IP: {ip_info.get('ip')} ({ip_info.get('country')})"
        if player:
            player.write_log(f"[VPN] {result}")
        if speak:
            speak(result)
        return result
    
    if action == "connect":
        if not country:
            return "Especifica un país (ej: FR, US, DE)."
        if player:
            player.write_log(f"[VPN] Conectando a {country}...")
        if speak:
            speak(f"Conectando a VPN en {country}...")
        
        # Ejecutar en un hilo separado para no bloquear
        def run_connect():
            return connect(country)
        
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_connect)
        
        if result.get("success"):
            msg = f"VPN conectada a {country} en {result.get('server_ip')}."
            if player:
                player.write_log(f"[VPN] {msg}")
            if speak:
                speak(msg)
            return msg
        else:
            err = result.get("error", "Error desconocido.")
            if player:
                player.write_log(f"[VPN] Falló: {err}")
            if speak:
                speak(f"Fallo la conexión VPN: {err}")
            return f"Fallo: {err}"
    
    if action == "disconnect":
        result = disconnect()
        if result.get("success"):
            msg = "VPN desconectada."
        else:
            msg = f"Error al desconectar: {result.get('error')}"
        if player:
            player.write_log(f"[VPN] {msg}")
        if speak:
            speak(msg)
        return msg
    
    if action == "cancel":
        cancel_connection()
        msg = "Cancelación de conexión solicitada."
        if player:
            player.write_log(f"[VPN] {msg}")
        if speak:
            speak(msg)
        return msg
    
    return f"Acción '{action}' no soportada. Usa: connect, disconnect, status, countries, cancel"