import socket
def scan_ports(ip):
    open_ports = []
    ports_to_scan = [22, 80, 443, 8080]
    for port in ports_to_scan:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)  # Timeout de 1 segundo
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(port)
    return open_ports
def run(params):
    ip = params.get('ip')
    if not ip:
        return {"error": "Se requiere una dirección IP."}
    open_ports = scan_ports(ip)
    return {"ip": ip, "open_ports": open_ports}