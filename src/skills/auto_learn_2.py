import subprocess
def run(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
def nmap_simulation():
    return run("echo 'Simulando Nmap: escaneando puertos...'")
def metasploit_simulation():
    return run("echo 'Simulando Metasploit: cargando exploits...'")
def aircrack_ng_simulation():
    return run("echo 'Simulando Aircrack-ng: crackeando contraseñas de WiFi...'")
def main():
    print(nmap_simulation())
    print(metasploit_simulation())
    print(aircrack_ng_simulation())
if __name__ == "__main__":
    run(main())