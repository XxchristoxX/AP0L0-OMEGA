import os
import subprocess
import json
from datetime import datetime
def run(params):
    repo_path = params.get("repo_path")
    commit_message = params.get("commit_message", "Actualización automática")
    if not os.path.exists(repo_path):
        return {"status": "error", "message": "El camino del repositorio no existe"}
    os.chdir(repo_path)
    # Añadir cambios
    subprocess.run(["git", "add", "."])
    # Hacer commit
    subprocess.run(["git", "commit", "-m", commit_message])
    # Hacer push
    try:
        subprocess.run(["git", "push"], check=True)
        return {"status": "success", "message": "Cambios subidos exitosamente"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": str(e)}