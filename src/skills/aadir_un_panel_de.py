import json
from datetime import datetime
def run(params):
    # Simulación de estadísticas
    stats = {
        "total_users": 1000,
        "active_users": 750,
        "total_sales": 5000,
        "sales_today": 150,
        "last_update": datetime.now().isoformat()
    }
    # Actualizar estadísticas con parámetros si están presentes
    if params.get("update_stats"):
        stats["total_users"] += params.get("new_users", 0)
        stats["active_users"] += params.get("new_active_users", 0)
        stats["total_sales"] += params.get("new_sales", 0)
        stats["sales_today"] += params.get("new_sales_today", 0)
    return json.dumps(stats)