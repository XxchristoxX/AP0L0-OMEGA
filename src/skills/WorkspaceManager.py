def run(params):
    import json
    import os
    import subprocess
    workspaces = {}
    def save_workspace(personality):
        windows = subprocess.check_output(['wmctrl', '-l']).decode('utf-8').strip().split('\n')
        workspaces[personality] = windows
    def restore_workspace(personality):
        if personality in workspaces:
            for window in workspaces[personality]:
                window_id = window.split()[0]
                subprocess.call(['wmctrl', '-ia', window_id])
    action = params.get('action')
    personality = params.get('personality')
    if action == 'save':
        save_workspace(personality)
        return json.dumps({"status": "success", "message": f"Workspace for {personality} saved."})
    elif action == 'restore':
        restore_workspace(personality)
        return json.dumps({"status": "success", "message": f"Workspace for {personality} restored."})
    return json.dumps({"status": "error", "message": "Invalid action or parameters."})