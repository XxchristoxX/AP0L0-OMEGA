import subprocess
import json
def run(command_dict):
    command = command_dict.get("command")
    if command == "ls":
        result = subprocess.run(["ls"], capture_output=True, text=True)
        return result.stdout.strip()
    elif command == "cd":
        directory = command_dict.get("directory")
        try:
            os.chdir(directory)
            return f"Cambiado a directorio: {directory}"
        except FileNotFoundError:
            return f"Directorio no encontrado: {directory}"
    elif command == "pwd":
        return os.getcwd()
    elif command == "grep":
        text = command_dict.get("text")
        search = command_dict.get("search")
        result = subprocess.run(["grep", search], input=text, capture_output=True, text=True)
        return result.stdout.strip()
    elif command == "chmod":
        mode = command_dict.get("mode")
        file_path = command_dict.get("file_path")
        try:
            os.chmod(file_path, int(mode, 8))
            return f"Permisos cambiados en: {file_path}"
        except Exception as e:
            return str(e)
    else:
        return "Comando no reconocido."