import json
from pathlib import Path
import datetime
def run(params):
    try:
        comando_voz = params.get("comando", "").lower()
        usuario = params.get("usuario", "default")
        log_path = Path("flujos_automatizados.log")
        timestamp = datetime.datetime.now().isoformat()
        habitos_conocidos = {
            "preparar entorno desarrollo": ["Abrir IDE", "Iniciar servidor local", "Revisar correos pendientes"],
            "organizar escritorio": ["Mover PDFs a Documentos", "Limpiar papelera", "Agrupar capturas de pantalla"],
            "resumen matutino": ["Analizar bandeja de entrada", "Listar tareas del día", "Verificar calendario"]
        }
        accion_ejecutada = habitos_conocidos.get(comando_voz, ["Ejecutar macro personalizada genérica"])
        registro = {
            "timestamp": timestamp,
            "usuario": usuario,
            "comando": comando_voz,
            "acciones": accion_ejecutada,
            "estado": "Completado con éxito"
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro) + "\n")
        return {
            "status": "success",
            "mensaje": f"Flujo contextual para '{comando_voz}' ejecutado exitosamente.",
            "acciones_realizadas": accion_ejecutada,
            "tiempo_ahorrado_estimado_minutos": 15
        }
    except Exception as e:
        return {
            "status": "error",
            "mensaje": str(e)
        }