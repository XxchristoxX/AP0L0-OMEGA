import os
import subprocess
import json
from datetime import datetime
def check_open_ports():
    result = subprocess.run(['netstat', '-tuln'], capture_output=True, text=True)
    return result.stdout
def check_user_accounts():
    users = subprocess.run(['cut', '-d:', '-f1', '/etc/passwd'], capture_output=True, text=True)
    return users.stdout.splitlines()
def check_file_permissions(path):
    permissions = subprocess.run(['ls', '-l', path], capture_output=True, text=True)
    return permissions.stdout
def run(params):
    vulnerabilities = {}
    
    # Check for open ports
    vulnerabilities['open_ports'] = check_open_ports()
    
    # Check for user accounts
    vulnerabilities['user_accounts'] = check_user_accounts()
    
    # Check permissions for specified path
    if 'path' in params:
        vulnerabilities['file_permissions'] = check_file_permissions(params['path'])
    
    vulnerabilities['timestamp'] = datetime.now().isoformat()
    
    return json.dumps(vulnerabilities, indent=4)