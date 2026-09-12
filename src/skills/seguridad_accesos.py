import os
import subprocess
import json
import datetime
def monitor_access():
    # Comando para obtener los registros de seguridad de Windows (puede variar según el sistema operativo)
    command = "wevtutil qe Security /f:text /c:5"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    return result.stdout
def check_suspicious_activity(logs):
    suspicious_keywords = ["failed", "unauthorized", "denied", "error"]
    alerts = []
    
    for line in logs.splitlines():
        if any(keyword in line.lower() for keyword in suspicious_keywords):
            alerts.append(line)
    
    return alerts
def run(params):
    logs = monitor_access()
    suspicious_activities = check_suspicious_activity(logs)
    
    if suspicious_activities:
        alert = {
            "timestamp": datetime.datetime.now().isoformat(),
            "suspicious_activities": suspicious_activities
        }
        return json.dumps(alert)
    else:
        return json.dumps({"message": "No suspicious activities detected"})