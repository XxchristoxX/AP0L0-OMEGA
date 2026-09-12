import json
import os
import requests
from datetime import datetime
def backup_assistant(configurations, cloud_url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_data = {
        "timestamp": timestamp,
        "configurations": configurations
    }
    response = requests.post(cloud_url, json=backup_data)
    return response.status_code, response.json()
def run(params):
    configurations = params.get("configurations", {})
    cloud_url = params.get("cloud_url", "")
    if not configurations or not cloud_url:
        return {"status": "error", "message": "Missing configurations or cloud URL"}
    status_code, response = backup_assistant(configurations, cloud_url)
    return {"status_code": status_code, "response": response}