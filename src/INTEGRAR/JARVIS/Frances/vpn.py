import os
import sys
import csv
import json
import re
import time
import subprocess
import urllib.request
import concurrent.futures

CSV_URL = "https://www.vpngate.net/api/iphone/"
MIRRORS_URL = "https://www.vpngate.net/en/sites.aspx"
CONNECTION_NAME = "JarvisVPN"
CATALOG_MAX_AGE = 7 * 24 * 60 * 60
MAX_OFFICIAL_MIRRORS = 5

_app_data_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.dirname(os.path.abspath(__file__))), "Jarvis")
CACHE_FILE = os.path.join(_app_data_dir, "vpn_servers_cache.json")

# Cache global pour éviter de retélécharger la liste des serveurs trop souvent
_cached_servers = []
_last_fetch_time = 0
_catalog_info = {"live": 0, "reserve": 0, "sources": 0}

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

def _download_text(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (JARVIS VPN catalog)'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode('utf-8', errors='replace')

def _official_csv_urls():
    """Retourne la source historique puis quelques miroirs publiés par VPN Gate."""
    urls = [CSV_URL]
    try:
        html = _download_text(MIRRORS_URL)
        mirror_roots = re.findall(r'https?://[^\s"\'<>]+?/en/', html, flags=re.IGNORECASE)
        for root in mirror_roots:
            candidate = root.rsplit('/en/', 1)[0].rstrip('/') + '/api/iphone/'
            if candidate not in urls:
                urls.append(candidate)
            if len(urls) >= MAX_OFFICIAL_MIRRORS + 1:
                break
    except Exception as exc:
        print(f"[VPN] Miroirs officiels indisponibles, source historique conservée : {exc}")
    return urls

def _parse_catalog(data, source, seen_at):
    lines = data.strip().splitlines()
    if len(lines) < 3:
        return []
    servers = []
    for row in csv.DictReader(lines[1:]):
        ip = (row.get('IP') or '').strip()
        code = (row.get('CountryShort') or '').strip().upper()
        if not ip or not code:
            continue
        servers.append({
            'hostname': row.get('#HostName'),
            'ip': ip,
            'score': safe_int(row.get('Score'), 0),
            'ping': safe_int(row.get('Ping'), 999),
            'speed': safe_int(row.get('Speed'), 0),
            'country_long': row.get('CountryLong') or code,
            'country_short': code,
            'uptime': safe_int(row.get('Uptime'), 0),
            'last_seen': seen_at,
            'is_live': True,
            'source': source
        })
    return servers

def _load_reserve(now):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as handle:
            saved = json.load(handle)
        return [s for s in saved if now - float(s.get('last_seen', 0)) <= CATALOG_MAX_AGE]
    except Exception:
        return []

def _save_reserve(servers):
    try:
        os.makedirs(_app_data_dir, exist_ok=True)
        temp_file = CACHE_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as handle:
            json.dump(servers, handle, ensure_ascii=False)
        os.replace(temp_file, CACHE_FILE)
    except Exception as exc:
        print(f"[VPN] Cache local non enregistré : {exc}")

def fetch_servers(force=False):
    """Agrège la source VPN Gate existante, ses miroirs officiels et la réserve récente."""
    global _cached_servers, _last_fetch_time, _catalog_info
    current_time = time.time()
    
    # Utiliser le cache si moins de 5 minutes
    if _cached_servers and (current_time - _last_fetch_time < 300) and not force:
        return _cached_servers
        
    print("[VPN] Actualisation VPN Gate + miroirs officiels...")
    urls = _official_csv_urls()
    downloaded = []
    successful_sources = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as executor:
        jobs = {executor.submit(_download_text, url): url for url in urls}
        for job in concurrent.futures.as_completed(jobs):
            url = jobs[job]
            try:
                source_servers = _parse_catalog(job.result(), url, current_time)
                downloaded.extend(source_servers)
                if source_servers:
                    successful_sources += 1
            except Exception as exc:
                print(f"[VPN] Source indisponible ({url}) : {exc}")

    # Une IP n'est ajoutée qu'une fois. Les entrées reçues maintenant restent prioritaires.
    merged = {}
    for server in downloaded:
        merged.setdefault(server['ip'], server)
    live_count = len(merged)
    for server in _load_reserve(current_time):
        if server.get('ip') not in merged:
            server['is_live'] = False
            server['source'] = 'reserve_locale'
            merged[server['ip']] = server

    if merged:
        servers = list(merged.values())
        _cached_servers = servers
        _last_fetch_time = current_time
        _catalog_info = {
            "live": live_count,
            "reserve": len(servers) - live_count,
            "sources": successful_sources
        }
        _save_reserve(servers)
        print(f"[VPN] {live_count} serveurs actuels + {_catalog_info['reserve']} en réserve récente.")
        return servers

    print("[VPN] Sources en ligne indisponibles : utilisation du cache mémoire.")
    return _cached_servers or []

def get_countries():
    """Retourne la liste des pays disponibles avec leur code ISO et nombre de serveurs."""
    servers = fetch_servers()
    countries = {}
    for s in servers:
        code = s['country_short']
        name = s['country_long']
        if code not in countries:
            countries[code] = {
                'code': code,
                'name': name,
                'count': 0,
                'live_count': 0
            }
        countries[code]['count'] += 1
        if s.get('is_live', True):
            countries[code]['live_count'] += 1
        
    # Trier par nom de pays
    return sorted(list(countries.values()), key=lambda x: x['name'])

def get_catalog_info():
    return dict(_catalog_info)

def get_current_public_ip():
    """Récupère l'IP publique actuelle et la localisation de l'utilisateur."""
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
    """Déconnecte le VPN JarvisVPN et supprime le profil de connexion."""
    try:
        print("[VPN] Déconnexion en cours...")
        # Lancer rasdial /disconnect
        subprocess.run(["rasdial", CONNECTION_NAME, "/disconnect"], capture_output=True)
        
        # Supprimer le profil VPN de Windows via PowerShell
        ps_cmd = f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        
        print("[VPN] Déconnecté avec succès.")
        return {"success": True}
    except Exception as e:
        print(f"[VPN] Erreur lors de la déconnexion : {e}")
        return {"success": False, "error": str(e)}

def get_status():
    """Retourne le statut actuel de la connexion VPN."""
    try:
        ps_cmd = f"Get-VpnConnection -Name '{CONNECTION_NAME}' | Select-Object -ExpandProperty ConnectionStatus"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
        status = res.stdout.strip()
        if status:
            return {"connected": status == "Connected", "status": status}
        return {"connected": False, "status": "Disconnected"}
    except Exception:
        return {"connected": False, "status": "Disconnected"}

cancel_requested = False

def cancel_connection():
    """Signale l'annulation de la connexion en cours et force l'arrêt de rasdial."""
    global cancel_requested
    cancel_requested = True
    print("[VPN] Annulation demandée par l'utilisateur. Force taskkill rasdial...")
    # Tuer de force le processus de numérotation Windows s'il est en cours
    subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)

def connect(country_code):
    """Tente de se connecter au meilleur serveur VPN du pays demandé en testant d'abord les serveurs de manière concurrente."""
    global cancel_requested
    cancel_requested = False
    
    # S'assurer d'être déconnecté d'abord
    disconnect()
    
    servers = fetch_servers()
    # Filtrer par pays et trier par Vitesse (Speed) décroissante
    country_servers = [s for s in servers if s['country_short'].lower() == country_code.lower()]
    country_servers.sort(key=lambda x: (x.get('is_live', True), x['speed'], -x['ping']), reverse=True)
    
    if not country_servers:
        return {"success": False, "error": f"Aucun serveur disponible pour le pays : {country_code}"}
        
    print(f"[VPN] Tentative de connexion vers {country_code} ({len(country_servers)} serveurs candidats)...")
    
    # 1. Sélectionner TOUS les serveurs candidats pour le test de ping
    candidates = country_servers
    active_servers = []
    
    # Ping concurrent avec ThreadPoolExecutor
    import concurrent.futures
    
    # Ajuster les workers de façon dynamique jusqu'à un maximum de 60 workers pour être ultra-rapide
    num_workers = min(60, len(candidates))
    if num_workers < 1:
        num_workers = 1
        
    def ping_worker(s):
        if cancel_requested:
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
        
    print(f"[VPN] Pré-filtrage concurrent de TOUS les serveurs actifs par ping ({len(candidates)} serveurs)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = executor.map(ping_worker, candidates)
        for r_srv in results:
            if cancel_requested:
                break
            if r_srv is not None:
                active_servers.append(r_srv)
                
    print(f"[VPN] {len(active_servers)} serveurs actifs répondent au ping sur {len(candidates)} testés.")
    
    # Si aucun ne répond au ping, on tente quand même les serveurs par défaut (fallback)
    if not active_servers:
        if cancel_requested:
            return {"success": False, "error": "Annulé par l'utilisateur."}
        print("[VPN] Aucun serveur n'a répondu au ping. Utilisation des serveurs de la liste par défaut.")
        active_servers = country_servers
        
    # Essayer de se connecter aux serveurs actifs (toutes les tentatives possibles)
    max_attempts = len(active_servers)
    
    for idx, s in enumerate(active_servers):
        if cancel_requested:
            print("[VPN] Connexion annulée avant la tentative.")
            return {"success": False, "error": "Annulé par l'utilisateur."}
            
        server_ip = s['ip']
        print(f"[VPN] [{idx+1}/{max_attempts}] Tentative de connexion au serveur {server_ip} (Ping: {s['ping']}ms)...")
        
        try:
            # 1. Créer la connexion L2TP/IPsec via PowerShell
            ps_cmd = (
                f"Add-VpnConnection -Name '{CONNECTION_NAME}' "
                f"-ServerAddress '{server_ip}' "
                f"-TunnelType L2tp "
                f"-L2tpPsk 'vpn' "
                f"-Force"
            )
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            
            if cancel_requested:
                print("[VPN] Connexion annulée juste après la création du profil.")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
                return {"success": False, "error": "Annulé par l'utilisateur."}

            # 2. Lancer la numérotation via rasdial avec un timeout réduit de 7 secondes
            dial_res = subprocess.run(
                ["rasdial", CONNECTION_NAME, "vpn", "vpn"], 
                capture_output=True, 
                text=True,
                timeout=7
            )
            
            if cancel_requested:
                print("[VPN] Connexion annulée pendant/juste après la numérotation.")
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
                return {"success": False, "error": "Annulé par l'utilisateur."}
                
            if dial_res.returncode == 0:
                print(f"[VPN] Connecté au serveur {server_ip} avec succès !")
                
                # Vérifier la nouvelle IP publique
                time.sleep(2)  # Attendre que la route s'établisse
                ip_info = get_current_public_ip()
                
                return {
                    "success": True,
                    "server_ip": server_ip,
                    "new_ip_info": ip_info or {"ip": server_ip, "country": country_code}
                }
            else:
                print(f"[VPN] Échec de la numérotation rasdial : {dial_res.stderr.strip() or dial_res.stdout.strip()}")
                # Nettoyer en cas d'échec
                subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
        except subprocess.TimeoutExpired:
            print(f"[VPN] Timeout (7s) expiré sur la numérotation rasdial pour {server_ip}.")
            # Tuer rasdial
            subprocess.run(["taskkill", "/F", "/IM", "rasdial.exe"], capture_output=True)
            # Nettoyer le profil
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
        except Exception as e:
            print(f"[VPN] Erreur lors de la tentative : {e}")
            subprocess.run(["powershell", "-Command", f"Remove-VpnConnection -Name '{CONNECTION_NAME}' -Force"], capture_output=True)
            
        if cancel_requested:
            print("[VPN] Connexion annulée détectée après la tentative.")
            return {"success": False, "error": "Annulé par l'utilisateur."}
            
    if cancel_requested:
        return {"success": False, "error": "Annulé par l'utilisateur."}
    return {"success": False, "error": f"Toutes les tentatives sur les {max_attempts} serveurs actifs ont échoué ou ont expiré. Veuillez réessayer."}
