import json
import subprocess
from datetime import datetime
def get_system_updates():
    try:
        result = subprocess.run(['git', 'log', '--since="1 month ago"', '--pretty=format:%h - %s (%cd)', '--date=short'], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        updates = result.stdout.strip().split('\n') if result.returncode == 0 else []
        return updates
    except Exception as e:
        return [str(e)]
def run(params):
    updates = get_system_updates()
    return {"timestamp": datetime.now().isoformat(), "updates": updates}